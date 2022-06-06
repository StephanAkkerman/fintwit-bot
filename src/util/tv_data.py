## > Imports
# > Standard libaries
from __future__ import annotations
import re
import json
import random
import string
import requests
import traceback
from typing import Optional, List

# > 3rd party dependencies
import aiohttp
import pandas as pd
from tradingview_ta import TA_Handler, Interval


class TV_data:
    """
    This class is used to get the current price, 24h change, and volume of a stock.
    It also includes methods to get the TradingView TA data.

    Methods
    -------
    on_msg(ws: aiohttp.ClientWebSocketResponse, msg) -> Optional[tuple[float, float, float]]:
        Parses the message from the TradingView API.
    sendMessage(ws: aiohttp.ClientWebSocketResponse, func: str, args: List[str]) -> None:
        Sends a message to the TradingView API.
    get_symbol_data(symbol: str, asset: str) -> Optional[tuple[str, str]]:
        Helper function to get the symbol data from the TradingView API.

    get_tv_TA(symbol: str, asset: str) -> Optional[str]:
        Gets the current TA (technical analysis) data from the TradingView API.
    """

    def __init__(self) -> None:
        # Get the current symbols and exchanges on TradingView
        tv_stocks = requests.get("https://scanner.tradingview.com/america/scan").json()[
            "data"
        ]
        tv_crypto = requests.get("https://scanner.tradingview.com/crypto/scan").json()[
            "data"
        ]

        self.stock_indices = [
            "AMEX:SPY",
            "NASDAQ:NDX",
            "USI:PCC",
            "USI:PCCE",
            "TVC:DXY",
            "TVC:US10Y",
            "TVC:VIX",
            "TVC:SPX",
        ]

        self.stock_indices_without_exch = [
            sym.split(":")[1] for sym in self.stock_indices
        ]

        tv_stocks = pd.DataFrame(tv_stocks).drop(columns=["d"])
        self.tv_stocks = pd.concat(
            [tv_stocks, pd.DataFrame(self.stock_indices, columns=["s"])]
        )
        self.tv_stocks[["exchange", "stock"]] = self.tv_stocks["s"].str.split(
            ":", 1, expand=True
        )

        # Get all EXCHANGE:INDEX symbols
        crypto_indices = [
            "CRYPTOCAP:TOTAL",
            "CRYPTOCAP:BTC.D",
            "CRYPTOCAP:OTHERS.D",
            "CRYPTOCAP:TOTALDEFI.D",
            "CRYPTOCAP:USDT.D",
        ]

        tv_crypto = pd.DataFrame(tv_crypto).drop(columns=["d"])
        self.tv_crypto = pd.concat(
            [tv_crypto, pd.DataFrame(crypto_indices, columns=["s"])]
        )
        self.tv_crypto[["exchange", "stock"]] = self.tv_crypto["s"].str.split(
            ":", 1, expand=True
        )

    async def on_msg(
        self, ws: aiohttp.ClientWebSocketResponse, msg
    ) -> Optional[tuple[float, float, float]]:
        """
        Parses the message from the TradingView API.

        Returns
        -------
        Optional[tuple[float, float, float, str]]
            float
                The current price.
            float
                The current 24h change.
            float
                The current volume.
        """

        try:
            # Try again
            if '"m":' not in msg:
                return None
            elif Res := re.findall("^.*?({.*)$", msg):
                jsonRes = json.loads(Res[0].split("~m~")[0])
                if "m" in jsonRes.keys():
                    if jsonRes["m"] == "qsd":
                        try:
                            price = float(jsonRes["p"][1]["v"]["lp"])
                            change = float(jsonRes["p"][1]["v"]["ch"])
                            volume = float(jsonRes["p"][1]["v"]["volume"])
                        except KeyError:
                            print("KeyError in TradingView ws_data")
                            return None

                        if price != 0:
                            perc_change = round((change / price) * 100, 2)
                        else:
                            print("TradingView returns price=0")
                            return None

                        return price, perc_change, volume
            else:
                # ping packet
                pingStr = re.findall(".......(.*)", msg)
                if len(pingStr) != 0:
                    pingStr = pingStr[0]
                    ws.send_str("~m~" + str(len(pingStr)) + "~m~" + pingStr)

                return None
        except Exception:
            print(traceback.format_exc())

    async def sendMessage(
        self, ws: aiohttp.ClientWebSocketResponse, func: str, args: List[str]
    ) -> None:
        """
        Sends a message to the TradingView API.
        This needs to be done before any data can be retrieved.

        Parameters
        ----------
        ws : aiohttp.ClientWebSocketResponse
            The websocket object to send the message from.
        func : str
            The function to call, all start with "quote_" followed by the function name.
        args : List[str]
            The list of arguments to send in the message.
        """

        as_json = json.dumps({"m": func, "p": args}, separators=(",", ":"))
        prepended = "~m~" + str(len(as_json)) + "~m~" + as_json
        await ws.send_str(prepended)

    def get_symbol_data(
        self, symbol: str, asset: str
    ) -> Optional[tuple[str, str, str]]:
        """
        Helper function to get the symbol data from the TradingView API.
        This data included the exchange and market this symbol is traded on.

        Parameters
        ----------
        symbol : str
            The ticker of the stock / crypto.
        asset : str
            The type of asset, either "stock" or "crypto".

        Returns
        -------
        Optional[tuple[str, str, str]]
            str
                The exchange the symbol is traded on.
            str
                The market the symbol is traded on.
            str
                The symbol itself.
        """

        if asset == "stock":
            stock = self.tv_stocks.loc[self.tv_stocks["stock"] == symbol]
            if not stock.empty:
                return stock["exchange"].values[0], "america", symbol
        else:
            crypto = self.tv_crypto.loc[self.tv_crypto["stock"] == symbol]
            if not crypto.empty:
                return crypto["exchange"].values[0], "crypto", symbol
            else:
                if not symbol.endswith("USD") or not symbol.endswith("USDT"):

                    # If it crypto try adding USD or USDT
                    crypto_USD = self.tv_crypto.loc[
                        self.tv_crypto["stock"] == symbol + "USD"
                    ]
                    crypto_USDT = self.tv_crypto.loc[
                        self.tv_crypto["stock"] == symbol + "USDT"
                    ]

                    if not crypto_USD.empty:
                        return (
                            crypto_USD["exchange"].values[0],
                            "crypto",
                            crypto_USD["stock"].values[0],
                        )
                    elif not crypto_USDT.empty:
                        return (
                            crypto_USDT["exchange"].values[0],
                            "crypto",
                            crypto_USDT["stock"].values[0],
                        )

    async def get_tv_data(
        self, symbol: str, asset: str
    ) -> Optional[tuple[float, float, float]]:
        """
        Gets the current price, volume, 24h change, and TA data from the TradingView API.

        Parameters
        ----------
        symbol: string
            The ticker of the stock / crypto, e.g. "AAPL" or "BTCUSDT".
        asset: string
            The type of asset, either "stock" or "crypto".

        Returns
        -------
        Optional[tuple[float, float, float, str]]
            float
                The current price.
            float
                The current 24h change.
            float
                The current volume.
            str
                The exchange that this symbol is listed on.
        """

        try:
            symbol_data = self.get_symbol_data(symbol, asset)
            if symbol_data is not None:
                # Format it "exchange:symbol"
                exchange = symbol_data[0]
                symbol = f"{exchange}:{symbol_data[2]}"
            else:
                return False

            # Create a session
            session = aiohttp.ClientSession()
            async with session.ws_connect(
                url="wss://data.tradingview.com/socket.io/websocket",
                headers={"Origin": "https://data.tradingview.com"},
            ) as ws:

                # This is mandatory to get the data
                auth_str = "qs_" + "".join(
                    random.choice(string.ascii_lowercase) for i in range(12)
                )

                # Send messages via websocket
                await self.sendMessage(ws, "quote_create_session", [auth_str])
                await self.sendMessage(
                    ws, "quote_set_fields", [auth_str, "ch", "lp", "volume"]
                )
                await self.sendMessage(ws, "quote_add_symbols", [auth_str, symbol])

                counter = 0

                # Check for response
                async for msg in ws:
                    counter += 1

                    if msg.type == aiohttp.WSMsgType.TEXT:
                        resp = await self.on_msg(ws, msg.data)

                        if resp is not None:
                            await ws.close()
                            await session.close()
                            return resp[0], resp[1], resp[2], exchange

                        elif counter == 3:
                            return False

                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        # self.restart_sockets()
                        print("Error")
                        return False

        except Exception:
            print(traceback.format_exc())

    def get_tv_TA(self, symbol: str, asset: str) -> Optional[str]:
        """
        Gets the current TA (technical analysis) data from the TradingView API.

        Parameters
        ----------
        symbol : str
            The ticker of the stock / crypto.
        asset : str
            The type of asset, either "stock" or "crypto".

        Returns
        -------
        Optional[str]
            The TA data as formatted string.
        """

        # There is no TA for stock indices
        if symbol in self.stock_indices_without_exch:
            return

        symbol_data = self.get_symbol_data(symbol, asset)

        # Get the TradingView TA for symbol
        # Interval can be 1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1W, 1M
        try:
            if symbol_data is not None:
                exchange, market, symbol = symbol_data

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

                # Format the analysis
                formatted_analysis = f"{analysis['RECOMMENDATION']}\n{analysis['BUY']}📈 {analysis['NEUTRAL']}⌛️ {analysis['SELL']}📉"

                return formatted_analysis

        except Exception as e:
            print(f"TradingView TA error for {symbol}.", e)
