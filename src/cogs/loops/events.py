import pytz
import datetime
from lxml.html import fromstring
from io import StringIO

# 3rd party imports
import pandas as pd
from bs4 import BeautifulSoup

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, post_json_data, data_sources, get_json_data
from util.disc_util import get_channel


class Events(commands.Cog):
    """
    This class is responsible for sending weekly overview of upcoming events.
    You can enable / disable this command in the config, under ["LOOPS"]["EVENTS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["EVENTS"]["FOREX"]["ENABLED"]:
            self.forex_channel = get_channel(
                self.bot,
                config["LOOPS"]["EVENTS"]["CHANNEL"],
                config["CATEGORIES"]["FOREX"],
            )
            self.post_events.start()

        if config["LOOPS"]["EVENTS"]["CRYPTO"]["ENABLED"]:
            self.crypto_channel = get_channel(
                self.bot,
                config["LOOPS"]["EVENTS"]["CHANNEL"],
                config["CATEGORIES"]["CRYPTO"],
            )
            self.post_crypto_events.start()

    async def get_events(self):
        """
        Gets the economic calendar from Investing.com for the next week.
        The data contains the most important information for the USA and EU.

        Forked from: https://github.com/alvarobartt/investpy/blob/master/investpy/news.py
        """

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
        }

        data = {
            "country[]": [72, 5],  # USA and EU
            "importance[]": 3,  # Highest importance, 3 stars
            "timeZone": 8,
            "timeFilter": "timeRemain",
            "currentTab": "nextWeek",
            "submitFilters": 1,
            "limit_from": 0,
        }

        url = "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData"

        req = await post_json_data(url, headers=headers, data=data)
        root = fromstring(req["data"])
        table = root.xpath(".//tr")

        results = []

        for reversed_row in table[::-1]:
            id_ = reversed_row.get("id")
            if id_ is not None:
                id_ = id_.replace("eventRowId_", "")

        for row in table:
            id_ = row.get("id")
            if id_ == None:
                curr_timescope = int(row.xpath("td")[0].get("id").replace("theDay", ""))
                curr_date = datetime.datetime.fromtimestamp(
                    curr_timescope, tz=pytz.timezone("GMT")
                ).strftime("%d/%m/%Y")
            else:
                id_ = id_.replace("eventRowId_", "")

                time = zone = currency = event = actual = forecast = previous = None

                if row.get("id").__contains__("eventRowId_"):
                    for value in row.xpath("td"):
                        if value.get("class").__contains__("first left"):
                            time = value.text_content()
                        elif value.get("class").__contains__("flagCur"):
                            zone = value.xpath("span")[0].get("title").lower()
                            currency = value.text_content().strip()
                        elif value.get("class") == "left event":
                            event = value.text_content().strip()
                        elif value.get("id") == "eventActual_" + id_:
                            actual = value.text_content().strip()
                        elif value.get("id") == "eventForecast_" + id_:
                            forecast = value.text_content().strip()
                        elif value.get("id") == "eventPrevious_" + id_:
                            previous = value.text_content().strip()

                results.append(
                    {
                        "id": id_,
                        "date": curr_date,
                        "time": time,
                        "zone": zone,
                        "currency": None if currency == "" else currency,
                        "event": event,
                        "actual": None if actual == "" else actual,
                        "forecast": None if forecast == "" else forecast,
                        "previous": None if previous == "" else previous,
                    }
                )

        return pd.DataFrame(results)

    @loop(hours=1)
    async def post_events(self):
        """
        Checks every hour if today is a friday and if the market is closed.
        If that is the case a overview will be posted with the upcoming earnings.

        Returns
        ----------
        None
        """

        # Send this message every friday at 23:00 UTC
        if datetime.datetime.today().weekday() == 4:
            if datetime.datetime.utcnow().hour == 23:
                df = await self.get_events()

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

                # Replace zone names

                df["zone"].replace(
                    {"euro zone": "🇪🇺", "united states": "🇺🇸"},
                    inplace=True,
                )

                time = "\n".join(df["timestamp"])

                # Do this if both forecast and previous are not NaN
                if (
                    not df["forecast"].isnull().all()
                    and not df["previous"].isnull().all()
                ):
                    df["forecast|previous"] = df["forecast"] + " | " + df["previous"]
                    for_prev = "\n".join(df["forecast|previous"].astype(str))
                    for_prev_title = "Forecast | Previous"

                else:
                    for_prev_title = "Previous"
                    for_prev = "\n".join(df["previous"].astype(str))

                df["info"] = df["zone"] + " " + df["event"]
                info = "\n".join(df["info"])

                # Make an embed with these tickers and their earnings date + estimation
                e = discord.Embed(
                    title=f"Events Upcoming Week",
                    url=f"https://www.investing.com/economic-calendar/",
                    description="",
                    color=data_sources["investing"]["color"],
                    timestamp=datetime.datetime.now(datetime.timezone.utc),
                )

                e.add_field(name="Date", value=time, inline=True)
                e.add_field(name="Event", value=info, inline=True)
                e.add_field(name=for_prev_title, value=for_prev, inline=True)

                e.set_footer(
                    text="\u200b",
                    icon_url=data_sources["investing"]["icon"],
                )

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

        # Add the current year to the date string and convert to datetime
        df["datetime"] = pd.to_datetime(
            df["date"] + " " + str(datetime.datetime.now().year) + " " + df["time"],
            format="%a %b %d %Y %I:%M%p",
            errors="coerce",
        )

        return df

    @loop(hours=24)
    async def post_crypto_events(self):
        df = await self.get_crypto_calendar()

        # Make an embed with these tickers and their earnings date + estimation
        e = discord.Embed(
            title=f"Upcoming Crypto Events",
            url=f"https://www.cryptocraft.com/calendar",
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
