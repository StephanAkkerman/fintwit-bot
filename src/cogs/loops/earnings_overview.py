import datetime

# > Discord dependencies
import discord

# > 3rd party dependencies
import pandas as pd

# Local dependencies
import util.vars
from discord.ext import commands
from discord.ext.tasks import loop
from util.disc_util import get_channel, get_tagged_users
from util.vars import config, data_sources
from yahoo_fin.stock_info import get_earnings_in_date_range


class Earnings_Overview(commands.Cog):
    """
    This class is responsible for sending weekly overview of upcoming earnings.
    You can enable / disable this command in the config, under ["LOOPS"]["EARNINGS_OVERVIEW"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = get_channel(
            self.bot, config["LOOPS"]["EARNINGS_OVERVIEW"]["CHANNEL"]
        )

        self.earnings.start()

    def earnings_embed(self, df: pd.DataFrame, date: str) -> tuple[str, discord.Embed]:
        # Create lists of the important info
        tickers = "\n".join(df["ticker"].to_list())

        time_type = "\n".join(df["startdatetimetype"].to_list())

        epsestimate = "\n".join(df["epsestimate"].replace("nan", "N/A").to_list())

        # Make an embed with these tickers and their earnings date + estimation
        e = discord.Embed(
            title=f"Earnings for {date}",
            url=f"https://finance.yahoo.com/calendar/earnings?day={date}",
            description="",
            color=data_sources["yahoo"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        e.add_field(name="Stock", value=tickers, inline=True)
        e.add_field(name="Time", value=time_type, inline=True)
        e.add_field(name="Estimate", value=epsestimate, inline=True)

        e.set_footer(
            text="\u200b",
            icon_url=data_sources["yahoo"]["icon"],
        )

        tags = get_tagged_users(df["ticker"].to_list())

        return tags, e

    def get_earnings_in_date_range(self, start_date, end_date) -> list[pd.DataFrame]:
        dfs = []
        for i in range((end_date - start_date).days + 1):
            date = start_date + datetime.timedelta(days=i)
            df = self.get_earnings_for_date(date)
            dfs.append(df)

        return dfs

    def get_earnings_for_date(self, date: datetime.datetime) -> pd.DataFrame:
        # Convert datetime to string YYYY-MM-DD
        import requests

        date = date.strftime("%Y-%m-%d")
        url = f"https://api.nasdaq.com/api/calendar/earnings?date={date}"
        # Add headers to avoid 403 error
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en,nl-NL;q=0.9,nl;q=0.8,en-CA;q=0.7,ja;q=0.6",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        }
        json = requests.get(url, headers=headers).json()
        # Automatically ordered from highest to lowest market cap
        df = pd.DataFrame(json["data"]["rows"])
        # Replace time with emojis
        emoji_dict = {
            "time-after-hours": "🌙",
            "time-pre-market": "🌞",
            "time-not-supplied": "❓",
        }
        df["time"] = df["time"].replace(emoji_dict)
        return df

    @loop(hours=1)
    async def earnings(self) -> None:
        """
        Checks every hour if today is a sunday and if the market is closed.
        If that is the case a overview will be posted with the upcoming earnings.

        Returns
        ----------
        None
        """

        # Send this message every sunday at 12:00 UTC
        if datetime.datetime.today().weekday() == 4:
            if datetime.datetime.utcnow().hour == 12:
                # Monday to Friday
                earnings = get_earnings_in_date_range(
                    datetime.datetime.now() + datetime.timedelta(days=1),
                    datetime.datetime.now() + datetime.timedelta(days=6),
                )
                earnings_df = pd.DataFrame(earnings)
                if earnings_df.empty:
                    print("No earnings found")
                    return

                # Filter on unique tickers in the nasdaq list
                earnings_df = earnings_df[
                    earnings_df["ticker"].isin(util.vars.nasdaq_tickers)
                ]

                earnings_df = earnings_df.drop_duplicates(subset="ticker")

                # Split dataframe based on date
                earnings_df["date"] = pd.to_datetime(
                    earnings_df["startdatetime"]
                ).dt.date

                dates = earnings_df["date"].unique()

                for date in dates:
                    date_df = earnings_df.loc[earnings_df["date"] == date]

                    # Necessary for using inplace operations below
                    date_df_copy = date_df.copy()

                    # Format the dataframe
                    date_df_copy.sort_values(by="ticker", inplace=True)

                    # AMC after market close (After-hours)
                    # BMO before market open (Pre-market)
                    # TNS Time not supplied (Unknown)
                    date_df_copy["startdatetimetype"].replace(
                        {
                            "AMC": "After-hours",
                            "BMO": "Pre-market",
                            "TNS": "Unknown",
                            "TAS": "Unknown",
                        },
                        inplace=True,
                    )

                    date_df_copy = date_df_copy.astype({"epsestimate": str})

                    split = 50
                    while not date_df_copy.iloc[split - 50 : split].empty:
                        tags, e = self.earnings_embed(
                            date_df_copy.iloc[split - 50 : split], date
                        )
                        await self.channel.send(content=tags, embed=e)
                        split += split


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Earnings_Overview(bot))
