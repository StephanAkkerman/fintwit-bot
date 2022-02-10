##> Imports
import os
import requests
import traceback
import asyncio
import threading
import time
import hmac
import base64
import hashlib

# > 3rd Party Dependencies
from discord.ext import commands
from discord.ext.tasks import loop
import pandas as pd
from websocket import WebSocketApp

def get_db():
    pickle_loc = "data/portfolio.pkl"
    
    if os.path.exists(pickle_loc):
        return pd.read_pickle(pickle_loc)
    else:
        # If it does not exist return an empty dataframe
        return pd.DataFrame()
    
def update_db(db):
    pickle_loc = "data/portfolio.pkl"
    db.to_pickle(pickle_loc)
    
def binance_msg(ws, msg):
    if "executionReport" in msg.keys():
        symbol = msg["s"]
        # Market buy
        operation = f"{msg['o']} {msg['s']}"
        quantity = msg['q']
        price = msg['L']
        
def kucoin_msg(ws,msg):
    print(msg)
    
def on_open(ws):
    print("### opened ###")
    
def on_close(ws):
    print("### closed ###")

class Portfolio(commands.Cog):    
    def __init__(self, bot):
        self.bot = bot
        
        # Start user sockets
        asyncio.create_task(self.trades())

    @commands.command()
    @commands.dm_only()
    async def portfolio(self, ctx, *input):
        """
        Adds your portfolio to the database
        Usage: `!portfolio <exchange> <key> <secret> (<passphrase>)`
        """
        
        if input:
            print(input[0].lower())

            if len(input) == 3:
                if input[0].lower() == 'binance':
                    exchange, key, secret = input
                    passphrase = None
                else:
                    raise commands.BadArgument()
            if len(input) == 4:
                if input[0].lower() == 'kucoin': 
                    exchange, key, secret, passphrase = input
                else:
                    raise commands.BadArgument()
            if len(input) < 3 or len(input) > 4:
                raise commands.UserInputError()
        
            new_data = pd.DataFrame({'user': ctx.message.author.id, 'exchange': exchange.lower(), 'key': key, 'secret': secret, 'passphrase': passphrase}, index=[0])
            update_db(pd.concat([get_db(),new_data], ignore_index=True))
            await ctx.send("Succesfully added your portfolio to the database!")
            
            # Open a websocket connection
            await self.trades(new_data)

        else:
            raise commands.UserInputError()
        
    @portfolio.error
    async def portfolio_error(self, ctx, error):
        print(traceback.format_exc())
        if isinstance(error, commands.BadArgument):
            await ctx.send(f"{ctx.author.mention} The exchange you specified is currently not supported! \nSupported exchanges: Kucoin, Binance")
        elif isinstance(error, commands.UserInputError):
            await ctx.send(f"{ctx.author.mention} You must specify an exchange, key, and secret!")
        elif isinstance(error, commands.PrivateMessageOnly):
            await ctx.message.author.send(
                "Please only use the `!portfolio` command in private messages for security reasons."
            )
        else:
            await ctx.send(
                f"{ctx.author.mention} An error has occurred. Please try again later."
            )
            
    async def trades(self, db=get_db()):     
        if not db.empty:
            binance = pd.DataFrame()#db.loc[db['exchange'] == 'binance']
            kucoin = db.loc[db['exchange'] == 'kucoin']
            
            # Documentation: https://github.com/binance/binance-spot-api-docs/blob/master/user-data-stream.md
            if not binance.empty:
                for _, row in binance.iterrows():
                    headers = {'X-MBX-APIKEY': row['key']}
                    listen_key = requests.post(url = 'https://api.binance.com/api/v3/userDataStream', headers=headers).json()
                    
                    if 'listenKey' in listen_key.keys():
                        binance_user_data = f'wss://stream.binance.com:9443/ws/{listen_key["listenKey"]}'
                        ws = WebSocketApp(binance_user_data, on_message=binance_msg, on_open=on_open, on_close=on_close)
                        # ws.run_forever() is blocking, use https://stackoverflow.com/questions/29145442/threaded-non-blocking-websocket-client
                        wst = threading.Thread(target=ws.run_forever)
                        wst.daemon = True
                        wst.start()
                        
            if not kucoin.empty:
                for _, row in kucoin.iterrows():
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
                        
                        # or try wss://push1-v2.kucoin.com/endpoint
                        kucoin_user_data = f'wss://ws-api.kucoin.com/endpoint?token={token}'
                        ws = WebSocketApp(kucoin_user_data, on_message=kucoin_msg, on_open=on_open, on_close=on_close)
                        ws.run_forever()
                    else:
                        print("Error getting KuCoin response")
                    
    async def reset_connection(self):
        pass
        
    @loop(hours=1)
    async def assets(self):
        pass

def setup(bot):
    bot.add_cog(Portfolio(bot))
