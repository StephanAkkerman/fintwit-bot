##> Imports
# Standard libraries
import datetime

# > 3rd Party Dependencies
import yfinance as yf
import pandas as pd
from pycoingecko import CoinGeckoAPI
from pandas.tseries.holiday import USFederalHolidayCalendar

# Local dependencies
from util.tv_data import get_tv_data

# Get the public holidays
cal = USFederalHolidayCalendar()
us_holidays = cal.holidays(
    start=datetime.date(datetime.date.today().year, 1, 1).strftime("%Y-%m-%d"),
    end=datetime.date(datetime.date.today().year, 12, 31).strftime("%Y-%m-%d"),
).to_pydatetime()


def afterHours():
    """
    Simple code to check if the current time is after hours in the US.
    return: True if after hours, False otherwise

    source: https://www.reddit.com/r/algotrading/comments/9x9xho/python_code_to_check_if_market_is_open_in_your/
    """

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5), "EST"))
    openTime = datetime.time(hour=9, minute=30, second=0)
    closeTime = datetime.time(hour=16, minute=0, second=0)

    # If a holiday
    if now.strftime("%Y-%m-%d") in us_holidays:
        return True

    # If before 0930 or after 1600
    if (now.time() < openTime) or (now.time() > closeTime):
        return True

    # If it's a weekend
    if now.date().weekday() > 4:
        return True

    # Otherwise the market is open
    return False


# Create CoinGecko object
cg = CoinGeckoAPI()

# Get all crypto tickers and change them to all caps
# Maybe refresh this df daily
df = pd.DataFrame(cg.get_coins_list())

# Make everything upper since ticker is always all caps
df["symbol"] = df["symbol"].str.upper()


def get_coin_info(ticker):
    """Free CoinGecko API allows 50 calls per mintue"""

    # Get the id of the ticker
    # Check if the symbol exists
    if ticker in df["symbol"].values:
        ids = df[df["symbol"] == ticker]["id"]
        if len(ids) > 1:
            id = None
            best_vol = 0
            for symbol in ids.values:
                coin_info = cg.get_coin_by_id(symbol)
                if "usd" in coin_info["market_data"]["total_volume"]:
                    volume = coin_info["market_data"]["total_volume"]["usd"]
                    if volume > best_vol:
                        best_vol = volume
                        id = symbol
        else:
            id = ids.values[0]
    elif tv_data := get_tv_data(ticker, 'crypto'):
        price, perc_change, volume, exchange = tv_data
        formatted_change = f"+{perc_change}% 📈" if perc_change > 0 else f"{perc_change}% 📉"
        website = f"https://www.tradingview.com/symbols/{ticker}-{exchange}/?coingecko"
        return volume, website, exchange, price, perc_change            
    elif ticker.lower() in df["id"].values:
        ids = df[df["id"] == ticker.lower()]["id"]
        if len(ids) > 1:
            id = None
            best_vol = 0
            for symbol in ids.values:
                coin_info = cg.get_coin_by_id(symbol)
                if "usd" in coin_info["market_data"]["total_volume"]:
                    volume = coin_info["market_data"]["total_volume"]["usd"]
                    if volume > best_vol:
                        best_vol = volume
                        id = symbol
        else:
            id = ids.values[0]
    elif ticker in df["name"].values:
        ids = df[df["name"] == ticker]["id"]
        if len(ids) > 1:
            id = None
            best_vol = 0
            for symbol in ids.values:
                coin_info = cg.get_coin_by_id(symbol)
                if "usd" in coin_info["market_data"]["total_volume"]:
                    volume = coin_info["market_data"]["total_volume"]["usd"]
                    if volume > best_vol:
                        best_vol = volume
                        id = symbol
        else:
            id = ids.values[0]
    else:
        return 0, None, None, None, None

    # Get the information of this coin
    try:
        coin_dict = cg.get_coin_by_id(id)
        total_vol = coin_dict["market_data"]["total_volume"]["usd"]
        website = f"https://coingecko.com/en/coins/{id}"
        price = coin_dict["market_data"]["current_price"]["usd"]

        price_change = coin_dict["market_data"]["price_change_percentage_24h"]

        if price_change != None:
            change = round(price_change, 2)
        else:
            return 0, None, None, None, None

        formatted_change = f"+{change}% 📈" if change > 0 else f"{change}% 📉"

        # Get the exchanges
        exchanges = [exchange["market"]["name"] for exchange in coin_dict["tickers"]]
    except Exception as e:
        print(e)
        print("CoinGecko API error:", ticker)
        return 0, None, None, None, None

    # Get the exchanges
    exchanges = [exchange["market"]["name"] for exchange in coin_dict["tickers"]]

    # Return the information
    return total_vol, website, exchanges, price, formatted_change


def get_stock_info(ticker):

    stock_info = yf.Ticker(ticker)
    
    if stock_info.info['regularMarketPrice'] != None:        
        try:
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
            return volume, f"https://finance.yahoo.com/quote/{ticker}", stock_info.info["exchange"], prices, changes

        except Exception as e:
            pass
        
    # Check TradingView data
    elif tv_data := get_tv_data(ticker, 'stock'):
        price, perc_change, volume, exchange = tv_data
        formatted_change = f"+{perc_change}% 📈" if perc_change > 0 else f"{perc_change}% 📉"
        website = f"https://www.tradingview.com/symbols/{ticker}-{exchange}/?yahoo"
        return volume, website, exchange, price, perc_change    

    else:
        return 0, None, None, None, None

def classify_ticker(ticker, majority):
    """Main function to classify the ticker as crypto or stock
    Returns 24h volume, website, and exchanges
    """

    if majority == 'crypto' or majority == '🤷‍♂️':
        coin = get_coin_info(ticker)
        # If volume of the crypto is bigger than half a million, it is likely a crypto
        if coin[0] > 500000:
            return coin
        stock = get_stock_info(ticker)
    else:
        stock = get_stock_info(ticker)
        if stock[0] > 500000:
            return stock
        coin = get_coin_info(ticker)

    # First in tuple represents volume
    if coin[0] > stock[0]:
        return coin
    elif coin[0] < stock[0]:
        return stock
    else:
        return None, None, None, None, None
