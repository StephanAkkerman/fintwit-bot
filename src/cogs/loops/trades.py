##> Imports
from __future__ import annotations
import asyncio
import time
import hmac
import base64
import json
import hashlib
import websockets
import datetime
import hmac
import threading

# > 3rd Party Dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop
import pandas as pd

# Local dependencies
from util.db import get_db, update_db
from util.disc_util import get_channel, get_user
from util.vars import config, stables, get_json_data, post_json_data

# Used to keep track of sent messages
messages = []


def clear_messages() -> None:
    """
    Clears the messages list

    Returns
    -------
    None
    """

    global messages

    if messages != []:
        messages.pop()


async def trades_msg(
    exchange: str,
    channel: discord.TextChannel,
    user: discord.User,
    symbol: str,
    side: str,
    orderType: str,
    price: float,
    quantity: float,
    usd: float,
) -> None:
    """
    Formats the Discord embed that will be send to the dedicated trades channel.

    Parameters
    ----------
    exchange : str
        The name of the exchange, currently only supports "binance" and "kucoin".
    channel : discord.TextChannel
        The channel that the message will be sent to.
    user : discord.User
        The user that the message will be sent from.
    symbol : str
        The symbol that has been traded.
    side : str
        The side of the trade, either "BUY" or "SELL".
    orderType : str
        The type of order, for instance "LIMIT" or "MARKET".
    price : float
        The price of the trade.
    quantity : float
        The amount traded.
    usd : float
        The worth of the trade in US dollar.

    Returns
    -------
    None
    """

    # Use messages list to prevent spamming
    global messages

    e = discord.Embed(
        title=f"{orderType.capitalize()} {side.lower()} {quantity} {symbol}",
        description="",
        color=0xF0B90B if exchange == "binance" else 0x24AE8F,
        timestamp=datetime.datetime.utcnow(),
    )

    # Check if this message has been send already
    check = f"{user.name} {symbol} {side}"

    if check not in messages:
        # Add it to the list
        messages.append(check)

        # Remove it after 60 sec
        threading.Timer(60, clear_messages).start()

        # Set the embed fields
        e.set_author(name=user.name, icon_url=user.avatar_url)

        # If the quote is USD, then the price is the USD value
        if symbol.endswith("USDT") or symbol.endswith("USD") or symbol.endswith("BUSD"):
            price = f"${price}"

        e.add_field(
            name="Price",
            value=price,
            inline=True,
        )

        e.add_field(name="Amount", value=quantity, inline=True)

        # If we know the USD value, then add it
        if usd != 0:
            e.add_field(
                name="$ Worth",
                value=f"${usd}",
                inline=True,
            )

        e.set_footer(
            icon_url="https://public.bnbstatic.com/20190405/eb2349c3-b2f8-4a93-a286-8f86a62ea9d8.png"
            if exchange == "binance"
            else "https://yourcryptolibrary.com/wp-content/uploads/2021/12/Kucoin-exchange-logo-1.png",
        )

        await channel.send(embed=e)

        # Tag the person
        if orderType.upper() != "MARKET":
            await channel.send(f"<@{user.id}>")


class Binance:
    def __init__(
        self,
        bot: commands.Bot,
        row: pd.Series | None,
        trades_channel: discord.TextChannel,
    ) -> None:
        """
        This class handles the Binance websocket connection.

        Methods
        -------
        hashing(query_string: str) -> str
            Necessary to send a signed request to the binance API.
        send_signed_request(url_path: str) -> dict:
            Sends the signed request to the binance API.
        get_data() -> pd.DataFrame:
            This function is used to get the account information from the binance API and convert it to a pandas dataframe.
        get_base_sym(sym: str) -> str:
            This function is used to get the base symbol of a symbol.
        get_usd_price(symbol: str) -> float:
            Gets the USD price of a symbol.
        on_msg(msg: str | bytes) -> None:
            This function is used to handle the incoming messages from the binance websocket.
        restart_sockets() -> None:
            Every 24 hours this function will restart the websockets.
         start_sockets() -> None:
            This function will start the websockets.
        """

        self.bot = bot
        self.trades_channel = trades_channel
        self.ws = None

        # So we can also just use None as row
        if isinstance(row, pd.Series):
            self.id = row["id"]
            self.key = row["key"]
            self.secret = row["secret"]
            self.user = bot.get_user(self.id)

        self.restart_sockets.start()

    # Necessary for sending a signed request
    def hashing(self, query_string: str) -> str:
        """
        This code has been taken from the binance documentation.
        It is necessary to send a signed request to the binance API.

        Parameters
        ----------
        query_string : str
            A string containing the timestamp in ms + recvWindow.

        Returns
        -------
        str
            String of hexadecimal characters.
        """

        return hmac.new(
            self.secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    async def send_signed_request(self, url_path: str) -> dict:
        """
        Sends the signed request to the binance API.
        Necessary to show that you own this account.

        Parameters
        ----------
        url_path : str
            The path following the base url, for instance "/api/v3/account".

        Returns
        -------
        dict
            Dictionary containing the response from the API.
        """

        query_string = f"timestamp={int(time.time() * 1000)}&recvWindow=60000"
        url = (
            "https://api.binance.com"
            + url_path
            + "?"
            + query_string
            + "&signature="
            + self.hashing(query_string)
        )
        headers = {
            "Content-Type": "application/json;charset=utf-8",
            "X-MBX-APIKEY": self.key,
        }

        return await get_json_data(url, headers)

    async def get_data(self) -> pd.DataFrame:
        """
        This code and above has been inspired by https://binance-docs.github.io/apidocs/spot/en/#account-information-user_data.
        This function is used to get the account information from the binance API and convert it to a pandas dataframe.

        Returns
        -------
        pd.DataFrame
            Dataframe containing the account balance.
        """

        response = await self.send_signed_request("/api/v3/account")
        balances = response["balances"]

        # Ensure that the user is set
        if self.user is None:
            self.user = await get_user(self.bot, self.id)

        # Create a list of dictionaries
        owned = [
            {
                "asset": asset["asset"],
                "owned": float(asset["free"]) + float(asset["locked"]),
                "exchange": "binance",
                "id": self.id,
                "user": self.user.name.split("#")[0],
            }
            # Loop over the balances
            for asset in balances
            # Only add them if they are not 0
            if float(asset["free"]) > 0 or float(asset["locked"]) > 0
        ]

        # Convert this list to a dataframe
        return pd.DataFrame(owned)

    async def get_base_sym(self, sym: str) -> str:
        """
        This function is used to get the base symbol of a symbol.
        For instance "BTCUDST" will return "BTC".

        Parameters
        ----------
        sym : str
            The symbol to get the base symbol of.

        Returns
        -------
        str
            The base symbol of the symbol sent as input.
        """

        # Use the Binance API to get the correct base symbol
        response = await get_json_data(
            f"https://api.binance.com/api/v3/exchangeInfo?symbol={sym}"
        )

        if "symbols" in response.keys():
            return response["symbols"][0]["baseAsset"]
        else:
            # Otherwise return the symbol given
            return sym

    async def get_usd_price(self, symbol: str) -> float:
        """
        Gets the USD price of a symbol.
        Symbol must only be usign the base symbol, for instance "BTC" will return the price of BTCUSD.

        Parameters
        ----------
        symbol : str
            The base symbol that we want to know the USD price of.

        Returns
        -------
        float
            The USD price of the symbol given.
        """

        # Use for-loop using USDT, USD, BUSD, DAI
        for usd in stables:
            response = await get_json_data(
                f"https://api.binance.com/api/v3/avgPrice?symbol={symbol+usd}"
            )

            if "price" in response.keys():
                return round(float(response["price"]), 2)

        # If the symbol is quoted in USDT, USD, BUSD, DAI, then return 0
        return 0

    #################################
    ### WEBSOCKET FUNCTIONS BELOW ###
    #################################

    async def on_msg(self, msg: str | bytes) -> None:
        """
        This function is used to handle the incoming messages from the binance websocket.

        Parameters
        ----------
        msg : str | bytes
            The message that is received from the binance websocket.

        Returns
        -------
        None
        """

        # Convert the message to a json object (dict)
        msg = json.loads(msg)

        if msg["e"] == "executionReport":
            sym = msg["s"]  # ie 'YFIUSDT'
            side = msg["S"]  # ie 'BUY', 'SELL'
            orderType = msg["o"]  # ie 'LIMIT', 'MARKET', 'STOP_LOSS_LIMIT'
            execType = msg["x"]  # ie 'TRADE', 'NEW' or 'CANCELLED'
            # execQuant = round(float(msg["z"]), 4) # The quantity filled
            price = round(float(msg["p"]), 4)  # Order price, sometimes shows 0.0
            if price == 0:
                price = round(float(msg["L"]), 4)  # The latest price it was filled at
            quantity = round(float(msg["q"]), 4)  # Order quantity

            # Only care about actual trades
            if execType == "TRADE":
                base = await self.get_base_sym(sym)
                if base not in stables:
                    usd = await self.get_usd_price(base)
                else:
                    usd = price

                # Send it in the discord channel
                await trades_msg(
                    "binance",
                    self.trades_channel,
                    self.user,
                    sym,
                    side,
                    orderType,
                    price,
                    quantity,
                    round(usd * quantity, 2),
                )

            # Assets db: asset, owned (quantity), exchange, id, user
            assets_db = get_db("assets")

            # Drop all rows for this user and exchange
            updated_assets_db = assets_db.drop(
                assets_db[
                    (assets_db["id"] == self.id) & (assets_db["exchange"] == "binance")
                ].index
            )

            assets_db = pd.concat(
                [updated_assets_db, await self.get_data()]
            ).reset_index(drop=True)

            update_db(assets_db, "assets")
            # Maybe post the updated assets of this user as well

    @loop(hours=24)
    async def restart_sockets(self) -> None:
        """
        Every 24 hours this function will restart the websockets.
        This is necessary otherwise the websockets will timeout.

        Returns
        -------
        None
        """

        if self.ws != None:
            await self.ws.close()
            self.ws = None
            await asyncio.sleep(60)
            await self.start_sockets()

    async def start_sockets(self) -> None:
        """
        This function will start the websockets.
        Documentation used for this websocket: https://github.com/binance/binance-spot-api-docs/blob/master/user-data-stream.md.
        Implementation of websockets inspired by: https://gist.github.com/pgrandinetti/964747a9f2464e576b8c6725da12c1eb.

        Returns
        -------
        None
        """

        # Documentation:
        listen_key = await post_json_data(
            url="https://api.binance.com/api/v3/userDataStream",
            headers={"X-MBX-APIKEY": self.key},
        )

        if "listenKey" in listen_key.keys():
            while True:
                # outer loop restarted every time the connection fails
                try:
                    async with websockets.connect(
                        uri=f'wss://stream.binance.com:9443/ws/{listen_key["listenKey"]}',
                        ping_interval=60 * 3,
                    ) as self.ws:
                        print(f"Succesfully connected {self.user} with Binance socket")
                        while True:
                            # listener loop
                            try:
                                reply = await self.ws.recv()

                            except RuntimeError as e:
                                print(
                                    "Binance ws.recv(): Waiting for another coroutine to get the next message.",
                                    e,
                                )

                            except (websockets.exceptions.ConnectionClosed):
                                print("Binance: Connection Closed")
                                await self.restart_sockets()
                                return

                            if reply:
                                await self.on_msg(reply)

                except ConnectionRefusedError:
                    print("Binance: Connection Refused")
                    await self.restart_sockets()
                    return

                # For some reason this always happens at startup, so ignore it
                except asyncio.TimeoutError:
                    continue


class KuCoin:
    """
    This class handles the KuCoin websocket connection.

    Methods
    -------
    get_data() -> pd.DataFrame:
        Gets the KuCoin assets of the user
    get_quote_price(self, symbol: str) -> float:
        Gets the quote price of a symbol.
    on_msg(msg: str | bytes) -> None:
        This function is used to handle the incoming messages from the KuCoin websocket.
    restart_sockets() -> None:
        Every 24 hours this function will restart the websockets.
    start_sockets() -> None:
        This function will start the websockets.
    get_token(api_request: str, headers: dict) -> dict:
        Gets the token necessary for starting the websocket.
    """

    def __init__(
        self, bot: commands.bot.Bot, row: pd.Series, trades_channel: discord.TextChannel
    ) -> None:

        self.bot = bot
        self.trades_channel = trades_channel
        self.ws = None

        if isinstance(row, pd.Series):
            self.id = row["id"]
            self.user = bot.get_user(row["id"])
            self.key = row["key"]
            self.secret = row["secret"]
            self.passphrase = row["passphrase"]

        self.restart_sockets.start()

    async def get_data(self) -> pd.DataFrame:
        """
        Gets the KuCoin assets of the user, documentation used: https://docs.kucoin.com/#get-an-account.

        Returns
        -------
        pd.DataFrame
            The dataframe of the assets of the user.
        """

        # Ensure that the user is set
        if self.user is None:
            self.user = await get_user(self.bot, self.id)

        url = "https://api.kucoin.com/api/v1/accounts"
        now = int(time.time() * 1000)
        str_to_sign = str(now) + "GET" + "/api/v1/accounts"
        signature = base64.b64encode(
            hmac.new(
                self.secret.encode("utf-8"), str_to_sign.encode("utf-8"), hashlib.sha256
            ).digest()
        )
        passphrase = base64.b64encode(
            hmac.new(
                self.secret.encode("utf-8"),
                self.passphrase.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        )
        headers = {
            "KC-API-SIGN": signature.decode("utf8"),
            "KC-API-TIMESTAMP": str(now),
            "KC-API-KEY": self.key,
            "KC-API-PASSPHRASE": passphrase.decode("utf8"),
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json",
        }

        response = await get_json_data(url, headers=headers)
        response = response["data"]

        owned = [
            {
                "asset": sym["currency"],
                "owned": float(sym["balance"]),
                "exchange": "kucoin",
                "id": self.id,
                "user": self.user.name.split("#")[0],
            }
            # Loop over all the symbols
            for sym in response
            # Only add them if they are not 0
            if float(sym["balance"]) > 0
        ]

        return pd.DataFrame(owned)

    async def get_quote_price(self, symbol: str) -> float:
        """
        Gets the quote price of a symbol.

        Parameters
        ----------
        symbol: str
                Symbol should be in the format of 'BASE-QUOTE, i.e. 'BTC-USDT'.

        Returns
        -------
        float
            Returns the value of a symbol in USD
        """

        response = await get_json_data(
            f"https://api.kucoin.com/api/v1/market/stats?symbol={symbol}"
        )
        data = response["data"]
        if data["averagePrice"] != None:
            return round(float(data["averagePrice"]), 2)
        else:
            return 0

    #################################
    ### WEBSOCKET FUNCTIONS BELOW ###
    #################################

    async def on_msg(self, msg: str | bytes) -> None:
        """
        This function is used to handle the incoming messages from the KuCoin websocket.

        Parameters
        ----------
        msg : str | bytes
            The message that is received from the KuCoin websocket.

        Returns
        -------
        None
        """

        msg = json.loads(msg)

        if "topic" in msg.keys():
            if (
                msg["topic"] == "/spotMarket/tradeOrders"
                and msg["data"]["type"] != "canceled"
                and "matchPrice" in msg["data"].keys()
            ):
                data = msg["data"]
                sym = data["symbol"]
                side = data["side"]
                orderType = data["orderType"]
                execPrice = float(data["matchPrice"])
                # "funds" is only available if side == 'buy'
                if side == "buy":
                    quantity = float(data["funds"]) / execPrice
                else:
                    quantity = float(data["size"])

                base = sym.split("-")[1]
                if base not in stables:
                    usd = await self.get_quote_price(base + "-" + "USDT")
                    worth = round(usd * quantity, 2)
                else:
                    if side == "buy":
                        worth = round(float(data["funds"]), 2)
                    else:
                        worth = round(float(data["size"]) * execPrice, 2)

                await trades_msg(
                    "KuCoin",
                    self.trades_channel,
                    self.user,
                    sym,
                    side,
                    orderType,
                    execPrice,
                    quantity,
                    worth,
                )

                # Assets db: asset, owned (quantity), exchange, id, user
                assets_db = get_db("assets")

                # Drop all rows for this user and exchange
                updated_assets_db = assets_db.drop(
                    assets_db[
                        (assets_db["id"] == self.id)
                        & (assets_db["exchange"] == "kucoin")
                    ].index
                )

                assets_db = pd.concat(
                    [updated_assets_db, await self.get_data()]
                ).reset_index(drop=True)

                update_db(assets_db, "assets")
                # Maybe post the assets of this user as well

    @loop(hours=24)
    async def restart_sockets(self) -> None:
        """
        Every 24 hours this function will restart the websockets.
        This is necessary otherwise the websockets will timeout.

        Returns
        -------
        None
        """

        if self.ws != None:
            await self.ws.close()
            self.ws = None
            await asyncio.sleep(60)
            await self.start_sockets()

    async def get_token(self, api_request: str, headers: dict) -> dict:
        """
        Gets the token necessary for starting the websocket.

        Parameters
        ----------
        api_request : str
            The request sent to the kucoin api.
        headers : dict
            The provided headers necessary for this request.

        Returns
        -------
        dict
            The response from the kucoin api.
        """

        return await post_json_data(
            url="https://api.kucoin.com" + api_request, headers=headers
        )

    async def start_sockets(self) -> None:
        """
        This function starts the websockets, documentation used: https://docs.kucoin.com/
        For the GET, DELETE request, all query parameters need to be included in the request url. (e.g. /api/v1/accounts?currency=BTC)
        For the POST, PUT request, all query parameters need to be included in the request body with JSON. (e.g. {"currency":"BTC"}).
        Do not include extra spaces in JSON strings.

        Returns
        -------
        None
        """

        # From https://docs.kucoin.com/#authentication
        now_time = int(time.time()) * 1000
        # Endpoint can be GET, DELETE, POST, PUT
        # Body can be for instance /api/v1/accounts
        api_request = "/api/v1/bullet-private"
        str_to_sign = str(now_time) + "POST" + api_request
        sign = base64.b64encode(
            hmac.new(
                self.secret.encode("utf-8"), str_to_sign.encode("utf-8"), hashlib.sha256
            ).digest()
        )
        passphrase = base64.b64encode(
            hmac.new(
                self.secret.encode("utf-8"),
                self.passphrase.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        )

        headers = {
            "KC-API-KEY": self.key,
            "KC-API-SIGN": sign.decode("utf8"),
            "KC-API-TIMESTAMP": str(now_time),
            "KC-API-PASSPHRASE": passphrase.decode("utf8"),
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json",
        }

        # https://docs.kucoin.com/#apply-connect-token
        try:
            response = await self.get_token(api_request, headers)
        except Exception as e:
            print("Error getting KuCoin token:", e)
            self.restart_sockets()

        # https://docs.kucoin.com/#request for codes
        if response["code"] == "200000":
            token = response["data"]["token"]

            # Set ping
            ping_interval = (
                int(response["data"]["instanceServers"][0]["pingInterval"]) // 1000
            )
            ping_timeout = (
                int(response["data"]["instanceServers"][0]["pingTimeout"]) // 1000
            )

            while True:
                # outer loop restarted every time the connection fails
                try:
                    async with websockets.connect(
                        uri=f"wss://ws-api.kucoin.com/endpoint?token={token}",
                        ping_interval=ping_interval,
                        ping_timeout=ping_timeout,
                    ) as self.ws:
                        await self.ws.send(
                            json.dumps(
                                {
                                    "type": "subscribe",
                                    "topic": "/spotMarket/tradeOrders",
                                    "privateChannel": "true",
                                    "response": "true",
                                }
                            )
                        )
                        print(f"Succesfully connected {self.user} with KuCoin socket")
                        while True:
                            # listener loop
                            try:
                                reply = await self.ws.recv()

                            except RuntimeError as e:
                                print(
                                    "KuCoin ws.recv(): Waiting for another coroutine to get the next message.",
                                    e,
                                )

                            except websockets.exceptions.ConnectionClosed as e:
                                print("KuCoin: Connection Closed", e)
                                # Close the websocket and restart
                                await self.restart_sockets()
                                # Return so that we do not restart multiple times
                                return

                            if reply:
                                await self.on_msg(reply)

                except websockets.exceptions.InvalidStatusCode as e:
                    print("KuCoin: Server rejected connection", e)
                    await self.restart_sockets()
                    return

                except ConnectionRefusedError as e:
                    print("KuCoin: Connection Refused", e)
                    await self.restart_sockets()
                    return

                # For some reason this always happens at startup, so ignore it
                except asyncio.TimeoutError:
                    continue
        else:
            print("Error getting KuCoin response")
            self.restart_sockets()


class Trades(commands.Cog):
    """
    This class contains the cog for posting new trades done by users.
    It can be enabled / disabled in the config under ["LOOPS"]["TRADES"].

    Methods
    -------
    trades(db : pd.DataFrame) -> None:
        Starts the websockets for each user in the database.
    """

    def __init__(
        self, bot: commands.Bot, db: pd.DataFrame = get_db("portfolio")
    ) -> None:
        self.bot = bot
        self.trades_channel = get_channel(
            self.bot, config["LOOPS"]["TRADES"]["CHANNEL"]
        )

        # Start getting trades
        asyncio.create_task(self.trades(db))

    async def trades(self, db: pd.DataFrame) -> None:
        """
        Starts the websockets for each user in the database.

        Parameters
        ----------
        db : pd.DataFrame
            The database containing all users.
        """

        if not db.empty:

            # Divide per exchange
            binance = db.loc[db["exchange"] == "binance"]
            kucoin = db.loc[db["exchange"] == "kucoin"]

            if not binance.empty:
                for _, row in binance.iterrows():
                    # If using await, it will block other connections
                    asyncio.create_task(
                        Binance(self.bot, row, self.trades_channel).start_sockets()
                    )

            if not kucoin.empty:
                for _, row in kucoin.iterrows():
                    asyncio.create_task(
                        KuCoin(self.bot, row, self.trades_channel).start_sockets()
                    )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Trades(bot))
