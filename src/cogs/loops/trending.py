# > 3rd party dependencies
from pycoingecko import CoinGeckoAPI
import yahoo_fin.stock_info as si
import pandas as pd

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, get_json_data
from util.disc_util import get_channel
from util.afterhours import afterHours
from util.formatting import format_embed


class Trending(commands.Cog):
    """
    This class contains the cog for posting the top trending crypto and stocks.
    It can be enabled / disabled in the config under ["LOOPS"]["TRENDING"].

    Methods
    -------
    cmc() -> None
        Gets the data from the CoinMarketCap API and posts in the trending crypto channel.
    coingecko() -> None
        Gets the data from the CoinGecko API and posts in the trending crypto channel.
    stocks() -> None
        Gets the data from the yahoo_fin API and posts in the trending stocks channel.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["TRENDING"]["CRYPTO"]["ENABLED"]:
            self.crypto_channel = get_channel(
                self.bot, config["LOOPS"]["TRENDING"]["CRYPTO"]["CHANNEL"]
            )

            self.coingecko.start()
            self.cmc.start()

        if config["LOOPS"]["TRENDING"]["STOCKS"]["ENABLED"]:
            self.stocks_channel = get_channel(
                self.bot, config["LOOPS"]["TRENDING"]["STOCKS"]["CHANNEL"]
            )

            self.stocks.start()

    @loop(hours=12)
    async def cmc(self) -> None:
        """
        Gets the data from the CoinMarketCap API and posts in the trending crypto channel.

        Returns
        -------
        None
        """
        cmc_data = await get_json_data(
            "https://api.coinmarketcap.com/data-api/v3/topsearch/rank"
        )

        # Convert to dataframe
        cmc_df = pd.DataFrame(cmc_data["data"]["cryptoTopSearchRanks"])

        # Only save [[symbol, price + pricechange, volume]]
        cmc_df = cmc_df[["symbol", "slug", "priceChange"]]

        # Rename symbol
        cmc_df.rename(columns={"symbol": "Symbol"}, inplace=True)

        # Add website to symbol
        cmc_df["Website"] = "https://coinmarketcap.com/currencies/" + cmc_df["slug"]
        # Format the symbol
        cmc_df["Symbol"] = "[" + cmc_df["Symbol"] + "](" + cmc_df["Website"] + ")"

        # Get important information from priceChange dictionary
        cmc_df["Price"] = cmc_df["priceChange"].apply(lambda x: x["price"])
        cmc_df["% Change"] = cmc_df["priceChange"].apply(lambda x: x["priceChange24h"])
        cmc_df["Volume"] = cmc_df["priceChange"].apply(lambda x: x["volume24h"])

        e = await format_embed(cmc_df, "Trending On CoinMarketCap", "coinmarketcap")

        await self.crypto_channel.send(embed=e)

    @loop(hours=12)
    async def coingecko(self) -> None:
        """
        Posts the top 7 trending cryptocurrencies in trending crypto channel

        Returns
        -------
        None
        """

        cg = CoinGeckoAPI()

        ticker = []
        prices = []
        price_changes = []
        vol = []

        for coin in cg.get_search_trending()["coins"]:
            coin_dict = cg.get_coin_by_id(coin["item"]["id"])

            website = f"https://coingecko.com/en/coins/{coin['item']['id']}"
            price = coin_dict["market_data"]["current_price"]["usd"]
            price_change = coin_dict["market_data"]["price_change_percentage_24h"]

            ticker.append(f"[{coin['item']['symbol']}]({website})")
            vol.append(coin_dict["market_data"]["total_volume"]["usd"])
            prices.append(price)
            price_changes.append(price_change)

        # Convert to dataframe
        df = pd.DataFrame(
            {
                "Symbol": ticker,
                "Price": prices,
                "% Change": price_changes,
                "Volume": vol,
            }
        )

        e = await format_embed(df, "Trending On CoinGecko", "coingecko")

        await self.crypto_channel.send(embed=e)

    @loop(hours=2)
    async def stocks(self) -> None:
        """
        Posts the most actively traded stocks in the trending stocks channel.

        Returns
        -------
        None
        """
        # Dont send if the market is closed
        if afterHours():
            return

        # Only use the top 50 stocks
        active = si.get_day_most_active().head(50)

        # Format the data
        active["Price"] = "$" + active["Price (Intraday)"].astype(str)

        e = await format_embed(active, "most-active", "yahoo")

        await self.stocks_channel.send(embed=e)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Trending(bot))
