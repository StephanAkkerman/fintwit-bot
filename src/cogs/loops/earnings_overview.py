import datetime

# > 3rd party dependencies
import pandas as pd
from yahoo_fin.stock_info import tickers_nasdaq, get_earnings_in_date_range

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config
from util.disc_util import get_channel, get_tagged_users


class Earnings_Overview(commands.Cog):
    """
    This class is responsible for sending weekly overview of upcoming earnings.

    Methods
    ----------
    earnings() -> None:
        Sends the earnings overview to the channel.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = get_channel(self.bot, config["LOOPS"]["EARNINGS_OVERVIEW"]["CHANNEL"])

        self.nasdaq_tickers = tickers_nasdaq()

        self.earnings.start()

    @loop(hours=1)
    async def earnings(self) -> None:
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

                earnings = get_earnings_in_date_range(
                    datetime.datetime.now(),
                    datetime.datetime.now() + datetime.timedelta(days=7),
                )
                earnings_df = pd.DataFrame(earnings)

                # Filter on unique tickers in the nasdaq list
                earnings_df = earnings_df[
                    earnings_df["ticker"].isin(self.nasdaq_tickers)
                ]

                earnings_df = earnings_df.drop_duplicates(subset="ticker")

                # Split dataframe based on date
                earnings_df["date"] = pd.to_datetime(
                    earnings_df["startdatetime"]
                ).dt.date

                dates = earnings_df["date"].unique()

                for date in dates:
                    date_df = earnings_df.loc[earnings_df["date"] == date]

                    # Necessary for using .replace()
                    date_df_copy = date_df.copy()

                    # Create lists of the important info
                    tickers = "\n".join(date_df["ticker"].to_list())
                    # AMC after market close (After-hours)
                    # BMO before market open (Pre-market)
                    # TNS Time not supplied (Unknown)
                    date_df_copy["startdatetimetype"].replace(
                        {"AMC": "After-hours", "BMO": "Pre-market", "TNS": "Unknown"},
                        inplace=True,
                    )
                    time_type = "\n".join(date_df_copy["startdatetimetype"].to_list())

                    date_df = date_df.astype({"epsestimate": str})

                    epsestimate = "\n".join(
                        date_df["epsestimate"].replace("nan", "N/A").to_list()
                    )

                    # Make an embed with these tickers and their earnings date + estimation
                    e = discord.Embed(
                        title=f"Earnings for {date}",
                        url=f"https://finance.yahoo.com/calendar/earnings?day={date}",
                        description="",
                        color=0x720E9E,
                        timestamp=datetime.datetime.now(datetime.timezone.utc),
                    )

                    e.add_field(name="Stock", value=tickers, inline=True)
                    e.add_field(name="Time", value=time_type, inline=True)
                    e.add_field(name="Estimate", value=epsestimate, inline=True)

                    e.set_footer(
                        text="\u200b",
                        icon_url="https://s.yimg.com/cv/apiv2/myc/finance/Finance_icon_0919_250x252.png",
                    )

                    tags = get_tagged_users(date_df["ticker"].to_list())
                    await self.channel.send(content=tags, embed=e)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Earnings_Overview(bot))
