##> Imports
# > Standard libaries
from __future__ import annotations
import traceback
from typing import Optional, List

# > 3rd Party Dependencies
import yfinance as yf

# Local dependencies
from util.tv_data import TV_data
from util.vars import stables, cg, format_change
from util.afterhours import afterHours
from util.db import get_db

tv = TV_data()
cg_coins = get_db("cg_crypto")


def get_crypto_info(ids):

    if len(ids) > 1:
        id = None
        best_vol = 0
        coin_dict = None
        for symbol in ids.values:
            # Catch potential errors
            try:
                coin_info = cg.get_coin_by_id(symbol)
                if "usd" in coin_info["market_data"]["total_volume"]:
                    volume = coin_info["market_data"]["total_volume"]["usd"]
                    if volume > best_vol:
                        best_vol = volume
                        id = symbol
                        coin_dict = coin_info
            except Exception:
                pass

    elif len(ids) == 1:
        id = ids.values[0]
        # Try in case the CoinGecko API does not work
        try:
            coin_dict = cg.get_coin_by_id(id)
        except Exception:
            return None, None

    return coin_dict, id


def get_coin_vol(coin_dict: dict) -> float:
    if "total_volume" in coin_dict["market_data"].keys():
        if "usd" in coin_dict["market_data"]["total_volume"].keys():
            return coin_dict["market_data"]["total_volume"]["usd"]
        else:
            return 1


def get_coin_price(coin_dict: dict) -> float:
    if "current_price" in coin_dict["market_data"].keys():
        if "usd" in coin_dict["market_data"]["current_price"].keys():
            return coin_dict["market_data"]["current_price"]["usd"]
        else:
            return 0


def get_coin_exchanges(coin_dict: dict) -> list:
    if "tickers" in coin_dict.keys():
        if "exchange" in coin_dict["tickers"][0].keys():
            return [ticker["exchange"]["name"] for ticker in coin_dict["tickers"]]
        else:
            return []


def get_info_from_dict(coin_dict: dict):
    if coin_dict:
        if "market_data" in coin_dict.keys():
            volume = get_coin_vol(coin_dict)
            price = get_coin_price(coin_dict)

            if "price_change_percentage_24h" in coin_dict["market_data"].keys():
                change = round(
                    coin_dict["market_data"]["price_change_percentage_24h"], 2
                )
            else:
                change = "N/A"

            # Get the exchanges
            exchanges = get_coin_exchanges(coin_dict)

            return volume, price, change, exchanges
    return None, None, None, None


async def get_coin_info(
    ticker: str,
) -> Optional[tuple[float, str, List[str], float, str]]:
    """
    Gets the volume, website, exchanges, price, and change of the coin.
    This can only be called maximum 50 times per minute.

    Parameters
    ----------
    ticker : str
        The ticker of the coin.

    Returns
    -------
    float
        The volume of the coin.
    str
        The website of the coin.
    list[str]
        The exchanges of the coin.
    float
        The price of the coin.
    str
        The 24h price change of the coin.
    """

    # Remove formatting from ticker input
    if ticker not in stables:
        for stable in stables:
            if ticker.endswith(stable):
                ticker = ticker[: -len(stable)]

    # Get the id of the ticker
    # Check if the symbol exists
    if ticker in cg_coins["symbol"].values:
        # Check coin by symbol, i.e. "BTC"
        coin_dict, id = get_crypto_info(cg_coins[cg_coins["symbol"] == ticker]["id"])

    if coin_dict is None:
        # As a second options check the TradingView data
        if tv_data := await tv.get_tv_data(ticker, "crypto"):
            # Unpack the data
            price, perc_change, volume, exchange, website = tv_data
            return (
                volume,
                website + "/?coingecko",
                exchange,
                price,
                format_change(perc_change),
            )

        # Third option is to check by id
        elif ticker.lower() in cg_coins["id"].values:
            coin_dict, id = get_crypto_info(
                cg_coins[cg_coins["id"] == ticker.lower()]["id"]
            )

        # Fourth option is to check by name, i.e. "Bitcoin"
        elif ticker in cg_coins["name"].values:
            coin_dict, id = get_crypto_info(cg_coins[cg_coins["name"] == ticker]["id"])

    # Get the information from the dictionary
    total_vol, price, change, exchanges = get_info_from_dict(coin_dict)

    # Return the information
    return (
        total_vol,
        f"https://coingecko.com/en/coins/{id}",
        exchanges,
        price,
        format_change(change),
    )


async def get_stock_info(
    ticker: str,
) -> Optional[tuple[float, str, List[str], float, str]]:
    """
    Gets the volume, website, exchanges, price, and change of the stock.

    Parameters
    ----------
    ticker : str
        The ticker of the stock.

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
    """

    stock_info = yf.Ticker(ticker)

    try:
        if stock_info.info["regularMarketPrice"] != None:

            prices = []
            changes = []

            # Return prices corresponding to market hours
            if afterHours():
                # Use bid if premarket price is not available
                price = (
                    round(stock_info.info["preMarketPrice"], 2)
                    if stock_info.info["preMarketPrice"] != None
                    else stock_info.info["bid"]
                )
                change = round(
                    (price - stock_info.info["regularMarketPrice"])
                    / stock_info.info["regularMarketPrice"]
                    * 100,
                    2,
                )
                formatted_change = f"+{change}% 📈" if change > 0 else f"{change}% 📉"

                # Dont add if prices are 0
                if price != 0:
                    prices.append(price)
                    changes.append(formatted_change)

            # Could try 'currentPrice' as well
            price = round(stock_info.info["regularMarketPrice"], 2)
            change = round(
                (price - stock_info.info["regularMarketPreviousClose"])
                / stock_info.info["regularMarketPreviousClose"]
                * 100,
                2,
            )

            formatted_change = f"+{change}% 📈" if change > 0 else f"{change}% 📉"

            prices.append(price)
            changes.append(formatted_change)

            # Return the important information
            # Could also try 'volume' or 'volume24Hr' (is None if market is closed)
            volume = stock_info.info["regularMarketVolume"] * price

            return (
                volume,
                f"https://finance.yahoo.com/quote/{ticker}",
                stock_info.info["exchange"],
                prices,
                changes,
            )

    except Exception:
        pass

    # Check TradingView data
    if tv_data := await tv.get_tv_data(ticker, "stock"):
        price, perc_change, volume, exchange, website = tv_data
        return volume, website, exchange, price, format_change(perc_change)

    else:
        return None


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
