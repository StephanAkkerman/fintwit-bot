import datetime

# > Discord dependencies
import discord

# > 3rd party dependencies
from discord.ext import commands
from discord.ext.tasks import loop

from api.binance import get_funding_rate
from constants.config import config

# Local dependencies
from constants.sources import data_sources
from util.disc import get_channel, loop_error_catcher


class Funding(commands.Cog):
    """
    This class is used to handle the funding loop.
    This can be enabled / disabled in the config, under ["LOOPS"]["FUNDING"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = None
        self.funding.start()

    @loop(hours=4)
    @loop_error_catcher
    async def funding(self) -> None:
        """
        This function gets the data from the funding API and posts it in the funding channel.

        Returns
        -------
        None
        """
        if self.channel is None:
            self.channel = await get_channel(
                self.bot, config["LOOPS"]["FUNDING"]["CHANNEL"]
            )

        e = discord.Embed(
            title="Binance Top 15 Lowest Funding Rates",
            url="",
            description="",
            color=data_sources["binance"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        lowest, timeToNextFunding = await get_funding_rate()

        # Set datetime and icon
        e.set_footer(
            text=f"Next funding in {str(timeToNextFunding).split('.')[0]}",
            icon_url=data_sources["binance"]["icon"],
        )

        lowest_tickers = "\n".join(lowest["symbol"].tolist())
        lowest_rates = "\n".join(lowest["lastFundingRate"].tolist())

        e.add_field(
            name="Coin",
            value=lowest_tickers,
            inline=True,
        )

        e.add_field(
            name="Funding Rate",
            value=lowest_rates,
            inline=True,
        )

        # Post the embed in the channel
        await self.channel.purge(limit=1)
        await self.channel.send(embed=e)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Funding(bot))
