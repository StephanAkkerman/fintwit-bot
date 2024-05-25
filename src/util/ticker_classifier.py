##> Imports
# > Standard libaries
from __future__ import annotations

from typing import List, Optional

from util.cg_data import get_coin_info

# Local dependencies
from util.tv_data import tv
from util.tv_symbols import currencies
from util.yf_data import get_stock_info


async def get_financials(ticker: str, website: str):
    if "coingecko" in website:
        _, _, _, price, change, _ = await get_coin_info(ticker)
        four_h_ta, one_d_ta = tv.get_tv_TA(ticker, "crypto")
    elif "yahoo" in website:
        _, _, _, price, change, _ = await get_stock_info(ticker)
        four_h_ta, one_d_ta = tv.get_tv_TA(ticker, "stock")
    elif "forex" in website:
        _, _, _, price, change, _ = await get_stock_info(ticker, "forex")
        four_h_ta, one_d_ta = tv.get_tv_TA(ticker, "forex")

    return price, change, four_h_ta, one_d_ta


async def get_best_guess(ticker: str, asset_type: str):
    """
    Gets the best guess of the ticker.

    Parameters
    ----------
    ticker : str
        The ticker mentioned in a tweet, e.g. BTC
    asset_type : str
        The guessed asset type, this can be crypto, stock or forex.

    Returns
    -------
    tuple
        The data of the best guess
    """

    get_TA = False
    four_h_ta = one_d_ta = None

    if asset_type == "crypto" and ticker.endswith("BTC") and ticker != "BTC":
        get_TA = True
        ticker = ticker[:-3]

    if asset_type == "crypto":
        (
            volume,
            website,
            exchange,
            price,
            change,
            base_sym,
        ) = await get_coin_info(ticker)

    elif asset_type == "stock":
        (
            volume,
            website,
            exchange,
            price,
            change,
            base_sym,
        ) = await get_stock_info(ticker)

    elif asset_type == "forex":
        if ticker in currencies:
            return (
                100000,
                "https://www.tradingview.com/ideas/eur/?forex",
                "forex",
                None,
                None,
                None,
                None,
                ticker,
                True,
            )
        (
            volume,
            website,
            exchange,
            price,
            change,
            base_sym,
        ) = await get_stock_info(ticker, asset_type)

        if price > 0:
            four_h_ta, one_d_ta = tv.get_tv_TA(ticker, "forex")
            return (
                volume,
                website,
                exchange,
                price,
                change,
                four_h_ta,
                one_d_ta,
                base_sym,
                True,
            )

    # If volume of the crypto is bigger than 1,000,000, it is likely a crypto
    # Stupid Tessla Coin https://www.coingecko.com/en/coins/tessla-coin
    if volume > 1000000:
        get_TA = True

    # Set the TA data, only if volume is high enough
    if get_TA:
        if base_sym is None:
            print("No base symbol found for", ticker)
            base_sym = ticker
        four_h_ta, one_d_ta = tv.get_tv_TA(base_sym, asset_type)

    return (
        volume,
        website,
        exchange,
        price,
        change,
        four_h_ta,
        one_d_ta,
        base_sym,
        get_TA,
    )


async def classify_ticker(
    ticker: str, majority: str
) -> Optional[tuple[float, str, List[str], float, str, str, str]]:
    """
    Main function to classify the ticker as crypto or stock.

    Parameters
    ----------
    ticker : str
        The ticker of the coin or stock.
    majority : str
        The guessed majority of the ticker.

    Returns
    -------
    Optional[tuple[float, str, List[str], float, str, str]]
        float
            The volume of the coin or stock.
        str
            The website of the coin or stock.
        list[str]
            The exchanges of the coin or stock.
        float
            The price of the coin or stock.
        str
            The 24h price change of the coin or stock.
        str
            The four hour technical analysis using TradingView.
        str
            The daily technical analysis using TradingView.
        str
            The base ticker.
    """

    # Try forex first
    forex_data = await get_best_guess(ticker, "forex")
    if forex_data[-1]:
        return forex_data[:-1]

    # If the majority is crypto or unkown check if the ticker is a crypto
    if majority == "crypto":
        crypto_data = await get_best_guess(ticker, "crypto")

        if crypto_data[-1]:
            return crypto_data[:-1]

        stock_data = await get_best_guess(ticker, "stock")

    elif majority == "stocks":
        stock_data = await get_best_guess(ticker, "stock")

        if stock_data[-1]:
            return stock_data[:-1]

        crypto_data = await get_best_guess(ticker, "crypto")
    else:
        crypto_data = await get_best_guess(ticker, "crypto")
        stock_data = await get_best_guess(ticker, "stock")

    # If it was not the majority, compare the data
    c_volume = crypto_data[0]
    s_volume = stock_data[0]

    if c_volume > s_volume and c_volume > 50000:
        if crypto_data[5] is None:
            four_h_ta, one_d_ta = tv.get_tv_TA(ticker, "crypto")

            crypto_data = list(crypto_data)
            crypto_data[5] = four_h_ta
            crypto_data[6] = one_d_ta
            tuple(crypto_data)

        return crypto_data[:-1]

    elif c_volume < s_volume:
        if stock_data[5] is None:
            four_h_ta, one_d_ta = tv.get_tv_TA(ticker, "stock")

            stock_data = list(stock_data)
            stock_data[5] = four_h_ta
            stock_data[6] = one_d_ta
            tuple(stock_data)

        return stock_data[:-1]
