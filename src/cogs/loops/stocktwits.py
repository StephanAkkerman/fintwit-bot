import datetime

import discord
from discord.ext import commands
from discord.ext.tasks import loop

from api.stocktwits import get_data
from constants.config import config
from constants.sources import data_sources
from util.disc import get_channel, loop_error_catcher


class StockTwits(commands.Cog):
    """
    This class contains the cog for posting the most discussed StockTwits tickers.
    It can be enabled / disabled in the config under ["LOOPS"]["STOCKTWITS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = None
        self.stocktwits.start()

    @loop(hours=6)
    @loop_error_catcher
    async def stocktwits(self) -> None:
        """
        The function posts the StockTwits embeds in the configured channel.

        Returns
        -------
        None
        """
        if self.channel is None:
            self.channel = await get_channel(
                self.bot,
                config["LOOPS"]["STOCKTWITS"]["CHANNEL"],
                config["CATEGORIES"]["STOCKS"],
            )

        for keyword in ["ts", "m_day", "wl_ct_day"]:
            df = await get_data(keyword)
            if df.empty:
                continue

            # Get the values as string
            assets = "\n".join(df["symbol"].to_list())
            prices = "\n".join(df["price"].to_list())
            values = "\n".join(df["val"].to_list())

            e = discord.Embed(
                title="StockTwits Rankings",
                url="https://stocktwits.com/rankings/trending",
                description="",
                color=data_sources["stocktwits"]["color"],
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )

            # Show Symbol, Price + change, Score / Count
            if keyword == "ts":
                name = "Trending"
                val = "Score"
            elif keyword == "m_day":
                name = "Most Active"
                val = "Count"
            else:
                name = "Most Watched"
                val = "Count"

            e.add_field(name=name, value=assets, inline=True)
            e.add_field(name="Price", value=prices, inline=True)
            e.add_field(name=val, value=values, inline=True)

            # Set datetime and icon
            e.set_footer(
                text="\u200b",
                icon_url=data_sources["stocktwits"]["icon"],
            )

            await self.channel.send(embed=e)


def setup(bot: commands.bot.Bot) -> None:
    bot.add_cog(StockTwits(bot))
