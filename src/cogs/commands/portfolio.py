##> Imports
import traceback

# > 3rd Party Dependencies
import pandas as pd

# > Discord dependencies
from discord.ext import commands
from discord.commands import SlashCommandGroup, Option

# Local dependencies
import util.vars
from util.db import update_db
from cogs.loops.trades import Trades
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

    # Create a slash command group
    portfolios = SlashCommandGroup("portfolio", description="Manage your portfolio.")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def update_portfolio_db(self, new_db):

        # Set the new portfolio so other functions can access it
        util.vars.portfolio_db = new_db

        # Write to SQL database
        update_db(new_db, "portfolio")

    @commands.dm_only()
    @portfolios.command(name="add", description="Add a portfolio to the database.")
    async def add(
        self,
        ctx: commands.Context,
        input: Option(
            str,
            description="Provide the follow information: <exchange> <key> <secret> (<passphrase>).",
            required=True,
        ),
    ) -> None:
        """
        Adds your portfolio to the database.

        Usage:
        `/portfolio add <exchange> <key> <secret> (<passphrase>)` to add your portfolio to the database.

        Parameters
        ----------
        ctx : commands.context.Context
            The context of the command, for instance the user who used it.
        input : tuple
            The information specified after `!portfolio`.
        """

        # Split the input using the spaces
        input = input.split(" ")

        if len(input) < 3 or len(input) > 4:
            raise commands.UserInputError()

        exchange = input[0]
        key = input[1]
        secret = input[2]

        # Check if the exchange is supported
        if exchange.lower() not in ["binance", "kucoin"]:
            raise commands.BadArgument()

        # Set the passphrase if necessary
        if exchange.lower() == "kucoin":
            if len(input) == 4:
                passphrase = input[3]
            else:
                raise commands.BadArgument()

        if exchange.lower() == "binance":
            if len(input) != 3:
                raise commands.BadArgument()

        new_data = pd.DataFrame(
            {
                "id": ctx.author.id,
                "user": ctx.message.author.name,
                "exchange": exchange.lower(),
                "key": key,
                "secret": secret,
                "passphrase": passphrase,
            },
            index=[0],
        )

        # Update the databse
        util.vars.portfolio_db = pd.concat(
            [util.vars.portfolio_db, new_data], ignore_index=True
        )

        await ctx.respond(
            "Succesfully added your portfolio to the database!\nPlease ensure that you set the API for read-only access."
        )

        # Init Exchanges to start websockets
        Trades(self.bot, new_data)
        # Post the assets
        Assets(self.bot, new_data)

    @portfolios.command(
        name="remove", description="Remove a portfolio to the database."
    )
    async def remove(
        self,
        ctx: commands.Context,
        exchange: Option(
            str,
            description="The name of the exchange that you want to remove, if left empty all will be removed.",
            required=True,
        ),
    ) -> None:
        """
        `/portfolio remove (<exchange>)` if exchange is not specified, all your portfolio(s) will be removed.
        """

        old_db = util.vars.portfolio_db
        if exchange:
            rows = old_db.index[
                (old_db["id"] == ctx.author.id) & (old_db["exchange"] == exchange)
            ].tolist()
        else:
            rows = old_db.index[old_db["id"] == ctx.author.id].tolist()            

        # Update database
        self.update_portfolio_db(old_db.drop(rows))

        await ctx.respond("Succesfully removed your portfolio from the database!")

        # Maybe unsubscribe from websockets

    @commands.dm_only()
    @portfolios.command(
        name="show", description="Show the portfolio(s) in the database."
    )
    async def show(
        self,
        ctx: commands.Context,
    ) -> None:
        """
        `!portfolio show` to show your portfolio(s) in our database.
        """

        db = util.vars.portfolio_db
        rows = db.loc[db["id"] == ctx.author.id]
        if not rows.empty:
            for _, row in rows.iterrows():
                await ctx.respond(
                    f"Exchange: {row['exchange']} \nKey: {row['key']} \nSecret: {row['secret']}"
                )
        else:
            await ctx.respond("Your portfolio could not be found")

    @add.error
    async def add_error(self, ctx: commands.Context, error: Exception) -> None:
        #print(traceback.format_exc())
        if isinstance(error, commands.BadArgument):
            await ctx.respond(
                f"The exchange you specified is currently not supported! \nSupported exchanges: Kucoin, Binance"
            )
        elif isinstance(error, commands.UserInputError):
            await ctx.respond(
                f"If using `/portfolio add`, you must specify an exchange, key, secret, and optionally a passphrase!"
            )
        elif isinstance(error, commands.PrivateMessageOnly):
            await ctx.respond(
                "Please only use the `/portfolio` command in private messages for security reasons."
            )
        else:
            await ctx.respond(f"An error has occurred. Please try again later.")

    @remove.error
    async def remove_error(self, ctx: commands.Context, error: Exception) -> None:
        #print(traceback.format_exc())
        await ctx.respond(f"An error has occurred. Please try again later.")

    @show.error
    async def show_error(self, ctx: commands.Context, error: Exception) -> None:
        #print(traceback.format_exc())
        if isinstance(error, commands.PrivateMessageOnly):
            await ctx.respond(
                "Please only use the `/portfolio` command in private messages for security reasons."
            )
        else:
            await ctx.respond(f"An error has occurred. Please try again later.")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Portfolio(bot))
