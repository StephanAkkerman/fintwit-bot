##> Imports
import traceback

# > 3rd Party Dependencies
from discord.ext import commands
import pandas as pd

# Local dependencies
from util.db import get_db, update_db
from cogs.loops.trades import Exchanges
from cogs.loops.assets import Assets


class Portfolio(commands.Cog):
    """
    This class is used to handle the portfolio command.

    Methods
    ----------
    portfolio(ctx : commands.context.Context, *input : tuple) -> None:
        Adds or removes your portfolio to the database.
    portfolio_error(ctx : commands.context.Context, *input : tuple) -> None:
        Handles the errors when using the `!portfolio` command.
    """
    
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.dm_only()
    async def portfolio(self, ctx : commands.context.Context, *input : tuple) -> None:
        """
        Adds or removes your portfolio to the database.
        Usage: 
        `!portfolio add <exchange> <key> <secret> (<passphrase>)` to add your portfolio to the database.
        `!portfolio remove (<exchange>)` if exchange is not specified, all your portfolio(s) will be removed.
        `!portfolio show` to show your portfolio(s) in our database.
        
        Parameters
        ----------
        ctx : commands.context.Context
            The context of the command, for instance the user who used it.
        input : tuple
            The information specified after `!portfolio`.
        """

        if input:
            if input[0] == "add":
                if len(input) == 4:
                    if input[1].lower() == "binance":
                        _, exchange, key, secret = input
                        passphrase = None
                    else:
                        raise commands.BadArgument()
                elif len(input) == 5:
                    if input[1].lower() == "kucoin":
                        _, exchange, key, secret, passphrase = input
                    else:
                        raise commands.BadArgument()
                elif len(input) < 4 or len(input) > 5:
                    raise commands.UserInputError()

                new_data = pd.DataFrame(
                    {
                        "id": ctx.message.author.id,
                        "user": ctx.message.author.name,
                        "exchange": exchange.lower(),
                        "key": key,
                        "secret": secret,
                        "passphrase": passphrase,
                    },
                    index=[0],
                )
                update_db(
                    pd.concat([get_db("portfolio"), new_data], ignore_index=True),
                    "portfolio",
                )
                await ctx.send("Succesfully added your portfolio to the database!")

                # Init Exchanges to start websockets
                Exchanges(self.bot, new_data)
                # Post the assets
                Assets(self.bot, new_data)

            elif input[0] == "remove":
                old_db = get_db("portfolio")
                if len(input) == 1:
                    rows = old_db.index[old_db["id"] == ctx.message.author.id].tolist()
                elif len(input) > 2:
                    rows = old_db.index[
                        (old_db["id"] == ctx.message.author.id)
                        & (old_db["exchange"] == input[1])
                    ].tolist()

                # Update database
                update_db(old_db.drop(index=rows), "portfolio")
                await ctx.send("Succesfully removed your portfolio from the database!")

                # Maybe unsubribe from websockets

            elif input[0] == "show":
                db = get_db("portfolio")
                rows = db.loc[db["id"] == ctx.message.author.id]
                if not rows.empty:
                    for _, row in rows.iterrows():
                        await ctx.send(
                            f"Exchange: {row['exchange']} \nKey: {row['key']} \nSecret: {row['secret']}"
                        )
                else:
                    await ctx.send("Your portfolio could not be found")

            else:
                await ctx.send(
                    "Please use one of the following keywords: 'add', 'remove', 'show'"
                )
        else:
            raise commands.UserInputError()

    @portfolio.error
    async def portfolio_error(self, ctx : commands.context.Context, error : Exception) -> None:
        print(traceback.format_exc())
        if isinstance(error, commands.BadArgument):
            await ctx.send(
                f"{ctx.author.mention} The exchange you specified is currently not supported! \nSupported exchanges: Kucoin, Binance"
            )
        elif isinstance(error, commands.UserInputError):
            await ctx.send(
                f"{ctx.author.mention} If using `portfolio add`, you must specify an exchange, key, secret, and optionally a passphrase!"
            )
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
