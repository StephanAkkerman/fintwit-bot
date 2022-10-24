##> Imports
# > Standard libaries
from __future__ import annotations
from typing import Optional, List

# > 3rd Party Dependencies
import yfinance as yf

# Local dependencies
from util.vars import format_change
from util.afterhours import afterHours
from util.tv_data import tv

def get_AH_info(stock_info):    
    price = change = None
    
    if stock_info.info["preMarketPrice"] != None and stock_info.info["bid"] != None:        
        # Use bid if premarket price is not available
        price = (
            round(stock_info.info["preMarketPrice"], 2)
            if stock_info.info["preMarketPrice"] != None
            else stock_info.info["bid"]
        )
        
        if price and stock_info.info["regularMarketPrice"]:
            change = round(
                (price - stock_info.info["regularMarketPrice"])
                / stock_info.info["regularMarketPrice"]
                * 100,
                2,
            )
            change = format_change(change)
            
    return price, change

def get_standard_info(stock_info):
    price = change = None
    
    if stock_info.info["regularMarketPrice"] != None:
        price = round(stock_info.info["regularMarketPrice"], 2)
        
        if price and stock_info.info["regularMarketPreviousClose"]:
            change = round(
                (price - stock_info.info["regularMarketPreviousClose"])
                / stock_info.info["regularMarketPreviousClose"]
                * 100,
                2,
            )
            change = format_change(change)
            
    return price, change

async def get_stock_info(
    ticker: str, asset_type: str = "stock"
) -> Optional[tuple[float, str, List[str], float, str, str]]:
    """
    Gets the volume, website, exchanges, price, and change of the stock.

    Parameters
    ----------
    ticker : str
        The ticker of the stock.
    asset_type : str
        The type of asset, this can be stock or forex.

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

        stock_info = yf.Ticker(ticker)

        try:
            if stock_info.info["regularMarketPrice"] != None:

                prices = []
                changes = []

                # Return prices corresponding to market hours
                if afterHours():
                    price, change = get_AH_info(stock_info)
                    
                    if price and change:
                        # Dont add if prices are 0
                        if price != 0:
                            prices.append(price)
                            changes.append(change)

                # Could try 'currentPrice' as well
                price, change = get_standard_info(stock_info)
                
                prices.append(price)
                changes.append(change)

                # Return the important information
                # Could also try 'volume' or 'volume24Hr' (is None if market is closed)
                volume = stock_info.info["regularMarketVolume"] * price

                return (
                    volume,
                    f"https://finance.yahoo.com/quote/{ticker}",
                    stock_info.info["exchange"],
                    prices,
                    changes,
                    ticker,
                )

        except Exception:
            pass

    # Check TradingView data
    tv_data = await tv.get_tv_data(ticker, asset_type)
    price, perc_change, volume, exchange, website = tv_data
    return (
        volume,
        website,
        exchange,
        price,
        format_change(perc_change) if perc_change else None,
        ticker,
    )
