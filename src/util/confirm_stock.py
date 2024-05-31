## > Imports
# > 3rd Party Dependencies
import discord
import yfinance as yf
from discord.ext import commands
from discord.ui import Button, View


async def confirm_stock(bot: commands.Bot, ctx: commands.Context, ticker: str) -> bool:

    # Check if this ticker exists
    stock_info = yf.Ticker(ticker)

    # If it does not exist let the user know
    if stock_info.info["regularMarketPrice"] == None:

        confirm_button = Button(
            label="Confirm",
            style=discord.ButtonStyle.green,
            emoji="✅",
            custom_id="confirm",
        )
        cancel_button = Button(
            label="Cancel",
            style=discord.ButtonStyle.red,
            emoji="❌",
            custom_id="cancel",
        )

        view = View()
        view.add_item(confirm_button)
        view.add_item(cancel_button)

        # Can also use ctx.followup.send
        await ctx.respond(
            (
                f"Are you sure {ticker.upper()} is correct? We could not find it on Yahoo Finance.\n"
                "Click on \N{WHITE HEAVY CHECK MARK} to continue and on \N{CROSS MARK} to cancel."
            ),
            view=view,
        )

        res = await bot.wait_for(
            "interaction", check=lambda i: i.custom_id == "confirm"
        )

        # If the confirm button was pressed, return True
        if res.data["custom_id"] == "confirm":
            return True
        else:
            return False

    return True
