##> Imports
import requests
import asyncio
import time
import hmac
import base64
import json
import hashlib
import websockets
import datetime
import hmac
from urllib.parse import urlencode

# > 3rd Party Dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop
import pandas as pd

# Local dependencies
from util.db import get_db, update_db
from util.disc_util import get_channel
from util.vars import config
from util.disc_util import get_guild

stables = ['USDT', 'USD', 'BUSD', 'DAI']

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
        
        # So we can also just use None as row
        if isinstance(row, pd.Series):
            self.id = row["id"]
            self.user = bot.get_user(row["id"])
            self.key = row["key"]
            self.secret = row["secret"]
        
    def get_timestamp(self):
        return int(time.time() * 1000)

    def hashing(self, query_string):
        return hmac.new(
            self.secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def dispatch_request(self, http_method):
        session = requests.Session()
        session.headers.update(
            {"Content-Type": "application/json;charset=utf-8", "X-MBX-APIKEY": self.key}
        )
        return {
            "GET": session.get,
            "DELETE": session.delete,
            "PUT": session.put,
            "POST": session.post,
        }.get(http_method, "GET")

    # used for sending request requires the signature
    def send_signed_request(self, http_method, url_path, payload={}):
        query_string = urlencode(payload, True)
        if query_string:
            query_string = "{}&timestamp={}".format(query_string, self.get_timestamp())
        else:
            query_string = "timestamp={}".format(self.get_timestamp())

        url = (
            "https://api.binance.com" + url_path + "?" + query_string + "&signature=" + self.hashing(query_string)
        )
        #print("{} {}".format(http_method, url))
        params = {"url": url, "params": {}}
        response = self.dispatch_request(http_method)(**params)
        return response.json()
    
    def get_data(self):
        #https://binance-docs.github.io/apidocs/spot/en/#account-information-user_data
        response = self.send_signed_request("GET", "/api/v3/account", {})
        balances = response['balances']
        owned = [{'asset':asset['asset'],
                  'owned':float(asset['free'])+float(asset['locked']),
                  'exchange':'binance',
                  'id':self.id,
                  'user':self.user.name.split('#')[0]} for asset in balances if float(asset['free']) > 0 or float(asset['locked']) > 0]
        return pd.DataFrame(owned) 
        
    def get_base_sym(self, sym):
        response = requests.get(f"https://api.binance.com/api/v3/exchangeInfo?symbol={sym}").json()
        if "symbols" in response.keys():
            return response["symbols"][0]["baseAsset"]
        else:
            return sym
        
    def get_usd_price(self, symbol):
        """Symbol should be in the format of 'BTCUSDT'"""
        # Use for-loop using USDT, USD, BUSD, DAI
        for usd in stables:
            response = requests.get(f"https://api.binance.com/api/v3/avgPrice?symbol={symbol+usd}").json()
            if "price" in response.keys():
                return round(float(response["price"]),2)
        
        print(f"Could not find average price on Binance for {symbol}")
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
                base = self.get_base_sym(sym)
                if base not in stables:
                    usd = self.get_usd_price(base)
                else:
                    usd = 0
                await trades_msg("binance", self.trades_channel, self.user, sym, side, orderType, price, quantity, usd)
                
            # Assets db: asset, owned (quantity), exchange, id, user
            assets_db = get_db("assets")
            
            # Drop all rows for this user and exchange
            updated_assets_db = assets_db.drop(assets_db[(assets_db["id"] == self.id) & 
                                              (assets_db["exchange"] == "binance")].index)
            
            assets_db = pd.concat([updated_assets_db, self.get_data()]).reset_index(drop=True)
            
            update_db(assets_db, "assets")
            # Maybe post the assets of this user as well

    async def start_sockets(self):
        # Documentation: https://github.com/binance/binance-spot-api-docs/blob/master/user-data-stream.md
        headers = {'X-MBX-APIKEY': self.key}
                    
        listen_key = requests.post(url = 'https://api.binance.com/api/v3/userDataStream', headers=headers).json()
                
        if 'listenKey' in listen_key.keys():
            # https://gist.github.com/pgrandinetti/964747a9f2464e576b8c6725da12c1eb
            while True:
                # outer loop restarted every time the connection fails
                try:
                    async with websockets.connect(uri=f'wss://stream.binance.com:9443/ws/{listen_key["listenKey"]}', 
                                                  ping_interval= 60*3) as ws:
                        print("Succesfully connected with Binance socket")
                        while True:
                        # listener loop
                            try:
                                reply = await ws.recv()
                                await self.on_msg(reply)
                            except (websockets.exceptions.ConnectionClosed):
                                print("Binance: Connection Closed")
                                break
                                # Maybe ping the server
                except ConnectionRefusedError:
                    print("Binance: Connection Refused")
                    # Should reconnect after a bit
                    
                # For some reason this always happens at startup, so ignore it
                except asyncio.TimeoutError:
                    continue
                    
class KuCoin():
    def __init__(self, bot, row, trades_channel):
        self.bot = bot
        self.trades_channel = trades_channel
        
        if isinstance(row, pd.Series):
            self.id = row["id"]
            self.user = bot.get_user(row["id"])
            self.key = row["key"]
            self.secret = row["secret"]
            self.passphrase = row["passphrase"]
        
    def get_data(self):
        #https://docs.kucoin.com/#get-an-account
        url = 'https://api.kucoin.com/api/v1/accounts'
        now = int(time.time() * 1000)
        str_to_sign = str(now) + 'GET' + '/api/v1/accounts'
        signature = base64.b64encode(hmac.new(self.secret.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest())
        passphrase = base64.b64encode(hmac.new(self.secret.encode('utf-8'), self.passphrase.encode('utf-8'), hashlib.sha256).digest())
        headers = {
            "KC-API-SIGN": signature,
            "KC-API-TIMESTAMP": str(now),
            "KC-API-KEY": self.key,
            "KC-API-PASSPHRASE": passphrase,
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers).json()['data']
        owned = [{"asset":sym['currency'],
                  "owned":sym['balance'],
                  'exchange':'kucoin',
                  'id':self.id,
                  'user':self.user.name.split('#')[0]} for sym in response if float(sym['balance']) > 0]
        return pd.DataFrame(owned)
    
    def get_quote_price(self, symbol):
        """
        Symbol should be in the format of 'BTC-USDT'
        Returns the value of BTC in USDT
        """
        response = requests.get(f"https://api.kucoin.com/api/v1/market/stats?symbol={symbol}").json()
        data = response['data']
        if data["averagePrice"] != None:
            return round(float(data["averagePrice"]),2)
        else:
            print(f"Could not find average price on KuCoin for {symbol}")
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
                    usd = self.get_quote_price( + '-' + "USDT")
                else:
                    usd = 0
                
                await trades_msg("KuCoin", self.trades_channel, self.user, sym, side, orderType, execPrice, quantity, usd)
            
                # Assets db: asset, owned (quantity), exchange, id, user
                assets_db = get_db("assets")
                
                # Drop all rows for this user and exchange
                updated_assets_db = assets_db.drop(assets_db[(assets_db["id"] == self.id) & 
                                                (assets_db["exchange"] == "kucoin")].index)
                
                assets_db = pd.concat([updated_assets_db, self.get_data()]).reset_index(drop=True)
                
                update_db(assets_db, "assets")
                # Maybe post the assets of this user as well
                        
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
                   "KC-API-SIGN" : sign, 
                   "KC-API-TIMESTAMP": str(now_time),
                   "KC-API-PASSPHRASE": passphrase, 
                   "KC-API-KEY-VERSION": '2',
                   "Content-Type": "application/json"}
        
        # https://docs.kucoin.com/#apply-connect-token
        response = requests.post(url = "https://api.kucoin.com" + api_request, headers=headers).json()
        
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
                                                  ping_timeout = ping_timeout) as ws:
                        await ws.send(json.dumps({'type': 'subscribe', 'topic': '/spotMarket/tradeOrders', 'privateChannel': 'true', 'response': 'true'}))
                        print("Succesfully connected with KuCoin socket")
                        while True:
                        # listener loop
                            try:
                                reply = await ws.recv()
                                await self.on_msg(reply)
                            except (websockets.exceptions.ConnectionClosed):
                                print("KuCoin: Connection Closed")
                                break
                                # Maybe ping the server
                except ConnectionRefusedError:
                    print("KuCoin: Connection Refused")
                    # Should reconnect after a bit
                    
                # For some reason this always happens at startup, so ignore it
                except asyncio.TimeoutError:
                    continue
        else:
            print("Error getting KuCoin response")
       
class Exchanges(commands.Cog):    
    def __init__(self, bot, db=get_db('portfolio')):
        self.bot = bot
        self.trades_channel = get_channel(self.bot, config["TRADES"]["CHANNEL"])  
                
        # Start getting trades
        asyncio.create_task(self.trades(db))      
        
        # Refresh assets
        asyncio.create_task(self.assets(db))
    
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
                            

    async def assets(self, db=get_db('portfolio')):
        """ 
        Only do this function at startup and if a new portfolio has been added
        Checks the account balances of accounts saved in portfolio db, then updates the assets db
        Posts an overview of everyone's assets in their asset channel
        """
        
        if db.equals(get_db('portfolio')):
             # Make a new assets db, since this call is for restarting the bot
            assets_db = pd.DataFrame({'asset':[],'owned':[],'exchange':[], 'id':[], 'user':[]})
        else:
            # Add it to the old assets db, since this call is for a specific person
            assets_db = get_db('assets')
           
        if not db.empty:
            
            # Divide per exchange
            binance = db.loc[db['exchange'] == 'binance']
            kucoin = db.loc[db['exchange'] == 'kucoin']
            
            if not binance.empty:
                for _, row in binance.iterrows():
                    # Add this data to the assets.pkl database                    
                    assets_db = pd.concat([assets_db, Binance(self.bot, row, None).get_data()], ignore_index=True)
                        
            if not kucoin.empty:
                for _, row in kucoin.iterrows():                    
                    assets_db = pd.concat([assets_db, KuCoin(self.bot, row, None).get_data()], ignore_index=True)
                    
        # Sum values where assets and names are the same
        assets_db = assets_db.astype({'asset':'string', 'owned':'float64', 'exchange':'string', 'id':'int64', 'user':'string'})
                    
        # Update the assets db
        update_db(assets_db, 'assets')
        print("Updated assets database")
        
        self.post_assets.start()

    @loop(hours=12)
    async def post_assets(self):        
        assets_db = get_db('assets')
        guild = get_guild(self.bot)
        
        # Use the user name as channel
        names = assets_db['user'].unique()
            
        for name in names:
            channel_name = '🌟┃' + name.lower()
                        
            # If this channel does not exist make it
            channel = get_channel(self.bot, channel_name)
            if channel is None:
                channel = await guild.create_text_channel(channel_name)
                print(f"Created channel {channel_name}")
                
            # Get the data
            assets = assets_db.loc[assets_db['user'] == name]
            
            if not assets.empty:
                e = discord.Embed(
                    title=f"{name}'s crypto assets",
                    description="",
                    color=0x1DA1F2,
                )
                
                e.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)
                
                # Divide it per exchange
                binance = assets.loc[assets['exchange'] == 'binance']
                kucoin = assets.loc[assets['exchange'] == 'kucoin']
                
                # Add the binance info
                if not binance.empty:
                    # Sort and clean the data
                    sorted_binance = binance.sort_values(by=['owned'], ascending=False)
                    sorted_binance = sorted_binance.round({'owned':3})
                    binance = sorted_binance.drop(sorted_binance[sorted_binance.owned == 0].index)
                                        
                    b_assets = "\n".join(binance['asset'].to_list())
                    b_owned_floats = binance['owned'].to_list()
                    b_owned = "\n".join(str(x) for x in b_owned_floats)
                    
                    if len(b_assets) > 1024:
                        b_assets = b_assets[:1024].split("\n")[:-1]
                        b_owned = "\n".join(b_owned.split("\n")[:len(b_assets)])
                        b_assets = "\n".join(b_assets)
                    elif len(b_owned) > 1024:
                        b_owned = b_owned[:1024].split("\n")[:-1]
                        b_assets = "\n".join(b_assets.split("\n")[:len(b_owned)])
                        b_owned = "\n".join(b_owned)
                    
                    usd_values = []
                    for sym in b_assets.split("\n"):
                        if sym != 'USDT':
                            usd_values.append(Binance(self.bot, None, None).get_usd_price(sym))
                        else:
                            usd_values.append(1)

                    values = [str(round(x*y,2)) for x,y in zip(b_owned_floats, usd_values)]
                    values = "\n".join(values)
                    
                    e.add_field(name="Binance Coins", value=b_assets, inline=True)
                    e.add_field(name="Amount Owned", value=b_owned, inline=True)
                    e.add_field(name="USD Value", value=values, inline=True)
                
                if not kucoin.empty:
                    sorted_kucoin = kucoin.sort_values(by=['owned'], ascending=False)
                    sorted_kucoin = sorted_kucoin.round({'owned':3})
                    kucoin = sorted_kucoin.drop(sorted_kucoin[sorted_kucoin.owned == 0].index)
                    
                    k_assets = "\n".join(kucoin['asset'].to_list())
                    k_owned_floats = kucoin['owned'].to_list()
                    k_owned = "\n".join(str(x) for x in k_owned_floats)

                    if len(k_assets) > 1024:
                        k_assets = k_assets[:1024].split("\n")[:-1]
                        k_owned = "\n".join(k_owned.split("\n")[:len(k_assets)])
                        k_assets = "\n".join(k_assets)
                    elif len(k_owned) > 1024:
                        k_owned = k_owned[:1024].split("\n")[:-1]
                        k_assets = "\n".join(k_assets.split("\n")[:len(k_owned)])
                        k_owned = "\n".join(k_owned)
                    
                    usd_values = []
                    for sym in k_assets.split("\n"):
                        if sym != 'USDT':
                            usd_values.append(KuCoin(self.bot, None, None).get_quote_price(sym+'-USDT'))
                        else:
                            usd_values.append(1)
                            
                    values = [str(round(x*y,2)) for x,y in zip(k_owned_floats, usd_values)]
                    values = "\n".join(values)
                    
                    e.add_field(name="Kucoin Coins", value=k_assets, inline=True)
                    e.add_field(name="Amount Owned", value=k_owned, inline=True)
                    e.add_field(name="USD Value", value=values, inline=True)
                    
                await channel.send(embed=e)  

        
def setup(bot):
    bot.add_cog(Exchanges(bot))