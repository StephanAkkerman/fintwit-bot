import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
from util.vars import stables

async def get_data(row) -> pd.DataFrame:
    
    exchange_info = {'apiKey': row["key"], 'secret': row["secret"]}
    
    if row['exchange'] == 'binance':
        exchange = ccxt.binance(exchange_info)
        exchange.options['recvWindow'] = 60000
    elif row['exchange'] == 'kucoin':
        exchange_info['password'] = row['passphrase']
        exchange = ccxt.kucoin(exchange_info)
        
    try:
        balances = await get_balance(exchange)
        
        # Create a list of dictionaries
        owned = []

        for symbol, amount in balances.items():
            usd_val = await get_usd_price(exchange, symbol)
            worth = amount * usd_val
        
            if worth < 5:
                continue
            
            buying_price = await get_buying_price(exchange, symbol)
            
            if buying_price != 0:
                owned.append({
                    "asset": symbol,
                    "buying_price" : buying_price,
                    "owned": amount,
                    "exchange": exchange.id,
                    "id": row["id"],
                    "user": row["user"],
                })
    
        df = pd.DataFrame(owned)
        
        if not df.empty:
            df = df.astype({"asset": str, "buying_price": float, "owned": float, "exchange": str, "id": np.int64, "user": str})
            
        await exchange.close()
        return df
    except Exception as e:
        await exchange.close()
        print("Error in get_data(). Error:", e)

async def get_balance(exchange) -> dict:
    try:
        balances = await exchange.fetchBalance()
        return {k: v for k, v in balances['total'].items() if v > 0}
    except ccxt.RequestTimeout:
        return {}

async def get_usd_price(exchange, symbol) -> float:
    """
    Returns the price of the symbol in USD
    Symbol must be in the format 'BTC/USDT'
    """    
    if symbol not in stables:
        for usd in stables:
            try:
                price = await exchange.fetchTicker(f"{symbol}/{usd}")
                if price != 0:
                    return float(price['last'])
            except ccxt.BadSymbol:
                continue
            except ccxt.ExchangeError as e:
                print(f"Exchange error for {symbol} on {exchange.id}")
                print(e)
                continue
    else:
        try:
            price = await exchange.fetchTicker(symbol + '/DAI')
            return float(price['last'])
        except ccxt.BadSymbol:
            return 1
    
    return 0

async def get_buying_price(exchange, symbol, full_sym : bool = False) -> float:
    # Maybe try different quote currencies when returned list is empty
    if symbol in stables:
        return 1
    
    symbol = symbol + '/USDT' if not full_sym else symbol
    
    params = {}
    if exchange.id == 'kucoin':
        params = {"side" : 'buy'}    
    try:
        trades = await exchange.fetchClosedOrders(symbol, params = params)
    except ccxt.BadSymbol:
        return 0
    except ccxt.RequestTimeout:
        return 0
    if type(trades) == list:
        if len(trades) > 1:
            if exchange.id == 'binance':
                # Filter list for side:buy
                trades = [trade for trade in trades if trade['info']['side'] == 'BUY']
                if len(trades) == 0:
                    return 0
                
            return float(trades[-1]['price'])
        
    return 0