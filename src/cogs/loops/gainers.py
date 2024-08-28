import pandas as pd
from discord.ext import commands
from discord.ext.tasks import loop

from api.binance import get_gainers_losers
from api.yahoo import get_gainers
from constants.config import config
from constants.logger import logger
from util.afterhours import afterHours
from util.disc import get_channel, loop_error_catcher
from util.formatting import format_embed


class Gainers(commands.Cog):
    """
    This class contains the cog for posting the top crypto and stocks gainers.
    It can be enabled / disabled in the config under ["LOOPS"]["GAINERS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["GAINERS"]["STOCKS"]["ENABLED"]:
            self.stocks_channel = None
            self.stocks.start()

        if config["LOOPS"]["GAINERS"]["CRYPTO"]["ENABLED"]:
            self.crypto_gainers_channel = None

        if config["LOOPS"]["LOSERS"]["CRYPTO"]["ENABLED"]:
            self.crypto_losers_channel = None

        if (
            config["LOOPS"]["GAINERS"]["CRYPTO"]["ENABLED"]
            or config["LOOPS"]["LOSERS"]["CRYPTO"]["ENABLED"]
        ):
            self.crypto.start()

    @loop(hours=1)
    @loop_error_catcher
    async def crypto(self) -> None:
        """
        This function will check the gainers and losers on Binance, using USDT as the base currency.
        To prevent too many calls the losers are also done in this section.

        Returns
        -------
        None
        """

        gainers, losers = await get_gainers_losers()

        # Format the embed
        e_gainers = await format_embed(gainers, "Gainers", "binance")
        e_losers = await format_embed(losers, "Losers", "binance")

        # Post the embed in the channel
        if config["LOOPS"]["GAINERS"]["CRYPTO"]["ENABLED"]:
            if self.crypto_gainers_channel is None:
                self.crypto_gainers_channel = await get_channel(
                    self.bot,
                    config["LOOPS"]["GAINERS"]["CHANNEL"],
                    config["CATEGORIES"]["CRYPTO"],
                )
            await self.crypto_gainers_channel.purge(limit=1)
            await self.crypto_gainers_channel.send(embed=e_gainers)

        if config["LOOPS"]["LOSERS"]["CRYPTO"]["ENABLED"]:
            if self.crypto_losers_channel is None:
                self.crypto_losers_channel = await get_channel(
                    self.bot,
                    config["LOOPS"]["LOSERS"]["CHANNEL"],
                    config["CATEGORIES"]["CRYPTO"],
                )
            await self.crypto_losers_channel.purge(limit=1)
            await self.crypto_losers_channel.send(embed=e_losers)

    @loop(hours=1)
    @loop_error_catcher
    async def stocks(self) -> None:
        """
        Gets the top 10 gainers for the day and posts them in the channel.

        Returns
        -------
        None
        """
        if self.stocks_channel is None:
            self.stocks_channel = await get_channel(
                self.bot,
                config["LOOPS"]["GAINERS"]["CHANNEL"],
                config["CATEGORIES"]["STOCKS"],
            )

        # Dont send if the market is closed
        if afterHours():
            return

        try:
            gainers = await get_gainers(count=10)
            e = await format_embed(pd.DataFrame(gainers), "Gainers", "yahoo")
            await self.stocks_channel.purge(limit=1)
            await self.stocks_channel.send(embed=e)
        except Exception as e:
            logger.error(f"Error posting stocks gainers: {e}")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Gainers(bot))
