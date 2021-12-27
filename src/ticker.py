from pycoingecko import CoinGeckoAPI
import yfinance as yf
import pandas as pd

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
    except IndexError:
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
        change = round((info.info['regularMarketPrice'] - info.info['regularMarketPreviousClose']) / info.info['regularMarketPreviousClose'] * 100, 2)
        premarket_change = round((info.info['preMarketPrice'] - info.info['regularMarketPrice']) / info.info['regularMarketPrice'] * 100, 2)
        
        return info.info['volume'], website, info.info['exchange'], info.info['regularMarketPrice'], info.info['preMarketPrice'], change, premarket_change
    except KeyError:
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