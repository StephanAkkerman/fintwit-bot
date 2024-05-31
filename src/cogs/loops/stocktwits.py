## > Imports
# > Standard libraries
import datetime

# > Discord dependencies
import discord

# > 3rd party dependencies
import pandas as pd
from discord.ext import commands
from discord.ext.tasks import loop

from util.disc_util import get_channel

# Local dependencies
from util.vars import config, data_sources, get_json_data


class StockTwits(commands.Cog):
    """
    This class contains the cog for posting the most discussed StockTwits tickers.
    It can be enabled / disabled in the config under ["LOOPS"]["STOCKTWITS"].
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
        data = await get_json_data(
            "https://api.stocktwits.com/api/2/charts/" + keyword,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            },
        )

        # If no data could be found, return the embed
        if data == {}:
            return e

        table = pd.DataFrame(data["table"][keyword])
        stocks = pd.DataFrame(data["stocks"]).T
        stocks["stock_id"] = stocks.index.astype(int)
        full_df = pd.merge(stocks, table, on="stock_id")
        full_df.sort_values(by="val", ascending=False, inplace=True)

        # Set types
        full_df["price"] = full_df["price"].astype(float).fillna(0)
        full_df["change"] = full_df["change"].astype(float).fillna(0)
        full_df["symbol"] = full_df["symbol"].astype(str)
        full_df["name"] = full_df["name"].astype(str)

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
            color=data_sources["stocktwits"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        e = await self.get_data(e, "ts")
        e = await self.get_data(e, "m_day")
        e = await self.get_data(e, "wl_ct_day")

        # Set datetime and icon
        e.set_footer(
            text="\u200b",
            icon_url=data_sources["stocktwits"]["icon"],
        )

        await self.channel.send(embed=e)


def setup(bot: commands.bot.Bot) -> None:
    bot.add_cog(StockTwits(bot))
