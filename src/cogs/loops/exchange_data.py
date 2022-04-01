##> Imports
import asyncio
import aiohttp
import time
import hmac
import base64
import json
import hashlib
import websockets
import datetime
import hmac

# > 3rd Party Dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop
import pandas as pd

# Local dependencies
from util.db import get_db, update_db
from util.disc_util import get_channel, get_user
from util.vars import config, stables

async def trades_msg(exchange, channel, user, symbol, side, orderType, price, quantity, usd):
    
    e = discord.Embed(
            title=f"{orderType.capitalize()} {side.lower()} {quantity} {symbol}",
            description="",
            color=0xf0b90b if exchange == 'binance' else 0x24ae8f,
        )
    
    e.set_author(name=user.name, icon_url=user.avatar_url)
    
    if symbol.endswith('USDT') or symbol.endswith('USD') or symbol.endswith('BUSD'):
        price = f"${price}"
    
    e.add_field(
            name="Price", value=price, inline=True,
        )
    
    e.add_field(name="Amount", value=quantity, inline=True)
    
    if usd != 0:
        e.add_field(
                name="$ Worth", value=f"${usd}", inline=True,
            )
    
    e.set_footer(
        text=f"Today at {datetime.datetime.now().strftime('%H:%M')}",
        icon_url="https://public.bnbstatic.com/20190405/eb2349c3-b2f8-4a93-a286-8f86a62ea9d8.png" if exchange == 'binance' else "https://yourcryptolibrary.com/wp-content/uploads/2021/12/Kucoin-exchange-logo-1.png",
    )
            
    await channel.send(embed=e)

    # Tag the person
    if orderType.upper() != "MARKET":
        await channel.send(f"<@{user.id}>")
        
class Binance():
    def __init__(self, bot, row, trades_channel):
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
        
    def hashing(self, query_string):
        return hmac.new(
            self.secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()
    
    # used for sending request requires the signature
    async def send_signed_request(self, url_path):
        query_string = f"timestamp={int(time.time() * 1000)}&recvWindow=60000"
        url = (
            "https://api.binance.com" + url_path + "?" + query_string + "&signature=" + self.hashing(query_string) 
        )
        headers = {"Content-Type": "application/json;charset=utf-8", "X-MBX-APIKEY": self.key}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=headers
            ) as r:
                response = await r.json()
                return response
        
    async def get_data(self):
        #https://binance-docs.github.io/apidocs/spot/en/#account-information-user_data
        response = await self.send_signed_request("/api/v3/account")
        balances = response['balances']
        
        # Ensure that the user is set
        if self.user is None:
            self.user = await get_user(self.bot, self.id)
        
        owned = [{'asset':asset['asset'],
                  'owned':float(asset['free'])+float(asset['locked']),
                  'exchange':'binance',
                  'id':self.id,
                  'user':self.user.name.split('#')[0]} for asset in balances if float(asset['free']) > 0 or float(asset['locked']) > 0]
        return pd.DataFrame(owned)
        
    async def get_base_sym(self, sym):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.binance.com/api/v3/exchangeInfo?symbol={sym}"
            ) as r:
                response = await r.json()
                
                if "symbols" in response.keys():
                    return response["symbols"][0]["baseAsset"]
                else:
                    return sym
        
    async def get_usd_price(self, symbol):
        """Symbol should be in the format of 'BTCUSDT'"""
        # Use for-loop using USDT, USD, BUSD, DAI
        for usd in stables:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.binance.com/api/v3/avgPrice?symbol={symbol+usd}"
                ) as r:
                    response = await r.json()

                    if "price" in response.keys():
                        return round(float(response["price"]),2)
        
        return 0
        
    ### From here are the websocket functions ###
    async def on_msg(self, msg):   
        # Convert the message to a json object (dict)
        msg = json.loads(msg)
             
        if msg['e'] == 'executionReport':                        
            sym = msg["s"]  # ie 'YFIUSDT'
            side = msg["S"]  # ie 'BUY', 'SELL'
            orderType = msg["o"]  # ie 'LIMIT', 'MARKET', 'STOP_LOSS_LIMIT'
            execType = msg["x"]  # ie 'TRADE', 'NEW' or 'CANCELLED'
            #execQuant = round(float(msg["z"]), 4) # The quantity filled
            price = round(float(msg["p"]), 4) # Order price, sometimes shows 0.0
            if price == 0:
                price = round(float(msg["L"]), 4) # The latest price it was filled at
            quantity = round(float(msg["q"]), 4) # Order quantity
            
            # Only care about actual trades
            if execType == "TRADE":
                base = await self.get_base_sym(sym)
                if base not in stables:
                    usd = await self.get_usd_price(base)
                else:
                    usd = 0
                await trades_msg("binance", self.trades_channel, self.user, sym, side, orderType, price, quantity, usd)
                
            # Assets db: asset, owned (quantity), exchange, id, user
            assets_db = get_db("assets")
            
            # Drop all rows for this user and exchange
            updated_assets_db = assets_db.drop(assets_db[(assets_db["id"] == self.id) & 
                                              (assets_db["exchange"] == "binance")].index)
            
            assets_db = pd.concat([updated_assets_db, await self.get_data()]).reset_index(drop=True)
            
            update_db(assets_db, "assets")
            # Maybe post the assets of this user as well
            
    @loop(hours=24)
    async def restart_sockets(self):
        if self.ws != None:
            await self.ws.close()
            self.ws = None
            await asyncio.sleep(60)
            await self.start_sockets()

    async def start_sockets(self):
        # Documentation: https://github.com/binance/binance-spot-api-docs/blob/master/user-data-stream.md
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url = 'https://api.binance.com/api/v3/userDataStream', headers= {'X-MBX-APIKEY': self.key}
            ) as r:
                listen_key = await r.json()
                                    
                if 'listenKey' in listen_key.keys():
                    # Implementation inspired by: https://gist.github.com/pgrandinetti/964747a9f2464e576b8c6725da12c1eb
                    while True:
                        # outer loop restarted every time the connection fails
                        try:
                            async with websockets.connect(uri=f'wss://stream.binance.com:9443/ws/{listen_key["listenKey"]}', 
                                                        ping_interval= 60*3) as self.ws:
                                print("Succesfully connected with Binance socket")
                                while True:
                                # listener loop
                                    try:
                                        reply = await self.ws.recv()
                                        await self.on_msg(reply)
                                    except (websockets.exceptions.ConnectionClosed):
                                        print("Binance: Connection Closed")
                                        await self.restart_sockets()
                                        
                        except ConnectionRefusedError:
                            print("Binance: Connection Refused")
                            await self.restart_sockets()
                            
                        # For some reason this always happens at startup, so ignore it
                        except asyncio.TimeoutError:
                            continue
                    
class KuCoin():
    def __init__(self, bot, row, trades_channel):
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
        
    async def get_data(self):
        # Ensure that the user is set
        if self.user is None:
            self.user = await get_user(self.bot, self.id)        
        
        #https://docs.kucoin.com/#get-an-account
        url = 'https://api.kucoin.com/api/v1/accounts'
        now = int(time.time() * 1000)
        str_to_sign = str(now) + 'GET' + '/api/v1/accounts'
        signature = base64.b64encode(hmac.new(self.secret.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest())
        passphrase = base64.b64encode(hmac.new(self.secret.encode('utf-8'), self.passphrase.encode('utf-8'), hashlib.sha256).digest())
        headers = {
            "KC-API-SIGN": signature.decode('utf8'),
            "KC-API-TIMESTAMP": str(now),
            "KC-API-KEY": self.key,
            "KC-API-PASSPHRASE": passphrase.decode('utf8'),
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=headers
            ) as r:
                response = await r.json()
                response = response['data']
        
                owned = [{"asset":sym['currency'],
                        "owned":float(sym['balance']),
                        'exchange':'kucoin',
                        'id':self.id,
                        'user':self.user.name.split('#')[0]} for sym in response if float(sym['balance']) > 0]
                return pd.DataFrame(owned)
            
    async def get_quote_price(self, symbol):
        """
        Symbol should be in the format of 'BTC-USDT'
        Returns the value of BTC in USDT
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.kucoin.com/api/v1/market/stats?symbol={symbol}"
            ) as r:
                response = await r.json()

                data = response['data']
                if data["averagePrice"] != None:
                    return round(float(data["averagePrice"]),2)
                else:
                    return 0
                
    ### From here are the websocket functions ###
    async def on_msg(self, msg):        
        msg = json.loads(msg)
                        
        if 'topic' in msg.keys():
            if msg['topic'] == "/spotMarket/tradeOrders" and msg['type'] != 'canceled':                 
                data = msg['data']
                sym = data['symbol']
                side = data['side']
                orderType = data['orderType']
                quantity = data['filledSize'] + data['remainSize']
                execPrice = data['matchPrice']
                
                base = sym.split('-')[0]
                if base not in stables:
                    usd = await self.get_quote_price(base + '-' + "USDT")
                else:
                    usd = 0
                
                await trades_msg("KuCoin", self.trades_channel, self.user, sym, side, orderType, execPrice, quantity, usd)
            
                # Assets db: asset, owned (quantity), exchange, id, user
                assets_db = get_db("assets")
                
                # Drop all rows for this user and exchange
                updated_assets_db = assets_db.drop(assets_db[(assets_db["id"] == self.id) & 
                                                (assets_db["exchange"] == "kucoin")].index)
                
                assets_db = pd.concat([updated_assets_db, await self.get_data()]).reset_index(drop=True)
                
                update_db(assets_db, "assets")
                # Maybe post the assets of this user as well
                
    @loop(hours=24)
    async def restart_sockets(self):
        if self.ws != None:
            await self.ws.close()
            self.ws = None
            await asyncio.sleep(60)
            await self.start_sockets()
                        
    async def start_sockets(self):
        # From documentation: https://docs.kucoin.com/
        # For the GET, DELETE request, all query parameters need to be included in the request url. (e.g. /api/v1/accounts?currency=BTC)
        # For the POST, PUT request, all query parameters need to be included in the request body with JSON. (e.g. {"currency":"BTC"}). 
        # Do not include extra spaces in JSON strings.
        
        # From https://docs.kucoin.com/#authentication
        now_time = int(time.time()) * 1000
        # Endpoint can be GET, DELETE, POST, PUT 
        # Body can be for instance /api/v1/accounts
        api_request = "/api/v1/bullet-private"
        str_to_sign = str(now_time) + "POST" + api_request
        sign = base64.b64encode(
            hmac.new(self.secret.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest())
        passphrase = base64.b64encode(
            hmac.new(self.secret.encode('utf-8'), self.passphrase.encode('utf-8'), hashlib.sha256).digest())
        
        headers = {"KC-API-KEY": self.key, 
                   "KC-API-SIGN" : sign.decode('utf8'), 
                   "KC-API-TIMESTAMP": str(now_time),
                   "KC-API-PASSPHRASE": passphrase.decode('utf8'), 
                   "KC-API-KEY-VERSION": '2',
                   "Content-Type": "application/json"}
        
        # https://docs.kucoin.com/#apply-connect-token
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url = "https://api.kucoin.com" + api_request, headers=headers
            ) as r:
                response = await r.json()
        
                # https://docs.kucoin.com/#request for codes
                if response['code'] == '200000':
                    token = response['data']['token']
                    
                    # Set ping 
                    ping_interval=int(response['data']['instanceServers'][0]['pingInterval']) // 1000
                    ping_timeout=int(response['data']['instanceServers'][0]['pingTimeout']) // 1000
                    
                    while True:
                        # outer loop restarted every time the connection fails
                        try:
                            async with websockets.connect(uri=f'wss://ws-api.kucoin.com/endpoint?token={token}', 
                                                        ping_interval = ping_interval,
                                                        ping_timeout = ping_timeout) as self.ws:
                                await self.ws.send(json.dumps({'type': 'subscribe', 'topic': '/spotMarket/tradeOrders', 'privateChannel': 'true', 'response': 'true'}))
                                print("Succesfully connected with KuCoin socket")
                                while True:
                                # listener loop
                                    try:
                                        reply = await self.ws.recv()
                                        await self.on_msg(reply)
                                    except (websockets.exceptions.ConnectionClosed):
                                        print("KuCoin: Connection Closed")
                                        # Close the websocket and restart
                                        await self.restart_sockets()

                        except websockets.exceptions.InvalidStatusCode:
                            print("KuCoin: Server rejected connection")
                            await self.restart_sockets()
                                                            
                        except ConnectionRefusedError:
                            print("KuCoin: Connection Refused")
                            await self.restart_sockets()
                            
                        # For some reason this always happens at startup, so ignore it
                        except asyncio.TimeoutError:
                            continue
                else:
                    print("Error getting KuCoin response")
                    self.restart_sockets()
       
class Exchanges(commands.Cog):    
    def __init__(self, bot, db=get_db('portfolio')):
        self.bot = bot
        self.trades_channel = get_channel(self.bot, config["TRADES"]["CHANNEL"])  
                
        # Start getting trades
        asyncio.create_task(self.trades(db))      
    
    async def trades(self, db):   
        if not db.empty:
            
            # Divide per exchange
            binance = db.loc[db['exchange'] == 'binance']
            kucoin = db.loc[db['exchange'] == 'kucoin']
            
            if not binance.empty:
                for _, row in binance.iterrows():
                    # If using await, it will block other connections
                    asyncio.create_task(Binance(self.bot, row, self.trades_channel).start_sockets())
                        
            if not kucoin.empty:
                for _, row in kucoin.iterrows():
                    asyncio.create_task(KuCoin(self.bot, row, self.trades_channel).start_sockets())

        
def setup(bot):
    bot.add_cog(Exchanges(bot))