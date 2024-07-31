# Standard libraries
# > 3rd party dependencies
import yahoo_fin.stock_info as si

# > Discord dependencies
from discord.ext import commands
from discord.ext.tasks import loop

from util.afterhours import afterHours
from util.disc_util import get_channel
from util.formatting import format_embed

# Local dependencies
from util.vars import config, logger


class Losers(commands.Cog):
    """
    This class contains the cog for posting the top crypto and stocks losers.
    It can be enabled / disabled in the config under ["LOOPS"]["LOSERS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["LOSERS"]["STOCKS"]["ENABLED"]:
            self.channel = None
            self.losers.start()

    @loop(hours=2)
    async def losers(self) -> None:
        """
        If the market is open, this function posts the top 50 losers for todays stocks.

        Returns
        -------
        None
        """
        if self.channel is None:
            self.channel = await get_channel(
                self.bot,
                config["LOOPS"]["LOSERS"]["CHANNEL"],
                config["CATEGORIES"]["STOCKS"],
            )

        # Dont send if the market is closed
        if afterHours():
            return

        try:
            e = await format_embed(si.get_day_losers().head(10), "Losers", "yahoo")
            await self.channel.send(embed=e)
        except Exception as e:
            logger.error("Error getting or posting stock losers, error:", e)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Losers(bot))
