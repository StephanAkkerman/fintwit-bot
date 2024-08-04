import datetime

# > Discord dependencies
import discord
import pandas as pd
import pytz

# > 3rd party dependencies
import yahoo_fin.stock_info as si
from discord.ext import commands
from discord.ext.tasks import loop

from api.cmc import trending
from util.afterhours import afterHours
from util.cg_data import get_top_categories, get_trending_coins
from util.disc_util import get_channel, loop_error_catcher
from util.formatting import (
    format_change,
    format_embed,
    format_embed_length,
    human_format,
)

# Local dependencies
from util.vars import config, data_sources, logger


class Trending(commands.Cog):
    """
    This class contains the cog for posting the top trending crypto and stocks.
    It can be enabled / disabled in the config under ["LOOPS"]["TRENDING"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["TRENDING"]["CRYPTO"]["ENABLED"]:
            self.crypto_channel = None
            self.crypto.start()

        if config["LOOPS"]["CRYPTO_CATEGORIES"]["ENABLED"]:
            self.crypto_categories_channel = None
            self.crypto_categories.start()

        if config["LOOPS"]["TRENDING"]["STOCKS"]["ENABLED"]:
            self.stocks_channel = None
            self.stocks.start()

        if config["LOOPS"]["TRENDING"]["PREMARKET"]["ENABLED"]:
            self.pre_market_channel = None
            self.premarket.start()

        if config["LOOPS"]["TRENDING"]["AFTERHOURS"]["ENABLED"]:
            self.after_hours_channel = None
            self.afterhours.start()

    def tv_market_data(self, url) -> pd.DataFrame:
        df = pd.read_html(url)[0]

        if len(df) <= 1:
            return

        # Use a more accurate regex to separate the symbol and company name
        # Assume symbols are 1-4 uppercase letters and company names start with a capital letter
        df[["Symbol", "Company Name"]] = df["Symbol"].str.extract(
            r"([A-Z]{1,4})([A-Z][a-zA-Z ,.\'-]*)", expand=True
        )

        # Strip any leading/trailing whitespaces from the 'Company Name'
        df["Company Name"] = df["Company Name"].str.strip()

        if "pre-market" in url:
            columns = [
                "Symbol",
                "Pre-market Vol",
                "Pre-market Close",
                "Pre-market Chg %",
            ]
        elif "after-hours" in url:
            columns = [
                "Symbol",
                "Post-market Vol",
                "Post-market Close",
                "Post-market Chg %",
            ]
        else:
            logger.error("Invalid URL for TradingView market data")
            return

        # Format the dataframe
        df = df[columns]

        # Create renaming dictionary dynamically
        rename_dict = {
            col: new_col
            for col, new_col in zip(columns[1:], ["Volume", "Price", "% Change"])
        }

        # Rename columns
        df = df.rename(columns=rename_dict)

        # Remove the ' USD' from the 'Price' column
        df["Price"] = df["Price"].str.replace(" USD", "")

        # Remove the '%' from the '% Change' column
        df["% Change"] = df["% Change"].str.replace("%", "")

        # Remove the + and - from the '% Change' column
        df["% Change"] = df["% Change"].str.replace("+", "")
        df["% Change"] = df["% Change"].str.replace("−", "")

        df["Website"] = "https://www.tradingview.com/symbols/NASDAQ-" + df["Symbol"]
        # Make the symbol a clickable link
        df["Symbol"] = "[" + df["Symbol"] + "](" + df["Website"] + ")"

        return df

    def is_pre_market(self):
        # Define pre-market trading hours in Eastern Time (ET)
        pre_market_start = datetime.time(4, 0)  # 4:00 AM
        pre_market_end = datetime.time(9, 30)  # 9:30 AM

        # Get the current time in Eastern Time (ET)
        et = pytz.timezone("US/Eastern")
        current_time = datetime.datetime.now(et).time()

        # Check if current time is within pre-market hours
        return pre_market_start <= current_time <= pre_market_end

    def is_after_hours(self):
        # Define post-market trading hours in Eastern Time (ET)
        post_market_start = datetime.time(16, 0)  # 4:00 PM
        post_market_end = datetime.time(20, 0)  # 8:00 PM

        # Get the current time in Eastern Time (ET)
        et = pytz.timezone("US/Eastern")
        current_time = datetime.datetime.now(et).time()

        # Check if current time is within post-market hours
        return post_market_start <= current_time <= post_market_end

    @loop(hours=1)
    @loop_error_catcher
    async def premarket(self) -> None:
        if self.pre_market_channel is None:
            self.pre_market_channel = await get_channel(
                self.bot,
                config["LOOPS"]["TRENDING"]["PREMARKET"]["CHANNEL"],
                config["CATEGORIES"]["STOCKS"],
            )
        if not self.is_pre_market():
            return

        premarket_url = "https://www.tradingview.com/markets/stocks-usa/market-movers-active-pre-market-stocks/"

        df = self.tv_market_data(premarket_url)
        if df is None:
            return

        pre_e = await format_embed(
            df.head(20), "Most Active Pre-market Stocks", "tradingview-premarket"
        )

        # Remove the previous message
        await self.pre_market_channel.purge(limit=1)
        await self.pre_market_channel.send(embed=pre_e)

    @loop(hours=1)
    @loop_error_catcher
    async def afterhours(self) -> None:
        if self.after_hours_channel is None:
            self.after_hours_channel = await get_channel(
                self.bot,
                config["LOOPS"]["TRENDING"]["AFTERHOURS"]["CHANNEL"],
                config["CATEGORIES"]["STOCKS"],
            )

        # Check if the after hours are now
        if not self.is_after_hours():
            return

        ah_url = "https://www.tradingview.com/markets/stocks-usa/market-movers-active-after-hours-stocks/"

        df = self.tv_market_data(ah_url)

        if df is None:
            return

        ah_e = await format_embed(
            df.head(20), "Most Active After Hours Stocks", "tradingview-afterhours"
        )

        # Remove the previous message
        await self.after_hours_channel.purge(limit=1)
        await self.after_hours_channel.send(embed=ah_e)

    @loop(hours=12)
    @loop_error_catcher
    async def crypto(self) -> None:
        """
        Gets the data from the CoinMarketCap API and posts in the trending crypto channel.

        Returns
        -------
        None
        """
        if self.crypto_channel is None:
            self.crypto_channel = await get_channel(
                self.bot,
                config["LOOPS"]["TRENDING"]["CHANNEL"],
                config["CATEGORIES"]["CRYPTO"],
            )

        cmc_df = await trending()
        cmc_e = await format_embed(cmc_df, "Trending On CoinMarketCap", "coinmarketcap")

        cg_df = await get_trending_coins()

        if cg_df.empty:
            return

        cg_e = await format_embed(cg_df, "Trending On CoinGecko", "coingecko")

        await self.crypto_channel.purge(limit=2)
        await self.crypto_channel.send(embed=cg_e)
        await self.crypto_channel.send(embed=cmc_e)

    @loop(hours=1)
    @loop_error_catcher
    async def crypto_categories(self) -> None:
        if self.crypto_categories_channel is None:
            self.crypto_categories_channel = await get_channel(
                self.bot,
                config["LOOPS"]["CRYPTO_CATEGORIES"]["CHANNEL"],
            )
        df = await get_top_categories()

        if df is None or df.empty:
            return

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
        if self.stocks_channel is None:
            self.stocks_channel = await get_channel(
                self.bot,
                config["LOOPS"]["TRENDING"]["CHANNEL"],
                config["CATEGORIES"]["STOCKS"],
            )
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
            logger.error(f"Error getting most active stocks: {e}")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Trending(bot))
