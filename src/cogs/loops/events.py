import datetime
import re
from io import StringIO

import discord
import pandas as pd
from bs4 import BeautifulSoup
from discord.ext import commands
from discord.ext.tasks import loop

from api.http_client import get_json_data
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
            self.forex_channel = None
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
        if self.forex_channel is None:
            self.forex_channel = await get_channel(
                self.bot,
                config["LOOPS"]["EVENTS"]["CHANNEL"],
                config["CATEGORIES"]["FOREX"],
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
        await self.forex_channel.purge()
        await self.forex_channel.send(embed=e)

    async def get_crypto_calendar(self) -> pd.DataFrame:
        """
        Gets the economic calendar from CryptoCraft.com for the next week.

        Returns
        -------
        pd.DataFrame
            The formatted DataFrame containing the economic calendar.
        """
        html = await get_json_data(
            url="https://www.cryptocraft.com/calendar",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4240.193 Safari/537.36"
            },
            text=True,
        )

        soup = BeautifulSoup(html, "html.parser")

        # Get the first table
        table = soup.find("table")

        impact_emoji = {
            "yel": "🟨",
            "ora": "🟧",
            "red": "🟥",
            "gra": "⬜",
        }

        impacts = []
        for row in table.find_all("tr")[2:]:  # Skip the header row
            # Get the impact value from the span class including "impact"
            impact = row.find("span", class_=lambda s: s and "impact" in s)
            if impact:
                impact = impact.get("class", [])[-1][-3:]
                impacts.append(impact_emoji[impact])

        # Convert the table to a string and read it into a DataFrame
        df = pd.read_html(StringIO(str(table)))[0]

        # Drop the first row
        df = df.iloc[1:]

        # Drop rows where the first and second column values are the same
        df = df[df.iloc[:, 0] != df.iloc[:, 1]]

        # Convert MultiIndex columns to regular columns
        df.columns = ["_".join(col).strip() for col in df.columns.values]

        # Rename second column to time and fifth column to event
        df.rename(
            columns={
                df.columns[0]: "date",
                df.columns[1]: "time",
                df.columns[4]: "event",
                df.columns[6]: "actual",
                df.columns[7]: "forecast",
                df.columns[8]: "previous",
            },
            inplace=True,
        )

        # Drop third and fourth column
        df.drop(df.columns[[2, 3, 5, 9]], axis=1, inplace=True)

        # Remove rows where event is NaN
        df = df[df["event"].notna()]

        # Reset index
        df.reset_index(drop=True, inplace=True)

        # Add impact column
        df["impact"] = impacts

        # Use ffill() for forward fill
        df["time"] = df["time"].ffill()

        # Mask for entries where 'time' does not match common time patterns (only checks for absence of typical hour-minute time format)
        mask_no_time_pattern = df["time"].str.contains(
            r"^\D*$|day", flags=re.IGNORECASE, na=False
        )
        # Mask for entries with specific time (i.e., typical time patterns are present)
        mask_time_specific = ~mask_no_time_pattern

        # Convert 'All Day' entries by appending the current year and no specific time
        df.loc[mask_no_time_pattern, "datetime"] = pd.to_datetime(
            df.loc[mask_no_time_pattern, "date"]
            + " "
            + str(datetime.datetime.now().year),
            format="%a %b %d %Y",
            errors="coerce",
        )

        # Convert specific time entries by appending the current year and the specific time
        df.loc[mask_time_specific, "datetime"] = pd.to_datetime(
            df.loc[mask_time_specific, "date"]
            + " "
            + str(datetime.datetime.now().year)
            + " "
            + df.loc[mask_time_specific, "time"],
            format="%a %b %d %Y %I:%M%p",
            errors="coerce",
        )

        return df

    @loop(hours=24)
    @loop_error_catcher
    async def post_crypto_events(self):
        if self.crypto_channel is None:
            self.crypto_channel = await get_channel(
                self.bot,
                config["LOOPS"]["EVENTS"]["CHANNEL"],
                config["CATEGORIES"]["CRYPTO"],
            )

        df = await self.get_crypto_calendar()

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
