import pandas as pd

# > 3rd party dependencies
import yahoo_fin.stock_info as si

# > Discord dependencies
from discord.ext import commands
from discord.ext.tasks import loop

from util.afterhours import afterHours
from util.disc_util import get_channel
from util.formatting import format_embed

# Local dependencies
from util.vars import config, get_json_data, logger


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
    async def crypto(self) -> None:
        """
        This function will check the gainers and losers on Binance, using USDT as the base currency.
        To prevent too many calls the losers are also done in this section.

        Returns
        -------
        None
        """

        binance_data = await get_json_data("https://api.binance.com/api/v3/ticker/24hr")

        # If the call did not work
        if not binance_data:
            return

        # Cast to dataframe
        try:
            df = pd.DataFrame(binance_data)
        except Exception as e:
            logger.error(f"Could not cast to dataframe, error: {e}")
            return

        # Keep only the USDT pairs
        df = df[df["symbol"].str.contains("USDT")]

        # Remove USDT from the symbol
        df["symbol"] = df["symbol"].str.replace("USDT", "")

        df[["priceChangePercent", "weightedAvgPrice", "volume"]] = df[
            ["priceChangePercent", "weightedAvgPrice", "volume"]
        ].apply(pd.to_numeric)

        # Sort on priceChangePercent
        sorted = df.sort_values(by="priceChangePercent", ascending=False)

        sorted.rename(
            columns={
                "symbol": "Symbol",
                "priceChangePercent": "% Change",
                "weightedAvgPrice": "Price",
                "volume": "Volume",
            },
            inplace=True,
        )

        # Add website to symbol
        sorted["Symbol"] = (
            "["
            + sorted["Symbol"]
            + "](https://www.binance.com/en/price/"
            + sorted["Symbol"]
            + ")"
        )

        # Post the top 10 highest
        gainers = sorted.head(10)

        # Post the top 10 lowest
        losers = sorted.tail(10)
        losers = losers.iloc[::-1]

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
    async def stocks(self) -> None:
        """
        This function uses the yahoo_fin.stock_info module to get the gainers for todays stocks.

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
            e = await format_embed(si.get_day_gainers().head(10), "Gainers", "yahoo")
            await self.stocks_channel.purge(limit=1)
            await self.stocks_channel.send(embed=e)
        except Exception as e:
            logger.error(f"Error posting stocks gainers: {e}")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Gainers(bot))
