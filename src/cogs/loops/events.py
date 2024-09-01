import datetime

import discord
import pandas as pd
from discord.ext import commands
from discord.ext.tasks import loop

from api.cryptocraft import get_crypto_calendar
from api.investing import get_events
from constants.config import config
from constants.sources import data_sources
from util.disc import get_channel, loop_error_catcher


class Events(commands.Cog):
    """
    This class is responsible for sending weekly overview of upcoming events.
    You can enable / disable this command in the config, under ["LOOPS"]["EVENTS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["EVENTS"]["STOCKS"]["ENABLED"]:
            self.stocks_channel = None
            self.post_events.start()

        if config["LOOPS"]["EVENTS"]["CRYPTO"]["ENABLED"]:
            self.crypto_channel = None
            self.post_crypto_events.start()

    @loop(hours=6)
    @loop_error_catcher
    async def post_events(self):
        """
        Checks every hour if today is a friday and if the market is closed.
        If that is the case a overview will be posted with the upcoming earnings.

        Returns
        ----------
        None
        """
        if self.stocks_channel is None:
            self.stocks_channel = await get_channel(
                self.bot,
                config["LOOPS"]["EVENTS"]["CHANNEL"],
                config["CATEGORIES"]["STOCKS"],
            )

        df = await get_events()

        # If time == "All Day" convert it to 00:00
        df["time"] = df["time"].str.replace("All Day", "00:00")

        # Create datetime
        df["datetime"] = pd.to_datetime(
            df["date"] + " " + df["time"],
            format="%d/%m/%Y %H:%M",
        )

        # Convert datetime to unix timestamp
        df["timestamp"] = df["datetime"].astype("int64") // 10**9

        # Convert timestamp to Discord timestamp using mode F
        df["timestamp"] = df["timestamp"].apply(lambda x: f"<t:{int(x)}:d>")

        # Replace zone names with emojis
        df["zone"] = df["zone"].replace({"euro zone": "🇪🇺", "united states": "🇺🇸"})
        time = "\n".join(df["timestamp"])

        # Do this if both forecast and previous are not NaN
        # Combine 'actual', 'forecast', and 'previous' into a single column
        df["Actual | Forecast | Previous"] = df.apply(
            lambda row: f"{row['actual'] or '~'} | {row['forecast'] or '~'} | {row['previous'] or '~'}",
            axis=1,
        )
        for_prev = "\n".join(df["Actual | Forecast | Previous"])

        df["info"] = df["zone"] + " " + df["event"]
        info = "\n".join(df["info"])

        # Make an embed with these tickers and their earnings date + estimation
        e = discord.Embed(
            title="Events This Week",
            url="https://www.investing.com/economic-calendar/",
            description="",
            color=data_sources["investing"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        e.add_field(name="Date", value=time, inline=True)
        e.add_field(name="Event", value=info, inline=True)
        e.add_field(name="Actual | Forecast | Previous", value=for_prev, inline=True)

        e.set_footer(
            text="\u200b",
            icon_url=data_sources["investing"]["icon"],
        )

        # Remove the previous message
        await self.stocks_channel.purge()
        await self.stocks_channel.send(embed=e)

    @loop(hours=24)
    @loop_error_catcher
    async def post_crypto_events(self):
        if self.crypto_channel is None:
            self.crypto_channel = await get_channel(
                self.bot,
                config["LOOPS"]["EVENTS"]["CHANNEL"],
                config["CATEGORIES"]["CRYPTO"],
            )

        df = await get_crypto_calendar()

        if df.empty:
            return

        # Make an embed with these tickers and their earnings date + estimation
        e = discord.Embed(
            title="Upcoming Crypto Events",
            url="https://www.cryptocraft.com/calendar",
            description="",
            color=data_sources["cryptocraft"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        # Convert datetime to unix timestamp
        df["timestamp"] = df["datetime"].astype("int64") // 10**9

        # Convert timestamp to Discord timestamp using mode F
        df["timestamp"] = df["timestamp"].apply(lambda x: f"<t:{int(x)}:d>")

        date = "\n".join(df["timestamp"])
        event = "\n".join(df["event"])
        impact = "\n".join(df["impact"])

        e.add_field(name="Date", value=date, inline=True)
        e.add_field(name="Event", value=event, inline=True)
        e.add_field(name="Impact", value=impact, inline=True)

        e.set_footer(
            text="\u200b",
            icon_url=data_sources["cryptocraft"]["icon"],
        )

        await self.crypto_channel.send(embed=e)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Events(bot))
