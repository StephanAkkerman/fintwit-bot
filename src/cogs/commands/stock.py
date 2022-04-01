##> Imports
# > 3rd Party Dependencies
import pandas as pd
from discord.ext import commands

# Local dependencies
from util.db import get_db, update_db


class Stock(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def stock(self, ctx, *input):
        """Add stocks to your portfolio.

        Usage: `!stock <keyword> <amount> [<ticker>]`
        `!stock add <ticker> <amount>` to add a stock to your portfolio
        `!stock remove <ticker>` to remove a stock from your portfolio
        `!stock show` to show your portfolio
        """

        if input:
            if input[0] == "add":
                if len(input) == 3:
                    _, ticker, amount = input

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
    async def follow_error(self, ctx, error):
        print(error)
        if isinstance(error, commands.UserInputError):
            await ctx.send(
                f"{ctx.author.mention} Please use one of the following keywords: 'add', 'remove', 'show' followed by stock ticker and amount!"
            )
        else:
            await ctx.send(
                f"{ctx.author.mention} An error has occurred. Please try again later."
            )


def setup(bot):
    bot.add_cog(Stock(bot))
