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
import util.vars
from util.vars import config
from util.db import update_db, merge_and_update
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

    async def stock_trade_msg(
        self, user: discord.User, side: str, stock_name: str, price: str, quantity: str, worth:float
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

        price = round(price, 2)

        e = discord.Embed(
            title=f"{side} {quantity} {stock_name} for ${price}",
            description="",
            color=0x720E9E,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        e.set_author(name=user.name, icon_url=user.display_avatar.url)
        e.add_field(name="Price", value=f"${price}", inline=True)
        e.add_field(name="Amount", value=quantity, inline=True)
        e.add_field(
            name="$ Worth", value=f"${round(worth,2)}", inline=True
        )

        e.set_footer(
            text="\u200b",
            icon_url="https://s.yimg.com/cv/apiv2/myc/finance/Finance_icon_0919_250x252.png",
        )

        channel = get_channel(
            self.bot, config["LOOPS"]["TRADES"]["CHANNEL"]
        )

        await channel.send(embed=e)

    @stocks.command(name="add", description="Add a stock to your portfolio.")
    async def add(
        self,
        ctx: commands.Context,
        ticker: Option(
            str, description="The ticker of the stock e.g., AAPL", required=True
        ),
        buying_price: Option(
            str, description="The price of the stock when you bought it, e.g., 106.40", required=True
        ),
        amount: Option(
            str, description="The amount of stocks that you own at this price, e.g., 2", required=True
        ),
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
            price = yf.Ticker(ticker).info["regularMarketPrice"]
        except Exception:
            price = 0
            
        worth = round(price * amount,2)

        # Add ticker to database
        new_data = pd.DataFrame(
            [{
                "asset": ticker.upper(),
                "worth": worth,
                "buying_price": buying_price,
                "owned": amount,
                "exchange": "stock",
                "id": ctx.author.id,
                "user": ctx.author.name,
            }]
        )

        old_db = util.vars.assets_db

        # Check if the user has this asset already
        owned_in_db = old_db.loc[
            (old_db["id"] == ctx.author.id)
            & (old_db["asset"] == ticker.upper())
        ]
        
        # If the user does not yet own this stock
        if owned_in_db.empty:
            util.vars.assets_db = merge_and_update(old_db, new_data, "assets")
        else:
            # Increase the amount if everything is the same
            same_price = old_db.loc[
                (old_db["id"] == ctx.author.id) & 
                (old_db["asset"] == ticker.upper()) & 
                (old_db["buying_price"] == buying_price)
            ]
            
            if not same_price.empty:
                old_db.loc[
                (old_db["id"] == ctx.author.id) & 
                (old_db["asset"] == ticker.upper()), 
                "owned"] += amount
                
            else:
                # Get the old buying price and average it with the new one
                old_buying_price = owned_in_db["buying_price"].values[0]
                old_amount_owned = owned_in_db["owned"].values[0]
                
                new_buying_price = (old_buying_price * old_amount_owned + buying_price * amount) / (old_amount_owned + amount)              
                
                # Update the buying price and amount owned
                old_db.loc[(old_db["id"] == ctx.author.id) & 
                (old_db["asset"] == ticker.upper()),
                "buying_price"] = new_buying_price
                
                # Update the amount owned
                old_db.loc[(old_db["id"] == ctx.author.id) & 
                (old_db["asset"] == ticker.upper()),
                "owned"] += amount
                        
            self.update_assets_db(old_db)
        await ctx.respond("Succesfully added your stock to the database!")

        # Send message in trades channel
        await self.stock_trade_msg(
            ctx.author,
            "Bought",
            ticker,
            buying_price,
            amount,
            worth
        )


    @stocks.command(
        name="remove", description="Remove a specific stock from your portfolio."
    )
    async def remove(self, 
                     ctx: commands.Context, 
                     ticker: Option(str, description="The ticker of the stock e.g., AAPL", required=True),
                     amount: Option(str, description="The amount of stocks that you want to delete, e.g., 2", required=False)) -> None:
        """
        Usage:
        `!stock remove <ticker> (<amount>)` to remove a stock from your portfolio
        """        
        old_db = util.vars.assets_db
                
        if not amount:
            row = old_db.index[
                (old_db["id"] == ctx.author.id)
                & (old_db["asset"] == ticker)
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
                (old_db["id"] == ctx.author.id)
                & (old_db["asset"] == ticker)
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
                        (old_db["id"] == ctx.author.id)
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
            price = yf.Ticker(ticker).info["regularMarketPrice"]
        except Exception:
            price = 0
            
        worth = amount * price

        # Send message in trades channel
        await self.stock_trade_msg(
            ctx.author,
            "Sold",
            ticker,
            price,
            amount,
            worth
        )

    @stocks.command(name="show", description="Show the stocks in your portfolio.")
    async def show(self, ctx: commands.Context) -> None:
        """
        Usage:
        `!stock show` to show the stocks in your portfolio
        """
        db = util.vars.assets_db
        rows = db.loc[
            (db["id"] == ctx.author.id) & (db["exchange"] == "stock")
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
