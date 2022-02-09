##> Imports
import os
from traceback import format_exc

# > 3rd Party Dependencies
from discord.ext import commands
import pandas as pd

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

class Portfolio(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
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
                update_db(get_db().append({'user': ctx.message.author.id, 'exchange': exchange, 'key': key, 'secret': secret}, ignore_index=True))
                await ctx.send("Succesfully added your portfolio to the database!")
            else:
                raise commands.BadArgument()
        else:
            raise commands.UserInputError()
        
    @portfolio.error
    async def portfolio_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(f"{ctx.author.mention} The exchange you specified is currently not supported! \nSupported exchanges: Kucoin, Binance")
        if isinstance(error, commands.UserInputError):
            await ctx.send(f"{ctx.author.mention} You must specify an exchange, key, and secret!")
        else:
            await ctx.send(
                f"{ctx.author.mention} An error has occurred. Please try again later."
            )

def setup(bot):
    bot.add_cog(Portfolio(bot))
