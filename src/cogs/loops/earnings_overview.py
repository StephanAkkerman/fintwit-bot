import datetime

import discord
import pandas as pd
from discord.ext import commands
from discord.ext.tasks import loop

from api.nasdaq import get_earnings_for_date
from constants.config import config
from constants.logger import logger
from constants.sources import data_sources
from util.disc import get_channel, get_tagged_users, loop_error_catcher


class Earnings_Overview(commands.Cog):
    """
    This class is responsible for sending weekly overview of upcoming earnings.
    You can enable / disable this command in the config, under ["LOOPS"]["EARNINGS_OVERVIEW"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = None

        self.earnings.start()

    def earnings_embed(self, df: pd.DataFrame, date: str) -> tuple[str, discord.Embed]:
        # Create lists of the important info
        tickers = "\n".join(df["symbol"].to_list())
        time_type = "\n".join(df["time"].to_list())
        epsestimate = "\n".join(df["epsForecast"].replace("nan", "N/A").to_list())

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

        tags = get_tagged_users(df["symbol"].to_list())

        return tags, e

    async def get_earnings_in_date_range(
        self, start_date, end_date
    ) -> list[pd.DataFrame]:
        dfs = []
        for i in range((end_date - start_date).days + 1):
            date = start_date + datetime.timedelta(days=i)
            df = await get_earnings_for_date(date)
            dfs.append(df)

        return dfs

    def date_check(self) -> bool:
        """
        Check if today is a sunday and if it's 12 o'clock.

        Returns
        ----------
        bool:
            True if today is a sunday and the market is closed.
        """

        if (
            datetime.datetime.today().weekday() == 6
            and datetime.datetime.utcnow().hour == 12
        ):
            return True
        return False

    @loop(hours=1)
    @loop_error_catcher
    async def earnings(self) -> None:
        """
        Checks every hour if today is a sunday and if the market is closed.
        If that is the case a overview will be posted with the upcoming earnings.

        Returns
        ----------
        None
        """
        if self.channel is None:
            self.channel = await get_channel(
                self.bot, config["LOOPS"]["EARNINGS_OVERVIEW"]["CHANNEL"]
            )

        # Send this message every sunday at 12:00 UTC
        if self.date_check():
            end_date = datetime.datetime.now() + datetime.timedelta(days=6)
            start_date = datetime.datetime.now() + datetime.timedelta(days=1)
            earnings_dfs = await self.get_earnings_in_date_range(
                start_date,
                end_date,
            )

            for earnings_df, i in zip(
                earnings_dfs, range((end_date - start_date).days + 1)
            ):
                date = start_date + datetime.timedelta(days=i)
                date_string = date.strftime("%Y-%m-%d")

                if earnings_df.empty:
                    logger.warn(f"No earnings found for {date_string}")
                    continue

                # Only use the top 10 per dataframe
                # Could change this in min. 1 billion USD market cap

                tags, e = self.earnings_embed(earnings_df.head(10), date_string)
                await self.channel.send(content=tags, embed=e)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Earnings_Overview(bot))
