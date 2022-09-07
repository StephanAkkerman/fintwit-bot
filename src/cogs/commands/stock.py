##> Imports
import datetime

# > 3rd Party Dependencies
import pandas as pd
import yfinance as yf

# Discord imports
import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup, Option

# Local dependencies
from util.vars import config
from util.db import DB_info, update_db
from util.disc_util import get_channel
from util.confirm_stock import confirm_stock


class Stock(commands.Cog):
    """
    This class handles the `/stock` command.

    Methods
    -------
    stock_trade_msg(user : discord.User, side : str, stock_name : str, price : str, quantity : str) -> None:
        The message to be sent in the trades channel, after issuing the `!stock` command.
    stock(ctx : commands.context.Context, *input : tuple) -> None:
        Handles the `!stock` command.
    stock_error(ctx : commands.context.Context, error : Exception) -> None:
        Reports the errors when using the `!stock` command.
    """

    # Create a slash command group
    stocks = SlashCommandGroup("stock", description="Add stocks to your portfolio.")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = get_channel(self.bot, config["LOOPS"]["TRADES"]["CHANNEL"])

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
        DB_info.set_assets_db(new_db)

        # Write to SQL database
        update_db(new_db, "assets")

    async def stock_trade_msg(
        self, user: discord.User, side: str, stock_name: str, price: str, quantity: str
    ) -> None:
        """
        Posts a message in the trades channel specifying a user's trade.

        Parameters
        ----------
        user : discord.User
            The user who made the trade.
        side : str
            Buy or sell.
        stock_name : str
            The ticker of the traded stock.
        price : str
            The price of the traded stock.
        quantity : str
            The amount bought or sold.

        Returns
        -------
        None
        """

        e = discord.Embed(
            title=f"{side} {quantity} {stock_name} for ${price}",
            description="",
            color=0x720E9E,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        e.set_author(name=user.name, icon_url=user.avatar_url)
        e.add_field(name="Price", value=f"${price}", inline=True)
        e.add_field(name="Amount", value=quantity, inline=True)
        e.add_field(
            name="$ Worth", value=f"${float(quantity)*float(price)}", inline=True
        )

        e.set_footer(
            icon_url="https://s.yimg.com/cv/apiv2/myc/finance/Finance_icon_0919_250x252.png",
        )

        await self.channel.send(embed=e)

    @stocks.command(name="add", description="Add a stock to your portfolio.")
    async def add(
        self,
        ctx: commands.Context,
        input: Option(
            str, description="Provide the following: <ticker> <amount>`", required=True
        ),
    ) -> None:

        """
        Add stocks to your portfolio.
        Usage:
        `/stock add <ticker> <amount>` to add a stock to your portfolio


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

        # Split the input using the spaces
        input = input.split(" ")
        
        if len(input) < 2 or len(input) >2:
            await ctx.respond("Please provide a ticker and amount.")
            return

        ticker, amount = input

        # Make sure that the user is aware of this stock's existence
        if not await confirm_stock(self.bot, ctx, ticker):
            return

        # Add ticker to database
        new_data = pd.DataFrame(
            {
                "asset": ticker.upper(),
                "owned": int(amount),
                "exchange": "stock",
                "id": ctx.message.author.id,
                "user": ctx.message.author.name,
            },
            index=[0],
        )

        old_db = DB_info.get_assets_db()

        # Check if the user has this asset already
        owned_in_db = old_db.loc[
            (old_db["id"] == ctx.message.author.id)
            & (old_db["asset"] == ticker.upper())
        ]
        if owned_in_db.empty:
            self.update_assets_db(
                pd.concat([old_db, new_data], ignore_index=True)
            )
        else:
            old_db.loc[
                (old_db["id"] == ctx.message.author.id)
                & (old_db["asset"] == ticker.upper()),
                "owned",
            ] += int(amount)
            self.update_assets_db(old_db)
        await ctx.send("Succesfully added your stock to the database!")

        stock_info = yf.Ticker(ticker)

        # Send message in trades channel
        await self.stock_trade_msg(
            ctx.message.author,
            "Bought",
            ticker,
            stock_info.info["regularMarketPrice"],
            amount,
        )


    @stocks.command(
        name="remove", description="Remove a specific stock from your portfolio."
    )
    async def remove(self, ctx: commands.Context, input: Option(str, description="Provide the following information: <ticker> (<amount>)", required=True)) -> None:
        """
        Usage:
        `!stock remove <ticker> (<amount>)` to remove a stock from your portfolio
        """
        
        # Split the input using the spaces
        input = input.split(" ")
        ticker = input[0]
        
        if len(input) < 1 or len(input) > 2:
            await ctx.respond("Please provide at least a ticker and possibly an amount.")
            return
                
        if len(input) == 1:
            old_db = DB_info.get_assets_db()
            row = old_db.index[
                (old_db["id"] == ctx.message.author.id)
                & (old_db["asset"] == ticker)
            ]

            # Update database
            if not row.empty:
                self.update_assets_db(old_db.drop(index=row))
                await ctx.respond(
                    f"Succesfully removed all {ticker.upper()} from your owned stocks!"
                )
            else:
                await ctx.respond("You do not own this stock!")

        elif len(input) == 2:
            amount = input[1]
            old_db = DB_info.get_assets_db()

            row = old_db.loc[
                (old_db["id"] == ctx.message.author.id)
                & (old_db["asset"] == ticker)
            ]

            # Update database
            if not row.empty:
                # Check the amount owned
                owned_now = row["owned"].tolist()[0]
                # if it is equal to or greater than the amount to remove, remove all
                if int(amount) >= owned_now:
                    self.update_assets_db(old_db.drop(index=row.index))
                    await ctx.respond(
                        f"Succesfully removed all {ticker.upper()} from your owned stocks!"
                    )
                else:
                    old_db.loc[
                        (old_db["id"] == ctx.message.author.id)
                        & (old_db["asset"] == ticker.upper()),
                        "owned",
                    ] -= int(amount)
                    self.update_assets_db(old_db)
                    await ctx.respond(
                        f"Succesfully removed {amount} {ticker.upper()} from your owned stocks!"
                    )

                # Send message in trades channel
                await self.stock_trade_msg(
                    ctx.message.author,
                    "Sold",
                    ticker,
                    yf.Ticker(ticker).info["regularMarketPrice"],
                    amount,
                )

            else:
                await ctx.respond("You do not own this stock!")

    @stocks.command(name="show", description="Show the stocks in your portfolio.")
    async def show(self, ctx: commands.Context) -> None:
        """
        Usage:
        `!stock show` to show the stocks in your portfolio
        """
        db = DB_info.get_assets_db()
        rows = db.loc[
            (db["id"] == ctx.message.author.id) & (db["exchange"] == "stock")
        ]
        if not rows.empty:
            for _, row in rows.iterrows():
                # Maybe send this an embed
                await ctx.respond(
                    f"Stock: {row['asset'].upper()} \nAmount: {row['owned']}"
                )
        else:
            await ctx.respond("You do not have any stocks")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Stock(bot))
