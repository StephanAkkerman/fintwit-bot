## > Imports
# > Standard libaries
from __future__ import annotations

import json
import random
import re
import string
import traceback
from typing import List, Optional

# > 3rd party dependencies
import aiohttp
import pandas as pd
from tradingview_ta import Interval, TA_Handler

# > Local dependencies
import util.vars
from util.tv_symbols import all_forex_indices, crypto_indices, stock_indices
from util.vars import get_json_data, logger


async def get_tv_ticker_data(url, append_to=None):
    data = await get_json_data(url)

    if not data or data == {} or "data" not in data.keys():
        return pd.DataFrame()

    # Convert data to pandas df
    tv_data = pd.DataFrame(data["data"]).drop(columns=["d"])

    if append_to:
        # This adds additional information to the dataframe
        tv_data = pd.concat([tv_data, pd.DataFrame(append_to, columns=["s"])])

    # Split the information in exchange and stock
    tv_data[["exchange", "stock"]] = tv_data["s"].str.split(":", n=1, expand=True)

    return tv_data


class TV_data:
    """
    This class is used to get the current price, 24h change, and volume of a stock.
    It also includes methods to get the TradingView TA data.
    """

    def __init__(self) -> None:
        self.stock_indices_without_exch = [sym.split(":")[1] for sym in stock_indices]
        self.crypto_indices_without_exch = [sym.split(":")[1] for sym in crypto_indices]
        self.forex_indices_without_exch = [
            sym.split(":")[1] for sym in all_forex_indices
        ]

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
                            logger.error("KeyError in TradingView ws_data")
                            return None

                        if price != 0:
                            perc_change = round((change / price) * 100, 2)
                        else:
                            logger.warn("TradingView returns price=0")
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
            logger.error(traceback.format_exc())

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
            The function to call, all start with ``quote_`` followed by the function name.
        args : List[str]
            The list of arguments to send in the message.
        """

        as_json = json.dumps({"m": func, "p": args}, separators=(",", ":"))
        prepended = "~m~" + str(len(as_json)) + "~m~" + as_json
        await ws.send_str(prepended)

    def get_usd_info(self, tv_crypto, symbol: str, suffix: str):
        if not symbol.endswith(suffix):
            # If it crypto try adding USD or USDT
            crypto_USD = tv_crypto.loc[tv_crypto["stock"] == symbol + suffix]

            if not crypto_USD.empty:
                return (
                    crypto_USD["exchange"].values[0],
                    "crypto",
                    crypto_USD["stock"].values[0],
                )

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
                The exchange the symbol is traded on, e.g. "FTX" or "Binance".
            str
                The market the symbol is traded on, e.g. "crypto", "america", "forex".
            str
                The symbol itself.
        """

        tv_stocks = util.vars.stocks
        tv_crypto = util.vars.crypto
        tv_forex = util.vars.forex

        if asset == "stock":
            stock = tv_stocks.loc[tv_stocks["stock"] == symbol]
            if not stock.empty:
                return stock["exchange"].values[0], "america", symbol

        elif asset == "forex":
            forex = tv_forex.loc[tv_forex["stock"] == symbol]
            if not forex.empty:
                return forex["exchange"].values[0], "forex", symbol

        elif asset == "crypto":
            crypto = tv_crypto.loc[tv_crypto["stock"] == symbol]
            if not crypto.empty:
                return crypto["exchange"].values[0], "crypto", symbol
            else:
                # Iterate over some USD suffixes
                for s in ["USD", "USDT", "USDTPERP"]:
                    if data := self.get_usd_info(tv_crypto, symbol, s):
                        return data

    async def get_tv_data(
        self, symbol: str, asset: str
    ) -> Optional[tuple[float, float, float, str, str]]:
        """
        Gets the current price, volume, 24h change, and TA data from the TradingView API.

        Parameters
        ----------
        symbol: string
            The ticker of the stock / crypto, e.g. "AAPL" or "BTCUSDT".
        asset: string
            The type of asset, either "stock", "crypto", or "forex".

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
            str
                The url to the TradingView chart for this symbol.
        """

        if asset == "stock":
            website_suffix = "/?yahoo"
        elif asset == "forex":
            website_suffix = "/?forex"
        elif asset == "crypto":
            website_suffix = "/?coingecko"

        website = f"https://www.tradingview.com/symbols/{symbol}{website_suffix}"

        try:
            symbol_data = self.get_symbol_data(symbol, asset)
            if symbol_data is not None:
                # Format it "exchange:symbol"
                exchange = symbol_data[0]
                symbol = f"{exchange}:{symbol_data[2]}"
                website = f"https://www.tradingview.com/symbols/{symbol_data[2]}{website_suffix}"

            else:
                return (0, None, 0, None, website)

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
                            # Convert to USD volume if asset is crypto
                            return (
                                float(resp[0]),
                                float(resp[1]),
                                resp[0] * resp[2] if asset == "crypto" else resp[2],
                                exchange.lower(),
                                website,
                            )

                        elif counter == 3:
                            await session.close()
                            return (0, None, 0, None, website)

                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        # self.restart_sockets()
                        logger.error("TradingView websocket Error")
                        await session.close()
                        return (0, None, 0, None, website)

        except aiohttp.ClientConnectionError:
            logger.error("Temporary TradingView websocket error")

        except Exception:
            logger.error(traceback.format_exc())

        return (0, None, 0, None, website)

    def format_analysis(self, analysis: dict) -> str:
        """
        Simple helper function to format the TA data into one string.

        Parameters
        ----------
        analysis : dict
            The original TA data from the TradingView API.

        Returns
        -------
        str
            The formatted TA data.
        """

        return f"{analysis['RECOMMENDATION']}\n{analysis['BUY']}📈 {analysis['NEUTRAL']}⌛️ {analysis['SELL']}📉"

    def get_tv_TA(self, symbol: str, asset: str) -> Optional[tuple[str, str]]:
        """
        Gets the current TA (technical analysis) data from the TradingView API.

        Parameters
        ----------
        symbol : str
            The ticker of the stock / crypto.
        asset : str
            The type of asset, either "stock", "crypto" or "forex".

        Returns
        -------
        Optional[tuple[str,str]]
            The 4h and 1d TA data as formatted strings.
        """

        # There is no TA for indices
        if (
            symbol in self.stock_indices_without_exch
            or symbol in self.crypto_indices_without_exch
            or symbol in self.forex_indices_without_exch
        ):
            return None, None

        symbol_data = self.get_symbol_data(symbol, asset)
        four_h_analysis = one_d_analysis = None

        # Get the TradingView TA for symbol
        # Interval can be 1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1W, 1M
        if symbol_data is not None:
            exchange, market, symbol = symbol_data

            # Wait max 5 sec
            try:
                four_h_analysis = TA_Handler(
                    symbol=symbol,
                    screener=market,
                    exchange=exchange,
                    interval=Interval.INTERVAL_4_HOURS,
                    timeout=5,
                ).get_analysis()

                one_d_analysis = TA_Handler(
                    symbol=symbol,
                    screener=market,
                    exchange=exchange,
                    interval=Interval.INTERVAL_1_DAY,
                    timeout=5,
                ).get_analysis()

            except Exception as e:
                logger.error(f"TradingView TA error for ticker: {symbol}, error:", e)
                return None, None

            if four_h_analysis:
                four_h_analysis = self.format_analysis(four_h_analysis.summary)

            if one_d_analysis:
                one_d_analysis = self.format_analysis(one_d_analysis.summary)

            # Format the analysis
            return four_h_analysis, one_d_analysis

        return None, None


tv = TV_data()
