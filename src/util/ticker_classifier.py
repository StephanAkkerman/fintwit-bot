##> Imports
# > Standard libaries
from __future__ import annotations
from typing import Optional, List

# Local dependencies
from util.tv_data import tv
from util.cg_data import get_coin_info
from util.yf_data import get_stock_info


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

    # If the majority is crypt or unkown check if the ticker is a crypto
    if majority == "crypto" or majority == "Unknown":
        (
            c_volume,
            c_website,
            c_exchange,
            c_price,
            c_change,
            c_ticker,
        ) = await get_coin_info(ticker)
        # If volume of the crypto is bigger than 1,000,000, it is likely a crypto
        # Stupid Tessla Coin https://www.coingecko.com/en/coins/tessla-coin

        if c_volume > 1000000 or ticker.endswith("BTC"):
            four_h_ta, one_d_ta = tv.get_tv_TA(ticker, "crypto")
            return (
                c_volume,
                c_website,
                c_exchange,
                c_price,
                c_change,
                four_h_ta,
                one_d_ta,
                c_ticker,
            )

        (
            s_volume,
            s_website,
            s_exchange,
            s_price,
            s_change,
            s_ticker,
        ) = await get_stock_info(ticker)

    else:
        (
            s_volume,
            s_website,
            s_exchange,
            s_price,
            s_change,
            s_ticker,
        ) = await get_stock_info(ticker)
        if s_volume > 1000000:
            four_h_ta, one_d_ta = tv.get_tv_TA(ticker, "stock")
            return (
                s_volume,
                s_website,
                s_exchange,
                s_price,
                s_change,
                four_h_ta,
                one_d_ta,
                s_ticker,
            )

        (
            c_volume,
            c_website,
            c_exchange,
            c_price,
            c_change,
            c_ticker,
        ) = await get_coin_info(ticker)

    if c_volume > s_volume and c_volume > 50000:
        four_h_ta, one_d_ta = tv.get_tv_TA(ticker, "crypto")
        return (
            c_volume,
            c_website,
            c_exchange,
            c_price,
            c_change,
            four_h_ta,
            one_d_ta,
            c_ticker,
        )
    elif c_volume < s_volume:
        four_h_ta, one_d_ta = tv.get_tv_TA(ticker, "stock")
        return (
            s_volume,
            s_website,
            s_exchange,
            s_price,
            s_change,
            four_h_ta,
            one_d_ta,
            s_ticker,
        )
