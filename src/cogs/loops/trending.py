import datetime

# > 3rd party dependencies
import yahoo_fin.stock_info as si
import pandas as pd

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, get_json_data, data_sources
from util.disc_util import get_channel
from util.afterhours import afterHours
from util.formatting import (
    format_embed,
    format_change,
    human_format,
    format_embed_length,
)
from util.cg_data import get_trending_coins, get_top_categories


class Trending(commands.Cog):
    """
    This class contains the cog for posting the top trending crypto and stocks.
    It can be enabled / disabled in the config under ["LOOPS"]["TRENDING"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["TRENDING"]["CRYPTO"]["ENABLED"]:
            self.crypto_channel = get_channel(
                self.bot,
                config["LOOPS"]["TRENDING"]["CHANNEL"],
                config["CATEGORIES"]["CRYPTO"],
            )

            self.crypto.start()

        if config["LOOPS"]["CRYPTO_CATEGORIES"]["ENABLED"]:
            self.crypto_categories_channel = get_channel(
                self.bot,
                config["LOOPS"]["CRYPTO_CATEGORIES"]["CHANNEL"],
            )

            self.crypto_categories.start()

        if config["LOOPS"]["TRENDING"]["STOCKS"]["ENABLED"]:
            self.stocks_channel = get_channel(
                self.bot,
                config["LOOPS"]["TRENDING"]["CHANNEL"],
                config["CATEGORIES"]["STOCKS"],
            )

            self.stocks.start()

    @loop(hours=12)
    async def crypto(self) -> None:
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

        cmc_e = await format_embed(cmc_df, "Trending On CoinMarketCap", "coinmarketcap")

        cg_df = await get_trending_coins()

        if cg_df.empty:
            print("No trending coins found on CoinGecko")
            return

        cg_e = await format_embed(cg_df, "Trending On CoinGecko", "coingecko")

        await self.crypto_channel.purge(limit=2)
        await self.crypto_channel.send(embed=cg_e)
        await self.crypto_channel.send(embed=cmc_e)

    @loop(hours=1)
    async def crypto_categories(self) -> None:
        df = await get_top_categories()

        # Only use top 10
        df = df.head(10)

        # Format the dataframe
        # Merge name and link
        df["Name"] = "[" + df["Name"] + "](" + df["Link"] + ")"

        # Format 24h change
        df["24h Change"] = df["24h Change"].apply(lambda x: format_change(x))

        # Format the volume
        df["Volume"] = df["Volume"].apply(lambda x: "$" + human_format(x))

        # Format the market cap
        df["Market Cap"] = df["Market Cap"].apply(lambda x: "$" + human_format(x))

        # Get lists of each column
        categories = "\n".join(df["Name"].tolist())
        change = "\n".join(df["24h Change"].tolist())
        volume = "\n".join(df["Volume"].tolist())

        # Prevent possible overflow
        categories, change, volume = format_embed_length([categories, change, volume])

        e = discord.Embed(
            title=f"Top {len(df)} Crypto Categories",
            url="https://www.coingecko.com/en/categories",
            description="",
            color=data_sources["coingecko"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        e.add_field(
            name="Category",
            value=categories,
            inline=True,
        )

        e.add_field(
            name="24h Change",
            value=change,
            inline=True,
        )

        e.add_field(
            name="Volume",
            value=volume,
            inline=True,
        )

        # Set empty text as footer, so we can see the icon
        e.set_footer(text="\u200b", icon_url=data_sources["coingecko"]["icon"])

        await self.crypto_categories_channel.purge(limit=1)
        await self.crypto_categories_channel.send(embed=e)

    @loop(hours=1)
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

        # Only use the top 10 stocks
        try:
            e = await format_embed(
                si.get_day_most_active().head(15), "Most Active Stocks", "yahoo"
            )
            await self.stocks_channel.purge(limit=1)
            await self.stocks_channel.send(embed=e)
        except Exception as e:
            print("Error getting most active stocks: ", e)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Trending(bot))
