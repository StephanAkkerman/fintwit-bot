##> Imports
from datetime import datetime

import pandas as pd
import pytz

# > 3rd Party Dependencies
import yfinance
from discord.commands import Option
from discord.commands.context import ApplicationContext
from discord.ext import commands

from constants.logger import logger

# Local dependencies
from util.confirm_stock import confirm_stock
from util.disc import log_command_usage


class Earnings(commands.Cog):
    """
    This class is used to handle the earnings command.
    You can enable / disable this command in the config, under ["COMMANDS"]["EARNINGS"].
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(
        name="earnings", description="Gets next earnings date for a given stock."
    )
    @log_command_usage
    async def earnings(
        self,
        ctx: ApplicationContext,
        stock: Option(str, description="Stock ticker, e.g. AAPL.", required=True),
    ):
        """
        Gets next earnings date for a given stock.
        For instance `/earnings AAPL` will return the next earnings date for Apple.

        Parameters
        ----------
        ctx : commands.Context
            Necessary Discord context object.
        stock : str
            The stock ticker to get the earnings date for.

        Raises
        ------
        commands.UserInputError
            If the provided stock ticker is not valid.
        """

        # Check if this stock exists
        if not await confirm_stock(self.bot, ctx, stock):
            return

        ticker = yfinance.Ticker(stock)
        df = ticker.get_earnings_dates()
        # Convert 'today' to a timezone-aware timestamp
        tz = pytz.timezone("America/New_York")
        today = pd.Timestamp(datetime.now(tz))

        # Filter the DataFrame to include only future dates
        future_dates = df[df.index > today]

        # Find the closest date
        closest_date = future_dates.index.min()

        msg = f"The next earnings date for {stock.upper()} is <t:{int(closest_date.timestamp())}:D>."
        await ctx.respond(msg)

    @earnings.error
    async def earnings_error(self, ctx: ApplicationContext, error: Exception):
        """
        Catches the errors when using the `!earnings` command.

        Parameters
        ----------
        ctx : commands.Context
            Necessary Discord context object.
        error : Exception
            The exception that was raised when using the `!earnings` command.
        """
        logger.error(error)
        if isinstance(error, commands.UserInputError):
            await ctx.respond(
                f"{ctx.author.mention} You must specify a stock to request the next earnings of!"
            )
        else:
            await ctx.respond(
                f"{ctx.author.mention} An error has occurred. Please try again later."
            )


def setup(bot: commands.Bot):
    bot.add_cog(Earnings(bot))
