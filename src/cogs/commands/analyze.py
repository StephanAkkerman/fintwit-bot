import datetime

import discord
from discord.commands.context import ApplicationContext
from discord.ext import commands

from api.benzinga import get_benzinga_data
from constants.config import config
from constants.logger import logger
from util.disc import conditional_role_decorator, log_command_usage


class Analyze(commands.Cog):
    """
    This class is used to handle the analyze command.
    You can enable / disable this command in the config, under ["COMMANDS"]["ANALYZE"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.slash_command(
        description="Request the current analysis for a stock ticker."
    )
    @discord.option(
        "stock", type=str, description="Stock ticker, e.g. AAPL.", required=True
    )
    @log_command_usage
    @conditional_role_decorator(config["COMMANDS"]["ANALYZE"]["ROLE"])
    async def analyze(self, ctx: ApplicationContext, stock: str) -> None:
        """
        The analyze command is used to get the current analyst ratings for a stock ticker from benzinga.com.

        Parameters
        ----------
        ctx : commands.Context
            Discord context object.
        stock : Option, optional
            The ticker of a stock, e.g. AAPL
        """

        await ctx.response.defer(ephemeral=True)

        e = discord.Embed(
            title=f"Last 10 {stock.upper()} Analysist Ratings",
            url=f"https://www.benzinga.com/quote/{stock}/analyst-ratings",
            description="",
            color=0x1F7FC1,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        e.set_footer(
            text="\u200b",
            icon_url="https://www.benzinga.com/next-assets/images/apple-touch-icon.png",
        )
        data = await get_benzinga_data(stock)
        # Only use top 10
        data = data.head(10)

        e.add_field(name="Date", value="\n".join(data["date▲▼"]), inline=True)
        e.add_field(
            name="Price Target",
            value="\n".join(data["Price Target Change▲▼"]),
            inline=True,
        )
        e.add_field(
            name="Rate",
            value="\n".join(data["Previous / Current Rating▲▼"]),
            inline=True,
        )

        await ctx.respond(embed=e)

    @analyze.error
    async def analyze_error(self, ctx: ApplicationContext, error: Exception):
        """
        Catches the errors when using the `/analyze` command.

        Parameters
        ----------
        ctx : commands.Context
            Necessary Discord context object.
        error : Exception
            The exception that was raised when using the `!earnings` command.
        """
        if isinstance(error, commands.UserInputError):
            await ctx.respond("Could not find any data for the stock you provided.")
        else:
            await ctx.respond("An error has occurred. Please try again later.")
            logger.error(error)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Analyze(bot))
