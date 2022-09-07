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
) -> Optional[tuple[float, str, List[str], float, str, str]]:
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
            The technical analysis using TradingView.
    """

    if majority == "crypto" or majority == "🤷‍♂️":
        coin = await get_coin_info(ticker)
        # If volume of the crypto is bigger than 1,000,000, it is likely a crypto
        # Stupid Tessla Coin https://www.coingecko.com/en/coins/tessla-coin
        if coin is not None:
            if coin[0] > 1000000 or ticker.endswith("BTC"):
                four_h_ta, one_d_ta = tv.get_tv_TA(ticker, "crypto")
                return *coin, four_h_ta, one_d_ta
        stock = await get_stock_info(ticker)
    else:
        stock = await get_stock_info(ticker)
        if stock is not None:
            if stock[0] > 1000000:
                four_h_ta, one_d_ta = tv.get_tv_TA(ticker, "stock")
                return *stock, four_h_ta, one_d_ta
        coin = await get_coin_info(ticker)

    # First in tuple represents volume
    if coin is None:
        coin_vol = 0
    else:
        coin_vol = coin[0]

    if stock is None:
        stock_vol = 0
    else:
        stock_vol = stock[0]

    if coin_vol > stock_vol and coin_vol > 50000:
        four_h_ta, one_d_ta = tv.get_tv_TA(ticker, "crypto")
        return *coin, four_h_ta, one_d_ta
    elif coin_vol < stock_vol:
        four_h_ta, one_d_ta = tv.get_tv_TA(ticker, "stock")
        return *stock, four_h_ta, one_d_ta
    else:
        return None
