## > Imports
# > Standard libraries
import datetime

# > 3rd party dependencies
import pandas as pd

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, get_json_data
from util.disc_util import get_channel


class StockTwits(commands.Cog):
    """
    This class contains the cog for posting the most discussed StockTwits tickers.
    It can be enabled / disabled in the config under ["LOOPS"]["STOCKTWITS"].

    Methods
    -------
    function() -> None:
        Gets the data and formats it into an embed.
    stocktwits() -> None:
        The function posts the StockTwits embeds in the configured channel.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = get_channel(self.bot, config["LOOPS"]["STOCKTWITS"]["CHANNEL"])

        self.stocktwits.start()

    async def get_data(self, e: discord.Embed, keyword: str) -> discord.Embed:
        """
        Gets the data from StockTwits based on the passed keywords and returns a discord.Embed.

        Parameters
        ----------
        e : discord.Embed
            The discord.Embed where the data will be added to.
        keyword : str
            The specific keyword to get the data for. Options are: ts, m_day, wl_ct_day.

        Returns
        -------
        discord.Embed
            The discord.Embed with the data added to it.
        """

        # Keyword can be "ts", "m_day", "wl_ct_day"
        data = await get_json_data("https://api.stocktwits.com/api/2/charts/" + keyword)

        table = pd.DataFrame(data["table"][keyword])
        stocks = pd.DataFrame(data["stocks"]).T
        stocks["stock_id"] = stocks.index.astype(int)
        full_df = pd.merge(stocks, table, on="stock_id")
        full_df.sort_values(by="val", ascending=False, inplace=True)

        # Fill all NaN / None values with 0, in case the price is not known
        full_df = full_df.fillna(0)

        # Format % change
        full_df["change"] = full_df["change"].apply(
            lambda x: f" (+{round(x,2)}% 📈)" if x > 0 else f" ({round(x,2)}% 📉)"
        )

        # Format price
        full_df["price"] = full_df["price"].apply(lambda x: round(x, 3))
        full_df["price"] = full_df["price"].astype(str) + full_df["change"]

        # Show Symbol, Price + change, Score / Count
        if keyword == "ts":
            name = "Trending"
            val = "Score"
        elif keyword == "m_day":
            name = "Most Active"
            val = "Count"
        else:
            name = "Most Watched"
            val = "Count"

        # Set values as string
        full_df["val"] = full_df["val"].astype(str)

        # Get the values as string
        assets = "\n".join(full_df["symbol"].to_list())
        prices = "\n".join(full_df["price"].to_list())
        values = "\n".join(full_df["val"].to_list())

        e.add_field(name=name, value=assets, inline=True)
        e.add_field(name="Price", value=prices, inline=True)
        e.add_field(name=val, value=values, inline=True)

        return e

    @loop(hours=6)
    async def stocktwits(self) -> None:
        """
        The function posts the StockTwits embeds in the configured channel.

        Returns
        -------
        None
        """

        e = discord.Embed(
            title=f"StockTwits Rankings",
            url="https://stocktwits.com/rankings/trending",
            description="",
            color=0xFFFFFF,
            timestamp=datetime.datetime.utcnow(),
        )

        e = await self.get_data(e, "ts")
        e = await self.get_data(e, "m_day")
        e = await self.get_data(e, "wl_ct_day")

        # Set datetime and binance icon
        e.set_footer(
            icon_url="https://pbs.twimg.com/profile_images/1464337316965720069/bZ4-cEg3_400x400.jpg",
        )

        await self.channel.send(embed=e)


def setup(bot: commands.bot.Bot) -> None:
    bot.add_cog(StockTwits(bot))
