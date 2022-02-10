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
from util.db import get_db

def binance_msg(ws, msg):
    if "executionReport" in msg.keys():
        symbol = msg["s"]
        # Market + buy
        operation = f"{msg['o']} {msg['s']}"
        quantity = msg['q']
        price = msg['L']
        
id = None
def kucoin_msg(ws,msg):
    msg = json.loads(msg)
    
    if msg['topic'] == "/spotMarket/tradeOrders":
        data = msg['data']
        symbol = data['symbol']
        operation = f"{data['orderType']} {data['side']}"
        quantity = data['filledSize'] + data['remainSize']
        price = data['matchPrice']
    
    global id
    
    # Set the global id
    if msg['type'] == 'welcome':
        id = json.loads(ws.recv())['id']

def binance_on_open(ws):
    print("Started Binance Socket")

def kucoin_on_open(ws):
    print("Started KuCoin Socket")
    if id != None:
        ws.send(json.dumps({'id': id, 'type': 'subscribe', 'topic': '/spotMarket/tradeOrders', 'privateChannel': 'true', 'response': 'true'}))
    
def binance_on_close(ws):
    print("Closed Binance Socket")
    
def kucoin_on_close(ws):
    print("Closed KuCoin Socket")   
    
def on_ping(ws, message):
    pass

def on_pong(ws, message):
    pass

class Exchanges(commands.Cog):    
    def __init__(self, bot):
        self.bot = bot
        print("Started exchanges")
        
    async def start_binance_ws(self, row):
        headers = {'X-MBX-APIKEY': row['key']}
                    
        listen_key = requests.post(url = 'https://api.binance.com/api/v3/userDataStream', headers=headers).json()
        
        if 'listenKey' in listen_key.keys():
            ws = WebSocketApp(f'wss://stream.binance.com:9443/ws/{listen_key["listenKey"]}',
                                on_message=binance_msg, 
                                on_open=binance_on_open, 
                                on_close=binance_on_close,
                                on_ping=on_ping, 
                                on_pong=on_pong)

            # ws.run_forever() is blocking, use https://stackoverflow.com/questions/29145442/threaded-non-blocking-websocket-client
            wst = threading.Thread(target=ws.run_forever, kwargs={'ping_interval':60*30, 'ping_timeout':10*3})
            wst.daemon = True
            wst.start()
            
    async def start_kucoin_ws(self, row):
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
            hmac.new(row['secret'].encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest())
        passphrase = base64.b64encode(
            hmac.new(row['secret'].encode('utf-8'), row['passphrase'].encode('utf-8'), hashlib.sha256).digest())
        
        headers = {"KC-API-KEY": row['key'], 
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
                                on_message=kucoin_msg,
                                on_open=kucoin_on_open, 
                                on_close=kucoin_on_close,
                                on_ping=on_ping, 
                                on_pong=on_pong)
            
            # Set ping pong
            ping_interval=int(response['data']['instanceServers'][0]['pingInterval']) // 1000
            ping_timeout=int(response['data']['instanceServers'][0]['pingTimeout']) // 1000
            
            wst = threading.Thread(target=ws.run_forever, kwargs={'ping_interval':ping_interval, 'ping_timeout':ping_timeout})
            wst.daemon = True
            wst.start()
            
        else:
            print("Error getting KuCoin response")
    
    async def trades(self, db=get_db()):     
        if not db.empty:
            binance = db.loc[db['exchange'] == 'binance']
            kucoin = db.loc[db['exchange'] == 'kucoin']
            
            # Documentation: https://github.com/binance/binance-spot-api-docs/blob/master/user-data-stream.md
            if not binance.empty:
                for _, row in binance.iterrows():
                    await self.start_binance_ws(row)
                        
            if not kucoin.empty:
                for _, row in kucoin.iterrows():
                    await self.start_kucoin_ws(row)
                    
    async def reset_connection(self):
        pass
        
    @loop(hours=1)
    async def assets(self):
        pass
    
def setup(bot):
    bot.add_cog(Exchanges(bot))