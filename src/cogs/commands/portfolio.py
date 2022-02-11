##> Imports
import traceback
import asyncio

# > 3rd Party Dependencies
from discord.ext import commands
import pandas as pd

# Local dependencies
from util.db import get_db, update_db
from cogs.loops.exchange_data import Exchanges
class Portfolio(commands.Cog):    
    def __init__(self, bot):
        self.bot = bot
        self.exchanges = Exchanges(bot)
        
        # Start getting trades
        asyncio.create_task(self.exchanges.trades())

    @commands.command()
    @commands.dm_only()
    async def portfolio(self, ctx, *input):
        """
        Adds or removes your portfolio to the database
        Usage: 
        `!portfolio add <exchange> <key> <secret> (<passphrase>)` to add your portfolio to the database
        `!portfolio remove (<exchange>)` if exchange is not specified, all your exchanges will be removed
        `!portfolio show` to show your portfolio in our database
        """
        
        if input:
            if input[0] == "add":
                if len(input) == 3:
                    if input[1].lower() == 'binance':
                        _, exchange, key, secret = input
                        passphrase = None
                    else:
                        raise commands.BadArgument()
                elif len(input) == 4:
                    if input[1].lower() == 'kucoin': 
                        _, exchange, key, secret, passphrase = input
                    else:
                        raise commands.BadArgument()
                elif len(input) < 3 or len(input) > 4:
                    raise commands.UserInputError()
            
                new_data = pd.DataFrame({'user': ctx.message.author.id, 'exchange': exchange.lower(), 'key': key, 'secret': secret, 'passphrase': passphrase}, index=[0])
                update_db(pd.concat([get_db('portfolio'),new_data], ignore_index=True), 'portfolio')
                await ctx.send("Succesfully added your portfolio to the database!")

                # Call trades to add this new data for websockets
                self.exchanges.trades(new_data)
                
            elif input[0] == "remove":
                old_db = get_db('portfolio')
                if len(input) == 1:  
                    rows = old_db.index[old_db['user'] == ctx.message.author.id].tolist()
                elif len(input) > 2:
                    rows = old_db.index[(old_db['user'] == ctx.message.author.id) & (old_db['exchange'] == input[1])].tolist()                
                
                # Update database
                update_db(old_db.drop(index=rows), 'portfolio')
                await ctx.send("Succesfully removed your portfolio from the database!")
                
                # Maybe unsubribe from websockets
                
            elif input[0] == "show":
                db = get_db('portfolio')
                rows = db.loc[db['user'] == ctx.message.author.id].tolist()
                await ctx.send("Your portfolio consists of: \n" + str(rows))
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

def setup(bot):
    bot.add_cog(Portfolio(bot))
