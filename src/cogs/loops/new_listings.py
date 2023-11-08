import asyncio
import datetime

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, get_json_data, data_sources
from util.disc_util import get_channel


class Exchange_Listings:
    """
    This class contains the cog for posting the new Binance listings
    It can be enabled / disabled in the config under ["LOOPS"]["NEW_LISTINGS"].
    """

    def __init__(self, bot: commands.Bot, exchange: str) -> None:
        self.bot = bot
        self.exchange = exchange
        self.old_symbols = []
        self.channel = get_channel(self.bot, config["LOOPS"]["NEW_LISTINGS"]["CHANNEL"])

        asyncio.create_task(self.set_old_symbols())
        self.new_listings.start()

    async def get_symbols(self) -> list:
        """
        Gets the symbols currently listed on the exchange.

        Returns
        -------
        list
            The symbols currently listed on the exchange
        """

        if self.exchange == "binance":
            url = "https://api.binance.com/api/v3/exchangeInfo"
            key1 = "symbols"
            key2 = "symbol"
        elif self.exchange == "kucoin":
            url = "https://api.kucoin.com/api/v1/symbols"
            key1 = "data"
            key2 = "symbol"
        elif self.exchange == "coinbase":
            url = "https://api.exchange.coinbase.com/currencies"
            key2 = "id"

        # Check if there have been new listings
        response = await get_json_data(url)

        # Get the symbols
        if self.exchange == "coinbase":
            return [x[key2] for x in response]

        return [x[key2] for x in response[key1]]

    def create_embed(self, ticker: str) -> discord.Embed:
        """
        Creates a styled embed for the newly listed ticker.

        Parameters
        ----------
        ticker : str
            The ticker that was newly listed.

        Returns
        -------
        discord.embeds.Embed
            The styled embed for the newly listed ticker.
        """

        if self.exchange == "binance":
            color = data_sources["binance"]["color"]
            icon_url = data_sources["binance"]["icon"]
            url = f"https://www.{self.exchange}.com/en/trade/{ticker}"
        elif self.exchange == "kucoin":
            color = data_sources["kucoin"]["color"]
            icon_url = data_sources["kucoin"]["icon"]
            url = f"https://www.{self.exchange}.com/trade/{ticker}"
        else:  # Coinbase
            color = data_sources["coinbase"]["color"]
            icon_url = data_sources["coinbase"]["icon"]
            url = f"https://www.pro.{self.exchange}.com/trade/{ticker}"

        e = discord.Embed(
            title=f"{self.exchange.capitalize()} Lists {ticker}",
            url=url,
            description="",
            color=color,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        # Set datetime and binance icon
        e.set_footer(text="\u200b", icon_url=icon_url)

        return e

    async def set_old_symbols(self) -> None:
        """
        Function to set the old symbols from the JSON response.
        This will be used to compare the new symbols to the old symbols.

        Returns
        -------
        None
        """

        # Set the old symbols
        self.old_symbols = await self.get_symbols()

    @loop(hours=6)
    async def new_listings(self) -> None:
        """
        This function will be called every 6 hours to check for new listings.
        It will compare the currently listed symbols with the old symbols.
        If there is a difference, it will post a message to the channel.

        Returns
        -------
        None
        """

        # Get the symbols
        new_symbols = await self.get_symbols()

        new_listings = []

        if self.old_symbols == []:
            await self.set_old_symbols()

        # If there is a new symbol, send a message
        if len(new_symbols) > len(self.old_symbols):
            new_listings = list(set(new_symbols) - set(self.old_symbols))

        # If symbols got removed do nothing
        if len(new_symbols) < len(self.old_symbols):
            # Update old_symbols
            self.old_symbols = new_symbols
            return

        # Update old_symbols
        self.old_symbols = new_symbols

        for ticker in new_listings:
            await self.channel.send(embed=self.create_embed(ticker))


class Binance(commands.Cog):
    """
    This class contains the cog for posting the new Binance listings
    It can be enabled / disabled in the config under ["LOOPS"]["NEW_LISTINGS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        Exchange_Listings(bot, "binance")


class KuCoin(commands.Cog):
    """
    This class contains the cog for posting the new KuCoin listings
    It can be enabled / disabled in the config under ["LOOPS"]["NEW_LISTINGS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        Exchange_Listings(bot, "kucoin")


class CoinBase(commands.Cog):
    """
    This class contains the cog for posting the new CoinBase listings
    It can be enabled / disabled in the config under ["LOOPS"]["NEW_LISTINGS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        Exchange_Listings(bot, "coinbase")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Binance(bot))
    bot.add_cog(KuCoin(bot))
    bot.add_cog(CoinBase(bot))
