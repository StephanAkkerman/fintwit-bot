##> Imports
import os
import requests
import traceback
import asyncio

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
    
def on_message(ws, msg):
    if "executionReport" in msg.keys():
        symbol = msg["s"]
        # Market buy
        operation = f"{msg['o']} {msg['s']}"
        quantity = msg['q']
        price = msg['L']
    
def on_close(ws):
    print("### closed ###")

class Portfolio(commands.Cog):    
    def __init__(self, bot):
        self.bot = bot
        self.binance_ws = 'wss://stream.binance.com:9443/ws'
        
        # Start user sockets
        asyncio.create_task(self.trades())

    @commands.command()
    @commands.dm_only()
    async def portfolio(self, ctx, *input):
        """
        Adds your portfolio to the database
        Usage: `!portfolio <exchange> <key> <secret>`
        """
        
        if input:
            try:
                exchange, key, secret = input
                exchange = exchange.lower()
            except Exception:
                raise commands.UserInputError()
            
            if exchange == 'kucoin' or exchange == 'binance':
                new_data = pd.DataFrame({'user': ctx.message.author.id, 'exchange': exchange, 'key': key, 'secret': secret}, index=[0])
                update_db(pd.concat([get_db(),new_data], ignore_index=True))
                await ctx.send("Succesfully added your portfolio to the database!")
                
                # Open a websocket connection
                await self.trades(new_data)
            else:
                raise commands.BadArgument()
        else:
            raise commands.UserInputError()
        
    @portfolio.error
    async def portfolio_error(self, ctx, error):
        print(traceback.format_exc())
        if isinstance(error, commands.BadArgument):
            await ctx.send(f"{ctx.author.mention} The exchange you specified is currently not supported! \nSupported exchanges: Kucoin, Binance")
        if isinstance(error, commands.UserInputError):
            await ctx.send(f"{ctx.author.mention} You must specify an exchange, key, and secret!")
        if isinstance(error, commands.PrivateMessageOnly):
            await ctx.message.author.send(
                "Please only use the `!portfolio` command in private messages for security reasons."
            )
        else:
            await ctx.send(
                f"{ctx.author.mention} An error has occurred. Please try again later."
            )
            
    async def trades(self, db=get_db()):     
        if not db.empty:
            binance = db.loc[db['exchange'] == 'binance']
            kucoin = db.loc[db['exchange'] == 'kucoin']
            
            # Documentation: https://github.com/binance/binance-spot-api-docs/blob/master/user-data-stream.md
            if not binance.empty:
                for _, row in binance.iterrows():
                    headers = {'X-MBX-APIKEY': row['key']}
                    listen_key = requests.post(url = 'https://api.binance.com/api/v3/userDataStream', headers=headers).json()
                    
                    if 'listenKey' in listen_key.keys():
                        binance_user_data = f'wss://stream.binance.com:9443/ws/{listen_key["listenKey"]}'
                        ws = WebSocketApp(binance_user_data, on_message=on_message, on_close=on_close)
                        # ws.run_forever() is blocking, use https://stackoverflow.com/questions/29145442/threaded-non-blocking-websocket-client
                        ws.run_forever()
                        
            if not kucoin.empty:
                pass
        
    async def reset_connection(self):
        pass
        
    @loop(hours=1)
    async def assets(self):
        pass

def setup(bot):
    bot.add_cog(Portfolio(bot))
