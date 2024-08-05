import datetime

import discord
from discord.ext import commands
from discord.ext.tasks import loop

from api.nasdaq import get_halt_data
from constants.config import config
from constants.sources import data_sources
from util.afterhours import afterHours
from util.disc import get_channel, get_tagged_users, loop_error_catcher


class StockHalts(commands.Cog):
    """
    This class contains the cog for posting the halted stocks.
    It can be configured in the config.yaml file under ["LOOPS"]["STOCK_HALTS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = None
        self.halt_embed.start()

    @loop(minutes=15)
    @loop_error_catcher
    async def halt_embed(self):
        # Dont send if the market is closed
        if afterHours():
            return

        if self.channel is None:
            self.channel = await get_channel(
                self.bot, config["LOOPS"]["STOCK_HALTS"]["CHANNEL"]
            )

        df = get_halt_data()
        if df.empty:
            return

        # Remove previous message first
        await self.channel.purge(limit=1)

        # Create embed
        e = discord.Embed(
            title="Halted Stocks",
            url="https://www.nasdaqtrader.com/trader.aspx?id=tradehalts",
            description="",
            color=data_sources["nasdaqtrader"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        # Get the values as string
        time = "\n".join(df["Time"].to_list())
        symbol = "\n".join(df["Issue Symbol"].to_list())

        # Add the values to the embed
        e.add_field(name="Time", value=time, inline=True)
        e.add_field(name="Symbol", value=symbol, inline=True)

        if "Resumption Time" in df.columns:
            resumption = "\n".join(df["Resumption Time"].to_list())
            e.add_field(name="Resumption Time", value=resumption, inline=True)

        e.set_footer(
            text="\u200b",
            icon_url=data_sources["nasdaqtrader"]["icon"],
        )

        tags = get_tagged_users(df["Issue Symbol"].to_list())

        await self.channel.send(content=tags, embed=e)


def setup(bot: commands.Bot) -> None:
    """
    This is a necessary method to make the cog loadable.

    Returns
    -------
    None
    """
    bot.add_cog(StockHalts(bot))
