##> Imports
# > Standard libaries
from __future__ import annotations
import traceback
from typing import Optional, List

# > 3rd Party Dependencies
import yfinance as yf

# Local dependencies
from util.tv_data import TV_data
from util.vars import stables, cg_coins, cg
from util.afterhours import afterHours

tv = TV_data()


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

    # Remove formatting
    if ticker not in stables:
        for stable in stables:
            if ticker.endswith(stable):
                ticker = ticker[: -len(stable)]

    # Get the id of the ticker
    # Check if the symbol exists
    if ticker in cg_coins["symbol"].values:
        ids = cg_coins[cg_coins["symbol"] == ticker]["id"]
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
                except Exception as e:
                    pass

        elif len(ids) == 1:
            id = ids.values[0]
            # Try in case the CoinGecko API does not work
            try:
                coin_dict = cg.get_coin_by_id(id)
            except Exception:
                return

        else:
            return

    # As a second options check the TradingView data
    elif tv_data := await tv.get_tv_data(ticker, "crypto"):
        price, perc_change, volume, exchange = tv_data
        formatted_change = (
            f"+{perc_change}% 📈" if perc_change > 0 else f"{perc_change}% 📉"
        )
        website = f"https://www.tradingview.com/symbols/{ticker}-{exchange}/?coingecko"
        return volume, website, exchange, price, formatted_change

    elif ticker.lower() in cg_coins["id"].values:
        ids = cg_coins[cg_coins["id"] == ticker.lower()]["id"]
        if len(ids) > 1:
            id = None
            best_vol = 0
            coin_dict = None
            for symbol in ids.values:
                coin_info = cg.get_coin_by_id(symbol)
                if "usd" in coin_info["market_data"]["total_volume"]:
                    volume = coin_info["market_data"]["total_volume"]["usd"]
                    if volume > best_vol:
                        best_vol = volume
                        id = symbol
                        coin_dict = coin_info

        elif len(ids) == 1:
            id = ids.values[0]
            try:
                coin_dict = cg.get_coin_by_id(id)
            except Exception:
                return

        else:
            return

    elif ticker in cg_coins["name"].values:
        ids = cg_coins[cg_coins["name"] == ticker]["id"]
        if len(ids) > 1:
            id = None
            best_vol = 0
            coin_dict = None
            for symbol in ids.values:
                coin_info = cg.get_coin_by_id(symbol)
                if "usd" in coin_info["market_data"]["total_volume"]:
                    volume = coin_info["market_data"]["total_volume"]["usd"]
                    if volume > best_vol:
                        best_vol = volume
                        id = symbol
                        coin_dict = coin_info

        elif len(ids) == 1:
            id = ids.values[0]
            try:
                coin_dict = cg.get_coin_by_id(id)
            except Exception:
                return

        else:
            return

    else:
        return

    # Get the information of this coin
    try:
        website = f"https://coingecko.com/en/coins/{id}"

        # For tokens that are previewed but not yet live
        if coin_dict["market_data"] is None:
            print(f"Could not get coingecko info for {ticker}")
            return

        if "usd" in coin_dict["market_data"]["total_volume"].keys():
            total_vol = coin_dict["market_data"]["total_volume"]["usd"]
        else:
            return 1, website, [], 0, "Preview Only"

        price = coin_dict["market_data"]["current_price"]["usd"]
        price_change = coin_dict["market_data"]["price_change_percentage_24h"]

        if price_change != None:
            change = round(price_change, 2)
        else:
            return total_vol, website, [], price, "?"

        formatted_change = f"+{change}% 📈" if change > 0 else f"{change}% 📉"

        # Get the exchanges
        exchanges = [exchange["market"]["name"] for exchange in coin_dict["tickers"]]
    except Exception as e:
        print(traceback.format_exc())
        print(f"CoinGecko API error for {ticker}. Error:", e)
        return None

    # Get the exchanges
    exchanges = [exchange["market"]["name"] for exchange in coin_dict["tickers"]]

    # Return the information
    return total_vol, website, exchanges, price, formatted_change


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
        price, perc_change, volume, exchange = tv_data
        formatted_change = (
            f"+{perc_change}% 📈" if perc_change > 0 else f"{perc_change}% 📉"
        )
        website = f"https://www.tradingview.com/symbols/{ticker}-{exchange}"
        return volume, website, exchange, price, formatted_change

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
                ta = tv.get_tv_TA(ticker, "crypto")
                return *coin, ta
        stock = await get_stock_info(ticker)
    else:
        stock = await get_stock_info(ticker)
        if stock is not None:
            if stock[0] > 1000000:
                ta = tv.get_tv_TA(ticker, "stock")
                return *stock, ta
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
        ta = tv.get_tv_TA(ticker, "crypto")
        return *coin, ta
    elif coin_vol < stock_vol:
        ta = tv.get_tv_TA(ticker, "stock")
        return *stock, ta
    else:
        return None
