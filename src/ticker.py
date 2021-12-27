##> Imports

# Standard libraries
import datetime

# > 3rd Party Dependencies
import yfinance as yf
import pandas as pd
from pycoingecko import CoinGeckoAPI
from pandas.tseries.holiday import USFederalHolidayCalendar

# Get the public holidays
cal = USFederalHolidayCalendar()
us_holidays = cal.holidays(start=datetime.date(datetime.date.today().year, 1, 1).strftime('%Y-%m-%d'),
                           end=datetime.date(datetime.date.today().year, 12, 31).strftime('%Y-%m-%d')).to_pydatetime()

def afterHours():
    """
    Simple code to check if the current time is after hours in the US.
    return: True if after hours, False otherwise
    
    source: https://www.reddit.com/r/algotrading/comments/9x9xho/python_code_to_check_if_market_is_open_in_your/
    """
    
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5), 'EST'))
    openTime = datetime.time(hour = 9, minute = 30, second = 0)
    closeTime = datetime.time(hour = 16, minute = 0, second = 0)
    
    # If a holiday
    if now.strftime('%Y-%m-%d') in us_holidays:
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
df['symbol'] = df['symbol'].str.upper()

def get_coin_info(ticker):
    """ Free CoinGecko API allows 50 calls per mintue """
    
    # Get the id of the ticker
    try:
        id = df.loc[df['symbol'] == ticker]['id'].values[0]
    except Exception:
        return 0, None
    
    # Get the information of this coin
    coin_dict = cg.get_coin_by_id(id)
    total_vol = coin_dict['market_data']['total_volume']['usd']
    website = f"coingecko.com/en/coins/{id}"
    price = coin_dict['market_data']['current_price']['usd']
    price_change = round(coin_dict['market_data']['price_change_percentage_24h'], 2)

    # Get the exchanges
    exchanges = [exchange['market']['name'] for exchange in coin_dict['tickers']]
    
    # Return the information
    return total_vol, website, exchanges, price, price_change


def get_stock_info(ticker):
    
    info = yf.Ticker(ticker)
    website = f"https://finance.yahoo.com/quote/{ticker}"
    try:
        # Return prices corresponding to market hours
        if afterHours():
            price = info.info['preMarketPrice']
            change = round((info.info['preMarketPrice'] - info.info['regularMarketPrice']) / info.info['regularMarketPrice'] * 100, 2)
        else:
            price = info.info['regularMarketPrice']
            change = round((info.info['regularMarketPrice'] - info.info['regularMarketPreviousClose']) / info.info['regularMarketPreviousClose'] * 100, 2)
        
        # Return the important information
        return info.info['volume'], website, info.info['exchange'], price, change
    
    except Exception:
        return 0, None, None, None, None
    
def classify_ticker(ticker):
    """ Main function to classify the ticker as crypto or stock
    Returns 24h volume, website, and exchanges
    """
    
    coin = get_coin_info(ticker)
    stock = get_stock_info(ticker)
    
    # First in tuple represents volume
    if coin[0] > stock[0]:
        return coin
    else:
        return stock