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
        Adds your portfolio to the database
        Usage: `!portfolio <exchange> <key> <secret> (<passphrase>)`
        """
        
        if input:
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

            # Call trades to add this new data for websockets
            self.exchanges.trades(new_data)
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
