import requests
import json
import random
import string
import re
import requests
import traceback

# > 3rd party dependencies
from websocket import create_connection
from tradingview_ta import TA_Handler, Interval
import pandas as pd

# Get the current symbols and exchanges on TradingView
tv_stocks = requests.get("https://scanner.tradingview.com/america/scan").json()["data"]
tv_crypto = requests.get("https://scanner.tradingview.com/crypto/scan").json()["data"]

stock_indices = [
    "AMEX:SPY",
    "NASDAQ:NDX",
    "USI:PCC",
    "USI:PCCE",
    "TVC:DXY",
    "TVC:US10Y",
    "TVC:VIX",
]

tv_stocks = pd.DataFrame(tv_stocks).drop(columns=["d"])
tv_stocks = pd.concat([tv_stocks, pd.DataFrame(stock_indices, columns=["s"])])
tv_stocks[["exchange", "stock"]] = tv_stocks["s"].str.split(":", 1, expand=True)

# Get all EXCHANGE:INDEX symbols
crypto_indices = [
    "CRYPTOCAP:TOTAL",
    "CRYPTOCAP:BTC.D",
    "CRYPTOCAP:OTHERS.D",
    "CRYPTOCAP:TOTALDEFI.D",
    "CRYPTOCAP:USDT.D",
]

tv_crypto = pd.DataFrame(tv_crypto).drop(columns=["d"])
tv_crypto = pd.concat([tv_crypto, pd.DataFrame(crypto_indices, columns=["s"])])
tv_crypto[["exchange", "stock"]] = tv_crypto["s"].str.split(":", 1, expand=True)
# Based on https://github.com/mohamadkhalaj/tradingView-API websocket implementation


def generateSession():
    stringLength = 12
    letters = string.ascii_lowercase
    random_string = "".join(random.choice(letters) for i in range(stringLength))
    return "qs_" + random_string


def prependHeader(st):
    return "~m~" + str(len(st)) + "~m~" + st


def constructMessage(func, paramList):
    return json.dumps({"m": func, "p": paramList}, separators=(",", ":"))


def createMessage(func, paramList):
    return prependHeader(constructMessage(func, paramList))


def sendMessage(ws, func, args):
    ws.send(createMessage(func, args))


def ws_data(ws):
    try:
        # Get the response
        result = ws.recv()
        # Try again
        if '"m":' not in result:
            return None
        elif Res := re.findall("^.*?({.*)$", result):
            jsonRes = json.loads(Res[0].split("~m~")[0])
            if "m" in jsonRes.keys():
                if jsonRes["m"] == "qsd":
                    try:
                        price = jsonRes["p"][1]["v"]["lp"]
                        change = jsonRes["p"][1]["v"]["ch"]
                        volume = jsonRes["p"][1]["v"]["volume"]
                    except KeyError:
                        print("KeyError in TradingView ws_data")
                        return None

                    perc_change = round((change / price) * 100, 2)

                    return price, perc_change, volume
        else:
            # ping packet
            pingStr = re.findall(".......(.*)", result)
            if len(pingStr) != 0:
                pingStr = pingStr[0]
                ws.send("~m~" + str(len(pingStr)) + "~m~" + pingStr)

            return None
    except Exception:
        print(traceback.format_exc())


def get_tv_TA(symbol, asset):

    if asset == "stock":
        stock = tv_stocks.loc[tv_stocks["stock"] == symbol]
        if not stock.empty:
            exchange = stock["exchange"].values[0]
            market = "america"
        else:
            return None
    else:
        crypto = tv_crypto.loc[tv_crypto["stock"] == symbol]
        if not crypto.empty:
            exchange = crypto["exchange"].values[0]
            market = "crypto"
        else:
            # If it crypto try adding USD or USDT
            crypto_USD = tv_crypto.loc[tv_crypto["stock"] == symbol + "USD"]
            crypto_USDT = tv_crypto.loc[tv_crypto["stock"] == symbol + "USDT"]

            if not crypto_USD.empty:
                symbol = crypto_USD["stock"].values[0]
                exchange = crypto_USD["exchange"].values[0]
                market = "crypto"
            elif not crypto_USDT.empty:
                symbol = crypto_USDT["stock"].values[0]
                exchange = crypto_USDT["exchange"].values[0]
                market = "crypto"
            else:
                return None

    # Get the TradingView TA for symbol
    # Interval can be 1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1W, 1M
    try:
        # Wait max 5 sec
        analysis = (
            TA_Handler(
                symbol=symbol,
                screener=market,
                exchange=exchange,
                interval=Interval.INTERVAL_4_HOURS,
                timeout=5,
            )
            .get_analysis()
            .summary
        )
    except Exception as e:
        print(f"Error getting TradingView TA for {symbol}")
        print(e)
        return None

    # Format the analysis
    formatted_analysis = f"{analysis['RECOMMENDATION']}\n{analysis['BUY']}📈 {analysis['NEUTRAL']}⌛️ {analysis['SELL']}📉"

    return formatted_analysis


def get_tv_data(symbol, asset):
    """
    Returns the current price and percent change of a stock based on TradingView websocket data
    @param symbol: string (ex: 'AAPL', 'BTCUSDT')
    @param asset: string (ex: 'stock', 'crypto')
    @return: tuple (price, perc_change, volume, exchange)
    """

    try:
        if asset == "stock":
            stock = tv_stocks.loc[tv_stocks["stock"] == symbol]
            if not stock.empty:
                exchange = stock["exchange"].values[0]
                symbol = f"{exchange}:{stock['stock'].values[0]}"
            else:
                return False
        else:
            crypto = tv_crypto.loc[tv_crypto["stock"] == symbol]
            if not crypto.empty:
                exchange = crypto["exchange"].values[0]
                symbol = f"{exchange}:{crypto['stock'].values[0]}"
            else:
                return False

        # create tunnel
        ws = create_connection(
            "wss://data.tradingview.com/socket.io/websocket",
            headers={"Origin": "https://data.tradingview.com"},
        )
        session = generateSession()

        sendMessage(ws, "quote_create_session", [session])
        sendMessage(ws, "quote_set_fields", [session, "ch", "lp", "volume"])
        sendMessage(ws, "quote_add_symbols", [session, symbol])

        # Keep trying untill we get a useful response
        counter = 0
        while True:
            ws_resp = ws_data(ws)
            counter += 1

            if ws_resp != None:
                break

            # Quit after 3 tries
            elif counter == 3:
                return False

        # Close the websocket connection
        ws.close()

        # Returns the price, percent change, volume and exchange
        return ws_resp[0], ws_resp[1], ws_resp[2], exchange

    except Exception:
        print(traceback.format_exc())
