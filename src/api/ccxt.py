from __future__ import annotations

import datetime
import time

import ccxt
import pandas as pd
from dateutil.parser import parse

# Save the exchanges that are useful
exchanges_with_ohlcv = []

for exchange_id in ccxt.exchanges:
    exchange = getattr(ccxt, exchange_id)()
    if exchange.has["fetchOHLCV"]:
        exchanges_with_ohlcv.append(exchange_id)


def fetch_data(
    exchange: str = "binance",
    since=None,
    limit: int = None,
) -> pd.DataFrame:
    """
    Pandas DataFrame with the latest OHLCV data from specified exchange.

    Parameters
    --------------
    exchange : string, check the exchange_list to see the supported exchanges. For instance "binance".
    since: integer, UTC timestamp in milliseconds. Default is None, which means will not take the start date into account.
    The behavior of this parameter depends on the exchange.
    limit : integer, the amount of rows that should be returned. For instance 100, default is None, which means 500 rows.

    All the timeframe options are: '1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M'
    """

    timeframe: str = "1d"
    symbol: str = "BTC/USDT"

    # If it is a string, convert it to a datetime object
    if isinstance(since, str):
        since = parse(since)

    if isinstance(since, datetime.datetime):
        since = int(since.timestamp() * 1000)

    # Always convert to lowercase
    exchange = exchange.lower()

    if exchange not in exchanges_with_ohlcv:
        raise ValueError(
            f"{exchange} is not a supported exchange. Please use one of the following: {exchanges_with_ohlcv}"
        )

    exchange = getattr(ccxt, exchange)()

    # Convert ms to seconds, so we can use time.sleep() for multiple calls
    rate_limit = exchange.rateLimit / 1000

    # Get data
    data = exchange.fetch_ohlcv(symbol, timeframe, since, limit)

    while len(data) < limit:
        # If the data is less than the limit, we need to make multiple calls
        # Shift the since date to the last date of the data
        since = data[-1][0] + 86400000

        # Sleep to prevent rate limit errors
        time.sleep(rate_limit)

        # Get the remaining data
        new_data = exchange.fetch_ohlcv(symbol, timeframe, since, limit - len(data))
        data += new_data

        if len(new_data) == 0:
            break

    df = pd.DataFrame(
        data, columns=["Timestamp", "open", "high", "low", "close", "volume"]
    )

    # Convert Timestamp to date
    df.Timestamp = (
        df.Timestamp / 1000
    )  # Timestamp is 1000 times bigger than it should be in this case
    df["Date"] = pd.to_datetime(df.Timestamp, unit="s")

    # The default values are string, so convert these to numeric values
    df["Value"] = pd.to_numeric(df["close"])

    # Returned DataFrame should consists of columns: index starting from 0, date as datetime, open, high, low, close, volume in numbers
    return df[["Date", "Value"]]
