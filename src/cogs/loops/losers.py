import pandas as pd
from discord.ext import commands
from discord.ext.tasks import loop

from api.yahoo import get_losers
from constants.config import config
from constants.logger import logger
from util.afterhours import afterHours
from util.disc import get_channel, loop_error_catcher
from util.formatting import format_embed


class Losers(commands.Cog):
    """
    This class contains the cog for posting the top stocks losers.
    The crypto losers can be found in gainers.py (because they are both done at the same time).
    It can be enabled / disabled in the config under ["LOOPS"]["LOSERS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["LOSERS"]["STOCKS"]["ENABLED"]:
            self.channel = None
            self.losers.start()

    @loop(hours=2)
    @loop_error_catcher
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
            e = await format_embed(
                pd.DataFrame(get_losers(count=10)), "Losers", "yahoo"
            )
            await self.channel.send(embed=e)
        except Exception as e:
            logger.error(f"Error getting or posting stock losers, error: {e}")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Losers(bot))
