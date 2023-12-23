import traceback

import ccxt.async_support as ccxt
import pandas as pd
import numpy as np

from util.vars import stables


async def get_data(row) -> pd.DataFrame:
    exchange_info = {"apiKey": row["key"], "secret": row["secret"]}

    if row["exchange"] == "binance":
        exchange = ccxt.binance(exchange_info)
        exchange.options["recvWindow"] = 60000
    elif row["exchange"] == "kucoin":
        exchange_info["password"] = row["passphrase"]
        exchange = ccxt.kucoin(exchange_info)

    try:
        balances = await get_balance(exchange)

        if balances == "invalid API key":
            await exchange.close()
            return "invalid API key"

        # Create a list of dictionaries
        owned = []

        for symbol, amount in balances.items():
            usd_val, percentage = await get_usd_price(exchange, symbol)
            worth = amount * usd_val

            # Add price change

            if worth < 5:
                continue

            buying_price = await get_buying_price(exchange, symbol)

            # If buying price is 0 then it is not known what the price was
            owned.append(
                {
                    "asset": symbol,
                    "buying_price": buying_price,
                    "owned": amount,
                    "exchange": exchange.id,
                    "id": row["id"],
                    "user": row["user"],
                    "worth": round(worth, 2),
                    "price": usd_val,
                    "change": percentage,
                }
            )

        df = pd.DataFrame(owned)

        # Se tthe types
        if not df.empty:
            df = df.astype(
                {
                    "asset": str,
                    "buying_price": float,
                    "owned": float,
                    "exchange": str,
                    "id": np.int64,
                    "user": str,
                    "worth": float,
                    "price": float,
                    "change": float,
                }
            )

        await exchange.close()
        return df
    except Exception as e:
        await exchange.close()
        print("Error in get_data(). Error:", e)
        print(traceback.format_exc())


async def get_balance(exchange) -> dict:
    try:
        balances = await exchange.fetchBalance()
        total_balance = balances["total"]
        if total_balance is None:
            return "invalid API key"
        return {k: v for k, v in total_balance.items() if v > 0}
    except Exception:
        return {}


async def get_usd_price(exchange, symbol: str) -> tuple[float, float]:
    """
    Returns the price of the symbol in USD
    Symbol must be in the format 'BTC/USDT'
    """
    exchange_price = 0
    exchange_change = 0

    if symbol not in stables:
        for usd in stables:
            try:
                price = await exchange.fetchTicker(f"{symbol}/{usd}")
                if price != 0:
                    if "last" in price:
                        exchange_price = float(price["last"])
                    if "percentage" in price:
                        exchange_change = float(price["percentage"])
            except ccxt.BadSymbol:
                continue
            except ccxt.ExchangeError as e:
                print(f"Exchange error for {symbol} on {exchange.id}")
                print(e)
                continue
    else:
        try:
            price = await exchange.fetchTicker(symbol + "/DAI")
            if "last" in price:
                exchange_price = float(price["last"])
            if "percentage" in price:
                exchange_change = float(price["percentage"])
        except ccxt.BadSymbol:
            return 1, 0

    return exchange_price, exchange_change


async def get_buying_price(exchange, symbol, full_sym: bool = False) -> float:
    # Maybe try different quote currencies when returned list is empty
    if symbol in stables:
        return 1

    symbol = symbol + "/USDT" if not full_sym else symbol

    params = {}
    if exchange.id == "kucoin":
        params = {"side": "buy"}
    try:
        trades = await exchange.fetchClosedOrders(symbol, params=params)
    except ccxt.BadSymbol:
        return 0
    except ccxt.RequestTimeout:
        return 0
    if type(trades) == list:
        if len(trades) > 0:
            if exchange.id == "binance":
                # Filter list for side:buy
                trades = [trade for trade in trades if trade["info"]["side"] == "BUY"]
                if len(trades) == 0:
                    return 0

            return float(trades[-1]["price"])

    return 0
