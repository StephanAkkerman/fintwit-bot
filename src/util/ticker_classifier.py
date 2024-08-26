##> Imports
# > Standard libaries
from __future__ import annotations

from typing import List, Optional, Tuple

from api.coingecko import get_coin_info

# Local dependencies
from api.tradingview import tv
from api.yahoo import get_stock_info
from constants.logger import logger


async def get_financials(ticker: str, website: str):
    """
    Get financial data (price, change, and technical analysis) for a given ticker.

    Parameters
    ----------
    ticker : str
        The ticker of the asset.
    website : str
        The source website (e.g., CoinGecko, Yahoo Finance, etc.).

    Returns
    -------
    tuple
        price, change, four_h_ta, one_d_ta
    """

    asset_type_mapping = {
        "coingecko": "crypto",
        "yahoo": "stock",
    }  # , "forex": "forex"}

    # Determine the asset type based on the website
    asset_type = next((v for k, v in asset_type_mapping.items() if k in website), None)

    if not asset_type:
        logger.error(f"Unknown website: {website} for ticker: {ticker}")

    # Get financial info based on asset type
    if asset_type == "crypto":
        _, _, _, price, change, _ = await get_coin_info(ticker)
    else:
        _, _, _, price, change, _ = await get_stock_info(ticker, asset_type)

    # Get technical analysis (TA) data
    four_h_ta, one_d_ta = tv.get_tv_TA(ticker, asset_type)

    return price, change, four_h_ta, one_d_ta


async def fetch_asset_info(ticker: str, asset_type: str) -> Tuple:
    """
    Fetches information for the given ticker and asset type.
    """
    if asset_type == "crypto":
        return await get_coin_info(ticker)
    elif asset_type == "stock":
        return await get_stock_info(ticker)
    # elif asset_type == "forex" and ticker in currencies:
    #     return (
    #         100000,
    #         "https://www.tradingview.com/ideas/eur/?forex",
    #         "forex",
    #         None,
    #         None,
    #         None,
    #         None,
    #         ticker,
    #         True,
    #     )
    else:
        return await get_stock_info(ticker, asset_type)


async def perform_ta(ticker: str, base_sym: str, asset_type: str, get_TA: bool):
    """
    Perform technical analysis if required.
    """
    if get_TA:
        if base_sym is None:
            logger.warning(f"No base symbol found for {ticker}")
            base_sym = ticker
        return tv.get_tv_TA(base_sym, asset_type)
    return None, None


async def get_best_guess(ticker: str, asset_type: str) -> Tuple:
    """
    Gets the best guess of the ticker.

    Parameters
    ----------
    ticker : str
        The ticker mentioned in a tweet, e.g. BTC.
    asset_type : str
        The guessed asset type, this can be crypto or stock.

    Returns
    -------
    tuple
        The data of the best guess.
    """

    get_TA = False
    if asset_type == "crypto" and ticker.endswith("BTC") and ticker != "BTC":
        get_TA = True
        ticker = ticker[:-3]

    volume, website, exchange, price, change, base_sym = await fetch_asset_info(
        ticker, asset_type
    )

    # Forex-specific logic
    # if asset_type == "forex" and price > 0:
    #     four_h_ta, one_d_ta = tv.get_tv_TA(ticker, "forex")
    #     return (
    #         volume,
    #         website,
    #         exchange,
    #         price,
    #         change,
    #         four_h_ta,
    #         one_d_ta,
    #         base_sym,
    #         True,
    #     )

    # Perform technical analysis if necessary
    if volume > 1000000 or get_TA:
        four_h_ta, one_d_ta = await perform_ta(ticker, base_sym, asset_type, True)
    else:
        four_h_ta, one_d_ta = None, None

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
) -> Optional[Tuple[float, str, List[str], float, str, str]]:
    """
    Classify the ticker as crypto, stock, or forex based on the best guess.

    Parameters
    ----------
    ticker : str
        The ticker of the coin or stock.
    majority : str
        The guessed majority of the ticker.

    Returns
    -------
    Optional[tuple]
        The classified asset data.
    """

    # Try forex first
    # forex_data = await get_best_guess(ticker, "forex")
    # if forex_data[-1]:  # If TA exists
    #     return forex_data[:-1]

    if majority == "crypto":
        crypto_data = await get_best_guess(ticker, "crypto")
        if crypto_data[-1]:  # If TA exists
            return crypto_data[:-1]
        stock_data = await get_best_guess(ticker, "stock")
    elif majority == "stocks":
        stock_data = await get_best_guess(ticker, "stock")
        if stock_data[-1]:  # If TA exists
            return stock_data[:-1]
        crypto_data = await get_best_guess(ticker, "crypto")
    else:
        crypto_data = await get_best_guess(ticker, "crypto")
        stock_data = await get_best_guess(ticker, "stock")

    # Compare volumes and determine best guess
    c_volume, s_volume = crypto_data[0], stock_data[0]

    if c_volume > s_volume and c_volume > 50000:
        if not crypto_data[5]:  # No TA data yet
            crypto_data = list(crypto_data)
            crypto_data[5], crypto_data[6] = tv.get_tv_TA(ticker, "crypto")
            crypto_data = tuple(crypto_data)
        return crypto_data[:-1]
    else:
        if not stock_data[5]:  # No TA data yet
            stock_data = list(stock_data)
            stock_data[5], stock_data[6] = tv.get_tv_TA(ticker, "stock")
            stock_data = tuple(stock_data)
        return stock_data[:-1]
