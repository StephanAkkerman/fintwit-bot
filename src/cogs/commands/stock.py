import discord
import pandas as pd
from discord.commands import SlashCommandGroup
from discord.commands.context import ApplicationContext
from discord.ext import commands

import util.vars
from api.yahoo import get_ohlcv
from constants.config import config
from constants.logger import logger
from util.confirm_stock import confirm_stock
from util.db import merge_and_update, update_db
from util.disc import get_channel, log_command_usage
from util.trades_msg import trades_msg


class Stock(commands.Cog):
    """
    This class handles the `/stock` command.
    You can enable / disable this command in the config, under ["COMMANDS"]["STOCK"].
    """

    # Create a slash command group
    stocks = SlashCommandGroup("stock", description="Add stocks to your portfolio.")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = None

    def update_assets_db(self, new_db):
        """
        Updates the assets database.

        Parameters
        ----------
        new_db : pandas.DataFrame
            The new database to be written to the assets database.

        Returns
        -------
        None
        """

        # Set the new portfolio so other functions can access it
        util.vars.assets_db = new_db

        # Write to SQL database
        update_db(new_db, "assets")

    @stocks.command(name="add", description="Add a stock to your portfolio.")
    @discord.option(
        "ticker",
        type=str,
        description="The ticker of the stock e.g., AAPL.",
        required=True,
    )
    @discord.option(
        "buying_price",
        type=str,
        description="The price of the stock when you bought it, e.g., 106.40",
        required=True,
    )
    @discord.option(
        "amount",
        type=str,
        description="The amount of stocks that you own at this price, e.g., 2",
        required=True,
    )
    @log_command_usage
    async def add(
        self,
        ctx: ApplicationContext,
        ticker: str,
        buying_price: str,
        amount: str,
    ) -> None:
        """
        Add stocks to your portfolio.
        Usage:
        `/stock add <ticker> <buying price> <amount>` to add a stock to your portfolio


        Parameters
        ----------
        ctx : commands.context.Context
            The context of the command, such as the user who used it.
        input : tuple
            The keywords used following the `!stock` command.

        Returns
        -------
        None
        """
        await ctx.response.defer(ephemeral=True)

        if self.channel is None:
            self.channel = await get_channel(
                self.bot, config["LOOPS"]["TRADES"]["CHANNEL"]
            )

        # Make sure that the user is aware of this stock's existence
        if not await confirm_stock(self.bot, ctx, ticker):
            return

        try:
            amount = float(amount)
            buying_price = float(buying_price)
        except Exception:
            await ctx.respond("Please provide a valid buying price and/or amount.")
            return

        try:
            price = get_ohlcv(ticker)["Close"]
        except Exception:
            price = 0
            logger.error(f"Could not get price for {ticker} when using /stock add")

        # Add ticker to database
        new_data = pd.DataFrame(
            [
                {
                    "asset": ticker.upper(),
                    "buying_price": buying_price,
                    "owned": amount,
                    "exchange": "stock",
                    "id": str(ctx.author.id),
                    "user": ctx.author.name,
                }
            ]
        )

        old_db = util.vars.assets_db

        # Check if the user has this asset already
        owned_in_db = old_db.loc[
            (old_db["id"] == str(ctx.author.id)) & (old_db["asset"] == ticker.upper())
        ]

        # If the user does not yet own this stock
        if owned_in_db.empty:
            util.vars.assets_db = merge_and_update(old_db, new_data, "assets")
        else:
            # Increase the amount if everything is the same
            same_price = old_db.loc[
                (old_db["id"] == str(ctx.author.id))
                & (old_db["asset"] == ticker.upper())
                & (old_db["buying_price"] == buying_price)
            ]

            if not same_price.empty:
                old_db.loc[
                    (old_db["id"] == str(ctx.author.id))
                    & (old_db["asset"] == ticker.upper()),
                    "owned",
                ] += amount

            else:
                # Get the old buying price and average it with the new one
                old_buying_price = float(owned_in_db["buying_price"].values[0])
                old_amount_owned = float(owned_in_db["owned"].values[0])

                new_buying_price = (
                    old_buying_price * old_amount_owned + buying_price * amount
                ) / (old_amount_owned + amount)

                # Update the buying price and amount owned
                old_db.loc[
                    (old_db["id"] == str(ctx.author.id))
                    & (old_db["asset"] == ticker.upper()),
                    "buying_price",
                ] = new_buying_price

                # Update the amount owned
                old_db.loc[
                    (old_db["id"] == str(ctx.author.id))
                    & (old_db["asset"] == ticker.upper()),
                    "owned",
                ] += amount

            self.update_assets_db(old_db)
        await ctx.respond("Succesfully added your stock to the database!")

        # Send message in trades channel
        await trades_msg(
            "stocks",
            self.channel,
            ctx.author,
            ticker,
            "buy",
            "market",
            buying_price,
            amount,
            round(price * amount, 2),
            None,
        )

    @stocks.command(
        name="remove", description="Remove a specific stock from your portfolio."
    )
    @discord.option(
        "ticker",
        type=str,
        description="The ticker of the stock e.g., AAPL.",
        required=True,
    )
    @discord.option(
        "amount",
        type=str,
        description="The amount of stocks that you want to delete, e.g., 2",
        required=False,
    )
    @log_command_usage
    async def remove(
        self,
        ctx: ApplicationContext,
        ticker: str,
        amount: str,
    ) -> None:
        """
        Usage:
        `/stock remove <ticker> (<amount>)` to remove a stock from your portfolio
        """
        await ctx.response.defer(ephemeral=True)

        if self.channel is None:
            self.channel = await get_channel(
                self.bot, config["LOOPS"]["TRADES"]["CHANNEL"]
            )

        old_db = util.vars.assets_db

        if not amount:
            row = old_db.index[
                (old_db["id"] == str(ctx.author.id)) & (old_db["asset"] == ticker)
            ]

            # Update database
            if not row.empty:
                amount = old_db.loc[row, "owned"].values[0]
                self.update_assets_db(old_db.drop(index=row))
                await ctx.respond(
                    f"Succesfully removed all {ticker.upper()} from your owned stocks!"
                )
            else:
                await ctx.respond("You do not own this stock!")
                return

        else:
            try:
                amount = float(amount)
            except Exception:
                await ctx.respond("Please provide a valid amount.")
                return

            row = old_db.loc[
                (old_db["id"] == str(ctx.author.id)) & (old_db["asset"] == ticker)
            ]

            # Update database
            if not row.empty:
                # Check the amount owned
                owned_now = row["owned"].tolist()[0]
                # if it is equal to or greater than the amount to remove, remove all
                if float(amount) >= owned_now:
                    self.update_assets_db(old_db.drop(index=row.index))
                    await ctx.respond(
                        f"Succesfully removed all {ticker.upper()} from your owned stocks!"
                    )
                else:
                    old_db.loc[
                        (old_db["id"] == str(ctx.author.id))
                        & (old_db["asset"] == ticker.upper()),
                        "owned",
                    ] -= float(amount)
                    self.update_assets_db(old_db)
                    await ctx.respond(
                        f"Succesfully removed {amount} {ticker.upper()} from your owned stocks!"
                    )
            else:
                await ctx.respond("You do not own this stock!")
                return

        try:
            price = get_ohlcv(ticker)["Close"]
        except Exception:
            price = 0

        buying_price = row["buying_price"].tolist()[0]

        # Send message in trades channel
        await trades_msg(
            "stocks",
            self.channel,
            ctx.author,
            ticker,
            "sold",
            "market",
            price,
            amount,
            round(price * amount, 2),
            buying_price,
        )

    @stocks.command(name="show", description="Show the stocks in your portfolio.")
    @log_command_usage
    async def show(self, ctx: ApplicationContext) -> None:
        """
        Usage:
        `/stock show` to show the stocks in your portfolio
        """
        await ctx.response.defer(ephemeral=True)

        db = util.vars.assets_db
        rows = db.loc[(db["id"] == str(ctx.author.id)) & (db["exchange"] == "stock")]
        if not rows.empty:
            for _, row in rows.iterrows():
                # TODO: send this as 1 embed
                await ctx.respond(
                    f"Stock: {row['asset'].upper()} \nAmount: {row['owned']} \nBuying price: {row['buying_price']}"
                )
        else:
            await ctx.respond("You do not have any stocks")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Stock(bot))
