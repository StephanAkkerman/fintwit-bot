# > 3rd Party Dependencies
import pandas as pd
import ccxt
import traceback

# > Discord dependencies
import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup, Option
from discord import Interaction, SelectOption
from discord.ui import Select, View

# Local dependencies
import util.vars
from util.db import update_db
from cogs.loops.trades import Trades
from cogs.loops.assets import Assets


class Portfolio(commands.Cog):
    """
    This class is used to handle the portfolio command.
    You can enable / disable this command in the config, under ["COMMANDS"]["PORTFOLIO"].
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
    @portfolios.command(
        name="add", description="Add a cryptocurrency portfolio to the database."
    )
    async def add(
        self,
        ctx: commands.Context,
        exchange: Option(
            str,
            description="Provide the name of your crypto exchange.",
            required=True,
        ),
        key: Option(
            str,
            description="Provide your API key.",
            required=True,
        ),
        secret: Option(
            str,
            description="Provide your API secret.",
            required=True,
        ),
        passphrase: Option(
            str,
            description="Provide your API passphrase (only used for Kucoin).",
            required=False,
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

        # Check if the exchange is supported
        if exchange.lower() not in ["binance", "kucoin"]:
            raise commands.BadArgument()

        if exchange.lower() == "kucoin":
            if not passphrase:
                raise commands.UserInputError()
            ccxt_exchange = ccxt.kucoin(
                {"apiKey": key, "secret": secret, "password": passphrase}
            )

        elif exchange.lower() == "binance":
            ccxt_exchange = ccxt.binance({"apiKey": key, "secret": secret})

        # Check if the API keys are valid
        status = ccxt_exchange.fetch_status()
        if status["status"] != "ok":
            await ctx.respond(
                f"Your API keys are not valid! Please check your API keys and try again."
            )
            return

        new_data = pd.DataFrame(
            {
                "id": ctx.author.id,
                "user": ctx.author.name,
                "exchange": exchange.lower(),
                "key": key,
                "secret": secret,
                "passphrase": passphrase,
            },
            index=[0],
        )

        # Check if new_data already exists in portfolio_db
        if not util.vars.portfolio_db.empty:  # ensure the DB isn't empty
            # Check for duplicates based on a subset of columns that should be unique together
            # Adjust the subset columns as per your data's unique constraints
            duplicate_entries = util.vars.portfolio_db[
                (util.vars.portfolio_db["user"] == ctx.author.name)
                & (util.vars.portfolio_db["exchange"] == exchange.lower())
                & (util.vars.portfolio_db["key"] == key)
                & (util.vars.portfolio_db["secret"] == secret)
            ]

            if not duplicate_entries.empty:
                # Handle the case where a duplicate is found
                await ctx.respond("This portfolio already exists in the database.")
                return

        # Update the databse
        util.vars.portfolio_db = pd.concat(
            [util.vars.portfolio_db, new_data], ignore_index=True
        )
        update_db(util.vars.portfolio_db, "portfolio")

        await ctx.respond(
            "Succesfully added your portfolio to the database!\n⚠️ Please ensure that you set the API for read-only access ⚠️"
        )

        # Init Exchanges to start websockets
        Trades(self.bot, new_data)
        # Post the assets
        Assets(self.bot, new_data)

    @portfolios.command(
        name="remove", description="Remove a portfolio from the database."
    )
    async def remove(
        self,
        ctx: commands.Context,
    ) -> None:
        """
        `/portfolio remove` to remove a specific portfolio from your list.
        """

        rows = util.vars.portfolio_db[util.vars.portfolio_db["id"] == ctx.author.id]
        if not rows.empty:
            options = []
            for i, (_, row) in enumerate(rows.iterrows()):
                description = f"Exchange: {row['exchange']}"
                options.append(
                    SelectOption(
                        label=f"Portfolio {i+1} - {row['exchange']}",
                        description=description,
                        value=str(i),
                    )
                )

            view = PortfolioSelectView(ctx, util.vars.portfolio_db)
            view.select_portfolio.options = options
            await ctx.respond("Select the portfolio you want to remove:", view=view)
            await view.wait()
        else:
            await ctx.respond("Your portfolio could not be found")

    @commands.dm_only()
    @portfolios.command(
        name="show", description="Show the portfolio(s) in the database."
    )
    async def show(
        self,
        ctx: commands.Context,
    ) -> None:
        """
        `/portfolio show` to show your portfolio(s) in our database.
        """
        rows = util.vars.portfolio_db[util.vars.portfolio_db["id"] == ctx.author.id]
        if not rows.empty:
            for _, row in rows.iterrows():
                response = f"Exchange: {row['exchange']} \nKey: {row['key']} \nSecret: {row['secret']}"

                if row["passphrase"]:
                    response += f"\nPassphrase: {row['passphrase']}"
                await ctx.respond(response)
        else:
            await ctx.respond("Your portfolio could not be found")

    @add.error
    async def add_error(self, ctx: commands.Context, error: Exception) -> None:
        # print(traceback.format_exc())
        if isinstance(error, commands.BadArgument):
            await ctx.respond(
                f"The exchange you specified is currently not supported! \nSupported exchanges: Kucoin, Binance"
            )
        elif isinstance(error, commands.UserInputError):
            await ctx.respond(
                f"If using `/portfolio add` with Kucoin, you must specify a passphrase!"
            )
        elif isinstance(error, commands.PrivateMessageOnly):
            await ctx.respond(
                "Please only use the `/portfolio` command in private messages for security reasons."
            )
        else:
            print(error)
            await ctx.respond(f"An error has occurred. Please try again later.")

    @remove.error
    async def remove_error(self, ctx: commands.Context, error: Exception) -> None:
        # print(traceback.format_exc())
        await ctx.respond(f"An error has occurred. Please try again later.")

    @show.error
    async def show_error(self, ctx: commands.Context, error: Exception) -> None:
        print(traceback.format_exc())
        if isinstance(error, commands.PrivateMessageOnly):
            await ctx.respond(
                "Please only use the `/portfolio` command in private messages for security reasons."
            )
        else:
            await ctx.respond(f"An error has occurred. Please try again later.")


class PortfolioSelectView(View):
    def __init__(self, ctx, portfolio_db):
        super().__init__()
        self.ctx = ctx
        self.portfolio_db = portfolio_db

    @discord.ui.select(placeholder="Select the portfolio to remove")
    async def select_portfolio(self, select: Select, interaction: Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "You are not authorized to confirm this action.", ephemeral=True
            )

        index = int(select.values[0])
        self.portfolio_db.drop(self.portfolio_db.index[index], inplace=True)
        await interaction.response.send_message(
            "Successfully removed the selected portfolio from the database!",
            ephemeral=True,
        )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Portfolio(bot))
