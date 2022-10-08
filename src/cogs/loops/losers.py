# Standard libraries
import datetime

# > 3rd party dependencies
import yahoo_fin.stock_info as si

# > Discord dependencies
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config
from util.disc_util import get_channel
from util.afterhours import afterHours
from util.formatting import format_embed


class Losers(commands.Cog):
    """
    This class contains the cog for posting the top crypto and stocks losers.
    It can be enabled / disabled in the config under ["LOOPS"]["LOSERS"].

    Methods
    -------
    losers() -> None:
        If the market is open, this function posts the top 50 losers for todays stocks.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["LOSERS"]["STOCKS"]["ENABLED"]:
            self.channel = get_channel(
                self.bot,
                config["LOOPS"]["LOSERS"]["CHANNEL"],
                config["CATEGORIES"]["STOCKS"],
            )
            self.losers.start()

    @loop(hours=2)
    async def losers(self) -> None:
        """
        If the market is open, this function posts the top 50 losers for todays stocks.

        Returns
        -------
        None
        """

        # Dont send if the market is closed
        if afterHours():
            return

        try:
            losers = si.get_day_losers().head(50)
        except Exception:
            print("Failed to get losers")
            return

        losers.rename(columns={"Price (Intraday)": "Price"}, inplace=True)

        e = await format_embed(losers, "Losers", "yahoo")

        await self.channel.send(embed=e)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Losers(bot))
