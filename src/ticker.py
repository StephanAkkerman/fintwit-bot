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
    
    # Get the exchanges
    exchanges = [exchange['market']['name'] for exchange in coin_dict['tickers']]
    
    return total_vol, website, exchanges


def get_stock_info(ticker):
    
    info = yf.Ticker(ticker)
    website = f"https://finance.yahoo.com/quote/{ticker}"
    try:
        return info.info['volume'], website, info.info['exchange']
    except KeyError:
        return 0, None, None
    
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