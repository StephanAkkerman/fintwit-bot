## > Imports

# > 3rd Party Dependencies
import yfinance as yf
from discord.ext import commands


async def confirm_stock(bot: commands.Bot, ctx: commands.Context, ticker: str) -> bool:

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
        reaction = await bot.wait_for(
            "reaction_add",
            check=lambda r, u: (
                str(r.emoji) == "\N{WHITE HEAVY CHECK MARK}"
                or str(r.emoji) == "\N{CROSS MARK}"
            )
            and u == ctx.author,
        )

        if reaction[0].emoji == "\N{CROSS MARK}":
            # Delete the messages
            await ctx.message.delete()
            await confirm_msg.delete()
            return False
        elif reaction[0].emoji == "\N{WHITE HEAVY CHECK MARK}":
            await confirm_msg.delete()
            return True
        else:
            # Delete the messages
            await ctx.message.delete()
            await confirm_msg.delete()
            await ctx.send("Something went wrong, please try again.")
            return False
    else:
        return True
