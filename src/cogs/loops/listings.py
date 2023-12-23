import asyncio
import datetime

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, get_json_data, data_sources
from util.disc_util import get_channel


class Exchange_Listings(commands.Cog):
    """
    This class contains the cog for posting the new Binance listings
    It can be enabled / disabled in the config under ["LOOPS"]["NEW_LISTINGS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.exchanges = config["LOOPS"]["LISTINGS"]["EXCHANGES"]
        self.old_symbols = {}

        self.listings_channel = get_channel(
            self.bot, config["LOOPS"]["LISTINGS"]["CHANNEL"]
        )
        self.delistings_channel = get_channel(
            self.bot, config["LOOPS"]["LISTINGS"]["DELISTINGS"]["CHANNEL"]
        )

        asyncio.create_task(self.set_old_symbols())

    async def get_symbols(self, exchange: str) -> list:
        """
        Gets the symbols currently listed on the exchange.

        Returns
        -------
        list
            The symbols currently listed on the exchange
        """

        if exchange == "binance":
            url = "https://api.binance.com/api/v3/exchangeInfo"
            key1 = "symbols"
            key2 = "symbol"
        elif exchange == "kucoin":
            url = "https://api.kucoin.com/api/v1/symbols"
            key1 = "data"
            key2 = "symbol"
        elif exchange == "coinbase":
            url = "https://api.exchange.coinbase.com/currencies"
            key2 = "id"

        # Check if there have been new listings
        response = await get_json_data(url)

        # Get the symbols
        if exchange == "coinbase":
            return [x[key2] for x in response]

        return [x[key2] for x in response[key1]]

    def create_embed(
        self, ticker: str, exchange: str, is_listing: bool
    ) -> discord.Embed:
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

        if exchange == "binance":
            color = data_sources["binance"]["color"]
            icon_url = data_sources["binance"]["icon"]
            url = f"https://www.{exchange}.com/en/trade/{ticker}"
        elif exchange == "kucoin":
            color = data_sources["kucoin"]["color"]
            icon_url = data_sources["kucoin"]["icon"]
            url = f"https://www.{exchange}.com/trade/{ticker}"
        elif exchange == "coinbase":
            color = data_sources["coinbase"]["color"]
            icon_url = data_sources["coinbase"]["icon"]
            url = f"https://www.pro.{exchange}.com/trade/{ticker}"

        title = f"{ticker} {'Listed' if is_listing else 'Delisted'} on {exchange.capitalize()}"

        e = discord.Embed(
            title=title,
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
        for exchange in self.exchanges:
            self.old_symbols[exchange] = await self.get_symbols(exchange)

        # Start after setting all the symbols
        self.new_listings.start()

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

        # Do this for all exchanges
        for exchange in self.exchanges:
            # Get the new symbols
            new_symbols = await self.get_symbols(exchange)

            new_listings = []
            delistings = []

            if self.old_symbols[exchange] == []:
                await self.set_old_symbols()

            # If there is a new symbol, send a message
            if len(new_symbols) > len(self.old_symbols):
                new_listings = list(set(new_symbols) - set(self.old_symbols))

            # If symbols got removed do nothing
            if len(new_symbols) < len(self.old_symbols):
                delistings = list(set(self.old_symbols) - set(new_symbols))

            # Update old_symbols
            self.old_symbols[exchange] = new_symbols

            # Create the embed and post it
            for ticker in new_listings:
                await self.listings_channel.send(
                    embed=self.create_embed(ticker, exchange, True)
                )

            for ticker in delistings:
                await self.delistings_channel.send(
                    embed=self.create_embed(ticker, exchange, False)
                )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Exchange_Listings(bot))
