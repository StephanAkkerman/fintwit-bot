import pytz
import datetime
from lxml.html import fromstring

# 3rd party imports
import pandas as pd

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, post_json_data
from util.disc_util import get_channel


class Events(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = get_channel(self.bot, config["LOOPS"]["EVENTS"]["CHANNEL"])

        self.post_events.start()

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
                
                events_df = await self.get_events()

                # Split dataframe based on date
                for date in events_df["date"].unique():
                    date_df = events_df.loc[events_df["date"] == date]
                    
                    if date_df.empty:
                        continue

                    # Necessary for using .replace()
                    date_df_copy = date_df.copy()

                    date_df_copy["zone"].replace(
                        {"euro zone": "EU", "united states": "USA"},
                        inplace=True,
                    )

                    time = "\n".join(date_df["time"])

                    date_df_copy["forecast|previous"] = (
                        date_df_copy["forecast"] + " | " + date_df_copy["previous"]
                    )
                    for_prev = "\n".join(date_df_copy["forecast|previous"].astype(str))

                    date_df_copy["info"] = date_df_copy["zone"] + ": " + date_df_copy["event"]
                    info = "\n".join(date_df_copy["info"])

                    # Make an embed with these tickers and their earnings date + estimation
                    e = discord.Embed(
                        title=f"Events on {date}",
                        url=f"https://www.investing.com/economic-calendar/",
                        description="",
                        color=0xDC8F02,
                        timestamp=datetime.datetime.now(datetime.timezone.utc),
                    )

                    e.add_field(name="Time", value=time, inline=True)
                    e.add_field(name="Event", value=info, inline=True)
                    e.add_field(name="Forecast | Previous", value=for_prev, inline=True)

                    e.set_footer(
                        text="\u200b",
                        icon_url="https://play-lh.googleusercontent.com/fJg2QmhVNd-LGxfBzNC6NPeUFY7EjoolG89dVOJ25ieyKpn3r7_ix1q93EFxI_s0RmE",
                    )

                    await self.channel.send(embed=e)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Events(bot))
