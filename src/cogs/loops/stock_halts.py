import datetime

import pandas as pd
from dateutil import tz

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, post_json_data
from util.disc_util import get_channel, get_tagged_users


class StockHalts(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = get_channel(self.bot, config["LOOPS"]["STOCK_HALTS"]["CHANNEL"])

        self.halt_embed.start()

    @loop(minutes=15)
    async def halt_embed(self):
        # Remove previous message first
        await self.channel.purge(limit=1)

        html = await self.get_halt_data()
        df = self.format_df(html)

        # Create embed
        e = discord.Embed(
            title=f"Halted Stocks",
            url="https://www.nasdaqtrader.com/trader.aspx?id=tradehalts",
            description="",
            color=0x0996C7,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        # Get the values as string
        time = "\n".join(df["Time"].to_list())
        symbol = "\n".join(df["Issue Symbol"].to_list())
        resumption = "\n".join(df["Resumption Time"].to_list())

        # Add the values to the embed
        e.add_field(name="Time", value=time, inline=True)
        e.add_field(name="Symbol", value=symbol, inline=True)
        e.add_field(name="Resumption Time", value=resumption, inline=True)

        e.set_footer(
            text="\u200b",
            icon_url="https://s3-symbol-logo.tradingview.com/nasdaq--600.png",
        )

        tags = get_tagged_users(df["Issue Symbol"].to_list())

        await self.channel.send(content=tags, embed=e)

    def format_df(self, html):
        df = pd.read_html(html["result"])[0]

        # Drop columns where halt date is not today
        df = df[df["Halt Date"] == pd.Timestamp.today().strftime("%m/%d/%Y")]

        # Combine columns into one singular datetime column
        df["Time"] = df["Halt Date"] + " " + df["Halt Time"]
        df["Time"] = pd.to_datetime(df["Time"], format="%m/%d/%Y %H:%M:%S")

        # Do for resumption as well
        df["Resumption Time"] = (
            df["Resumption Date"] + " " + df["Resumption Trade Time"]
        )
        df["Resumption Time"] = pd.to_datetime(
            df["Resumption Time"], format="%m/%d/%Y %H:%M:%S"
        )

        # Convert to my own timezone
        df["Time"] = df["Time"].dt.tz_localize("US/Eastern").dt.tz_convert(tz.tzlocal())
        df["Resumption Time"] = (
            df["Resumption Time"]
            .dt.tz_localize("US/Eastern")
            .dt.tz_convert(tz.tzlocal())
        )

        # Convert times to string
        df["Time"] = df["Time"].dt.strftime("%H:%M:%S")
        df["Resumption Time"] = df["Resumption Time"].dt.strftime("%H:%M:%S")

        # Replace NaN with ?
        df = df.fillna("?")

        # Keep the necessary columns
        return df[["Time", "Issue Symbol", "Resumption Time"]]

    async def get_halt_data(self) -> dict:
        # Based on https://github.com/reorx/nasdaqtrader-rss/blob/e675af99ace7d384950d6c75144e9efb1d80b5a7/rss/index.py#L18
        headers = {
            "Content-Type": "application/json",
            "Origin": "https://www.nasdaqtrader.com",
            "Referer": "https://www.nasdaqtrader.com/trader.aspx?id=tradehalts",
            "Sec-Ch-Ua": '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        }
        req_data = {
            "id": 3,
            "method": "BL_TradeHalt.GetTradeHalts",
            "params": "[]",
            "version": "1.1",
        }

        html = await post_json_data(
            "https://www.nasdaqtrader.com/RPCHandler.axd",
            headers=headers,
            json=req_data,
        )

        # Convert to DataFrame
        return html


def setup(bot: commands.Bot) -> None:
    """
    This is a necessary method to make the cog loadable.

    Returns
    -------
    None
    """
    bot.add_cog(StockHalts(bot))
