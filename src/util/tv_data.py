import requests
import json
import random
import string
import re
import requests
import traceback

# > 3rd party dependencies
from websocket import create_connection
import pandas as pd

# Get the current symbols and exchanges on TradingView
tv_stocks = requests.get("https://scanner.tradingview.com/america/scan").json()["data"]
tv_crypto = requests.get("https://scanner.tradingview.com/crypto/scan").json()["data"]

tv_stocks = pd.DataFrame(tv_stocks).drop(columns=["d"])
tv_stocks[["exchange", "stock"]] = tv_stocks["s"].str.split(":", 1, expand=True)

tv_crypto = pd.DataFrame(tv_crypto).drop(columns=["d"])
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
                    # symbol = jsonRes['p'][1]['n']
                    price = jsonRes["p"][1]["v"]["lp"]
                    change = jsonRes["p"][1]["v"]["ch"]
                    perc_change = round((change / price) * 100,2)
                    volume = jsonRes['p'][1]['v']['volume']
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


def get_tv_data(symbol, asset):
    """
    Returns the current price and percent change of a stock based on TradingView websocket data
    @param symbol: string (ex: 'AAPL', 'BTCUSDT')
    @param asset: string (ex: 'stock', 'crypto')
    @return: tuple (price, perc_change, volume, exchange)
    """

    try:
        stock = tv_stocks.loc[tv_stocks["stock"] == symbol]
        crypto = tv_crypto.loc[tv_crypto["stock"] == symbol]

        if not stock.empty and asset == 'stock':
            exchange = stock["exchange"].values[0]
            symbol = f"{exchange}:{stock['stock'].values[0]}"
        elif not crypto.empty and asset == 'crypto':
            exchange = stock["exchange"].values[0]
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

        return ws_resp[0], ws_resp[1], ws_resp[2], exchange

    except Exception:
        print(traceback.format_exc())
