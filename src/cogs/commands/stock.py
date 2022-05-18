##> Imports
import datetime

# > 3rd Party Dependencies
import pandas as pd
import yfinance as yf

# Discord imports
import discord
from discord.ext import commands


# Local dependencies
from util.vars import config
from util.db import get_db, update_db
from util.disc_util import get_channel


class Stock(commands.Cog):
    """
    This class handles the `!stock` command.

    Methods
    -------
    stock_trade_msg(user : discord.User, side : str, stock_name : str, price : str, quantity : str) -> None:
        The message to be sent in the trades channel, after issuing the `!stock` command.
    stock(ctx : commands.context.Context, *input : tuple) -> None:
        Handles the `!stock` command.
    stock_error(ctx : commands.context.Context, error : Exception) -> None:
        Reports the errors when using the `!stock` command.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = get_channel(self.bot, config["LOOPS"]["TRADES"]["CHANNEL"])

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
            timestamp=datetime.datetime.utcnow(),
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

    @commands.command()
    async def stock(self, ctx: commands.Context, *input: tuple) -> None:
        """
        Add stocks to your portfolio.
        Usage: `!stock <keyword> <amount> [<ticker>]`
        `!stock add <ticker> <amount>` to add a stock to your portfolio
        `!stock remove <ticker>` to remove a stock from your portfolio
        `!stock show` to show your portfolio

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

        if input:
            if input[0] == "add":
                if len(input) == 3:
                    _, ticker, amount = input

                    # Check if this ticker exists
                    stock_info = yf.Ticker(ticker)

                    # If it does not exist let the user know
                    if stock_info.info["regularMarketPrice"] == None:
                        confirm_msg = await ctx.send(
                            (
                                f"Are you sure {ticker} is correct? We could not find it on Yahoo Finance.\n"
                                "Click on \N{WHITE HEAVY CHECK MARK} to continue and on \N{CROSS MARK} to cancel."
                            )
                        )
                        await confirm_msg.add_reaction("\N{WHITE HEAVY CHECK MARK}")
                        await confirm_msg.add_reaction("\N{CROSS MARK}")

                        # Handle preview accept/deny using reactions
                        reaction = await self.bot.wait_for(
                            "reaction_add",
                            check=lambda r, u: (
                                str(r.emoji) == "\N{WHITE HEAVY CHECK MARK}"
                                or str(r.emoji) == "\N{CROSS MARK}"
                            )
                            and u == ctx.author,
                        )

                        if reaction[0].emoji == "\N{CROSS MARK}":
                            await ctx.send(f"Did not add {ticker} to the database.")
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

                    old_db = get_db("assets")

                    # Check if the user has this asset already
                    owned_in_db = old_db.loc[
                        (old_db["id"] == ctx.message.author.id)
                        & (old_db["asset"] == ticker.upper())
                    ]
                    if owned_in_db.empty:
                        update_db(
                            pd.concat([old_db, new_data], ignore_index=True), "assets"
                        )
                    else:
                        old_db.loc[
                            (old_db["id"] == ctx.message.author.id)
                            & (old_db["asset"] == ticker.upper()),
                            "owned",
                        ] += int(amount)
                        update_db(old_db, "assets")
                    await ctx.send("Succesfully added your stock to the database!")

                    # Send message in trades channel
                    await self.stock_trade_msg(
                        ctx.message.author,
                        "Bought",
                        ticker,
                        stock_info.info["regularMarketPrice"],
                        amount,
                    )

                else:
                    await ctx.send("Please specify a ticker and amount!")

            elif input[0] == "remove":
                if len(input) == 2:
                    _, ticker = input

                    old_db = get_db("assets")
                    row = old_db.index[
                        (old_db["id"] == ctx.message.author.id)
                        & (old_db["asset"] == ticker)
                    ]

                    # Update database
                    if not row.empty:
                        update_db(old_db.drop(index=row), "assets")
                        await ctx.send(
                            f"Succesfully removed all {ticker.upper()} from your owned stocks!"
                        )
                    else:
                        await ctx.send("You do not own this stock!")

                elif len(input) == 3:
                    _, ticker, amount = input
                    old_db = get_db("assets")

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
                            update_db(old_db.drop(index=row.index), "assets")
                            await ctx.send(
                                f"Succesfully removed all {ticker.upper()} from your owned stocks!"
                            )
                        else:
                            old_db.loc[
                                (old_db["id"] == ctx.message.author.id)
                                & (old_db["asset"] == ticker.upper()),
                                "owned",
                            ] -= int(amount)
                            update_db(old_db, "assets")
                            await ctx.send(
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
                        await ctx.send("You do not own this stock!")
                else:
                    await ctx.send("Please specify a ticker!")

            elif input[0] == "show":
                db = get_db("assets")
                rows = db.loc[
                    (db["id"] == ctx.message.author.id) & (db["exchange"] == "stock")
                ]
                if not rows.empty:
                    for _, row in rows.iterrows():
                        # Maybe send this an embed
                        await ctx.send(
                            f"Stock: {row['asset'].upper()} \nAmount: {row['owned']}"
                        )
                else:
                    await ctx.send("You do not have any stocks")
            else:
                await ctx.send(
                    "Please use one of the following keywords: 'add', 'remove', 'show'"
                )
        else:
            raise commands.UserInputError()

    @stock.error
    async def stock_error(self, ctx: commands.Context, error: Exception) -> None:
        print(error)

        if isinstance(error, commands.UserInputError):
            await ctx.send(
                f"{ctx.author.mention} Please use one of the following keywords: 'add', 'remove', 'show' followed by stock ticker and amount!"
            )
        else:
            await ctx.send(
                f"{ctx.author.mention} An error has occurred. Please try again later."
            )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Stock(bot))
