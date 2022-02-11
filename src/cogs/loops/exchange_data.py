##> Imports
import requests
import asyncio
import threading
import time
import hmac
import base64
import json
import hashlib

# > 3rd Party Dependencies
import pandas as pd
from discord.ext import commands
from discord.ext.tasks import loop
from websocket import WebSocketApp

# Local dependencies
from util.db import get_db, update_db
from util.disc_util import get_channel
from util.vars import config

class Binance_Socket():
    def __init__(self, bot, row, trades_channel):
        self.bot = bot
        self.trades_channel = trades_channel
        
        self.user = row["user"]
        self.key = row["key"]
        self.secret = row["secret"]
        
    def on_open(ws):
        print("Started Binance Socket")
        
    def on_close(ws):
        print("Closed Binance Socket")
        
    def on_msg(self, ws, msg):
        if "executionReport" in msg.keys():
            sym = msg["s"]  # ie 'YFIUSDT'
            side = msg["S"]  # ie 'BUY', 'SELL'
            orderType = msg["o"]  # ie 'LIMIT', 'MARKET', 'STOP_LOSS_LIMIT'
            execType = msg["x"]  # ie 'TRADE', 'NEW' or 'CANCELLED'
            execPrice = msg["L"]  # The latest price it was filled at
            
            # Only care about actual trades
            if execType == "TRADE":
                pass
        
    async def start_sockets(self):
        # Documentation: https://github.com/binance/binance-spot-api-docs/blob/master/user-data-stream.md
        headers = {'X-MBX-APIKEY': self.key}
                    
        listen_key = requests.post(url = 'https://api.binance.com/api/v3/userDataStream', headers=headers).json()
        
        if 'listenKey' in listen_key.keys():
            ws = WebSocketApp(f'wss://stream.binance.com:9443/ws/{listen_key["listenKey"]}',
                                on_message=self.on_msg, 
                                on_open=self.on_open, 
                                on_close=self.on_close)

            # ws.run_forever() is blocking, use https://stackoverflow.com/questions/29145442/threaded-non-blocking-websocket-client
            wst = threading.Thread(target=ws.run_forever, kwargs={'ping_interval':60*30, 'ping_timeout':10*3})
            wst.daemon = True
            wst.start()

class KuCoin_Socket():
    def __init__(self, bot, row, trades_channel):
        self.bot = bot
        self.trades_channel = trades_channel
        
        self.user = row["user"]
        self.key = row["key"]
        self.secret = row["secret"]
        self.passphrase = row["passphrase"]
        
    def on_open(ws):
        print("Started KuCoin Socket")
        
        # Subscribe to tradeOrders
        ws.send(json.dumps({'type': 'subscribe', 'topic': '/spotMarket/tradeOrders', 'privateChannel': 'true', 'response': 'true'}))
        
    def on_close(ws):
        print("Closed KuCoin Socket")   
        
    def on_msg(self, ws, msg):        
        msg = json.loads(msg)
                
        if msg['topic'] == "/spotMarket/tradeOrders":
            data = msg['data']
            symbol = data['symbol']
            operation = f"{data['orderType']} {data['side']}"
            quantity = data['filledSize'] + data['remainSize']
            price = data['matchPrice']
        
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
            
            ws = WebSocketApp(f'wss://ws-api.kucoin.com/endpoint?token={token}', 
                                on_message=self.on_msg,
                                on_open=self.on_open, 
                                on_close=self.on_close)
            
            # Set ping pong
            ping_interval=int(response['data']['instanceServers'][0]['pingInterval']) // 1000
            ping_timeout=int(response['data']['instanceServers'][0]['pingTimeout']) // 1000
            
            wst = threading.Thread(target=ws.run_forever, kwargs={'ping_interval':ping_interval, 'ping_timeout':ping_timeout})
            wst.daemon = True
            wst.start()
            
        else:
            print("Error getting KuCoin response")
    
class Exchanges(commands.Cog):    
    def __init__(self, bot):
        self.bot = bot
        self.trades_channel = get_channel(self.bot, config["TRADES"]["CHANNEL"])         
    
    async def trades(self, db=get_db('portfolio')):     
        if not db.empty:
            
            # Divide per exchange
            binance = db.loc[db['exchange'] == 'binance']
            kucoin = db.loc[db['exchange'] == 'kucoin']
            
            if not binance.empty:
                for _, row in binance.iterrows():
                    await Binance_Socket(self.bot, row, self.trades_channel).start_sockets()
                        
            if not kucoin.empty:
                for _, row in kucoin.iterrows():
                    await KuCoin_Socket(self.bot, row, self.trades_channel).start_sockets()
                    
    async def reset_connection(self):
        pass
        
    @loop(hours=1)
    async def assets(self):
        pass
    
def setup(bot):
    bot.add_cog(Exchanges(bot))