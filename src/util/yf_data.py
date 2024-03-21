##> Imports
# > Standard libaries
from __future__ import annotations
from typing import Optional, List

# > 3rd Party Dependencies
from yahooquery import Ticker

# Local dependencies
from util.formatting import format_change
from util.afterhours import afterHours
from util.tv_data import tv


def yf_info(ticker: str, do_format_change: bool = True):
    # try:
    stock_info = Ticker(ticker, asynchronous=True).price

    # Test if the ticker is valid
    if not isinstance(stock_info.get(ticker), dict):
        return None

    stock_info = stock_info[ticker]
    prices = []
    changes = []

    # Helper function to format and append price data
    def append_price_data(price_key, change_key):
        price = stock_info.get(price_key)
        change = stock_info.get(change_key, 0)
        if do_format_change:
            change = format_change(change)
        if price and price != 0:
            prices.append(price)
            changes.append(change or "N/A")  # Handle None or missing change

    # Determine which price to report based on market hours
    if afterHours():
        append_price_data("preMarketPrice", "preMarketChangePercent")
    append_price_data("regularMarketPrice", "regularMarketChangePercent")

    # Calculate volume
    volume = stock_info.get("regularMarketVolume", 0) * prices[-1] if prices else 0

    # Prepare return values
    url = f"https://finance.yahoo.com/quote/{ticker}"
    exchange = stock_info.get("exchange", "N/A")

    return volume, url, exchange, prices, changes if changes else ["N/A"], ticker

    # TODO: ratelimit exception
    # except Exception as e:
    #    print(f"Error in getting Yahoo Finance data for {ticker}: {e}")

    return None


async def get_stock_info(
    ticker: str, asset_type: str = "stock", do_format_change: bool = True
) -> Optional[tuple[float, str, List[str], float, str, str]]:
    """
    Gets the volume, website, exchanges, price, and change of the stock.

    Parameters
    ----------
    ticker : str
        The ticker of the stock.
    asset_type : str
        The type of asset, this can be stock or forex.
    do_format_change : bool
        Whether to format the change or not.

    Returns
    -------
    Optional[tuple[float, str, List[str], float, str]]
        float
            The volume of the stock.
        str
            The website of the stock.
        list[str]
            The exchanges of the stock.
        float
            The price of the stock.
        str
            The 24h price change of the stock.
        str
            The ticker, to match the crypto function.
    """

    if asset_type == "stock":
        stock_info = yf_info(ticker, do_format_change)
        if stock_info:
            return stock_info

    # Check TradingView data
    tv_data = await tv.get_tv_data(ticker, asset_type)
    if tv_data:
        # print(f"Could not find {ticker} on Yahoo Finance, using TradingView data.")
        price, perc_change, volume, exchange, website = tv_data

    if do_format_change:
        perc_change = format_change(perc_change) if perc_change else "N/A"
    return (
        volume,
        website,
        exchange,
        price,
        perc_change,
        ticker,
    )
