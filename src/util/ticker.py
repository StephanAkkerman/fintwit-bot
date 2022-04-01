##> Imports
# > 3rd Party Dependencies
import yfinance as yf

# Local dependencies
from util.tv_data import get_tv_data, get_tv_TA
from util.vars import stables, cg_coins, cg
from util.afterhours import afterHours

def get_coin_info(ticker):
    """Free CoinGecko API allows 50 calls per mintue"""
    
    # Remove formatting
    if ticker not in stables:
        for stable in stables:
            if ticker.endswith(stable):
                ticker = ticker[:-len(stable)]

    # Get the id of the ticker
    # Check if the symbol exists    
    if ticker in cg_coins["symbol"].values:
        ids = cg_coins[cg_coins["symbol"] == ticker]["id"]
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
        else:
            id = ids.values[0]
            coin_dict = cg.get_coin_by_id(id)
    elif tv_data := get_tv_data(ticker, 'crypto'):
        price, perc_change, volume, exchange = tv_data
        formatted_change = f"+{perc_change}% 📈" if perc_change > 0 else f"{perc_change}% 📉"
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
        else:
            id = ids.values[0]
            coin_dict = cg.get_coin_by_id(id)
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
        else:
            id = ids.values[0]
            coin_dict = cg.get_coin_by_id(id)
    else:
        return 0, None, None, None, None

    # Get the information of this coin
    try:
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
    
    try:
        if stock_info.info['regularMarketPrice'] != None:        
        
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
    if tv_data := get_tv_data(ticker, 'stock'):
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
        # If volume of the crypto is bigger than 1,000,000, it is likely a crypto
        # Stupid Tessla Coin https://www.coingecko.com/en/coins/tessla-coin
        if coin[0] > 1000000 or ticker.endswith('BTC'):
            ta = get_tv_TA(ticker, 'crypto')
            return *coin, ta
        stock = get_stock_info(ticker)
    else:
        stock = get_stock_info(ticker)
        if stock[0] > 1000000:
            ta = get_tv_TA(ticker, 'stock')
            return *stock, ta
        coin = get_coin_info(ticker)

    # First in tuple represents volume
    if coin[0] > stock[0] and coin[0] > 50000:
        ta = get_tv_TA(ticker, 'crypto')
        return *coin, ta
    elif coin[0] < stock[0]:
        ta = get_tv_TA(ticker, 'stock')
        return *stock, ta
    else:
        return None, None, None, None, None, None
