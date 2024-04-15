# Standard libraries
import datetime
import pandas as pd

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, get_json_data, data_sources
from util.disc_util import get_channel, get_guild
from util.formatting import human_format


async def get_UW_data(url, overwrite_headers=None, last_15min=False):
    if overwrite_headers is None:
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36",
        }
    else:
        headers = overwrite_headers

    data = await get_json_data(url, headers)
    df = pd.DataFrame(data)

    if df.empty:
        print("No UW data found for url:", url)
        return df

    # Get the timestamp convert to datetime and local time
    df["alert_time"] = pd.to_datetime(df["timestamp"], utc=True)

    # Filter df on last 15 minutes
    if last_15min:
        df = df[
            df["alert_time"]
            > datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=15)
        ]

        if df.empty:
            return df

    df["alert_time"] = df["alert_time"].dt.tz_convert(
        datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    )

    # Format to string
    df["alert_time"] = df["alert_time"].dt.strftime("%I:%M %p")

    return df


class Options(commands.Cog):
    """
    This class contains the cog for posting the latest Unusual Whales alerts.
    It can be enabled / disabled in the config under ["LOOPS"]["UNUSUAL_WHALES"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.guild = get_guild(bot)

        self.volume_channel = get_channel(
            self.bot, config["LOOPS"]["OPTIONS"]["VOLUME_CHANNEL"]
        )

        self.spacs_channel = get_channel(
            self.bot, config["LOOPS"]["OPTIONS"]["SPACS_CHANNEL"]
        )

        self.shorts_channel = get_channel(
            self.bot, config["LOOPS"]["OPTIONS"]["SHORTS_CHANNEL"]
        )

        self.volume.start()
        self.spacs.start()
        self.shorts.start()

    def make_UW_embed(self, row):
        e = discord.Embed(
            title=f"${row['ticker_symbol']}",
            url=f"https://unusualwhales.com/stock/{row['ticker_symbol']}",
            description="",
            color=self.guild.self_role.color,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        e.add_field(
            name="Volume", value=f"${human_format(float(row['volume']))}", inline=True
        )
        e.add_field(
            name="Average 30d Volume",
            value=f"${human_format(float(row['avg_volume_last_30_days']))}",
            inline=True,
        )
        e.add_field(
            name="Volume Deviation",
            value=f"{round(float(row['volume_dev_from_norm']))}",
            inline=True,
        )
        e.add_field(name="Price", value=f"${row['bid_price']}", inline=True)

        e.set_footer(
            # Use the time the alert was created in the footer
            text=f"Alerted at {row['alert_time']}",
            icon_url=data_sources["unusualwhales"]["icon"],
        )

        return e

    @loop(minutes=15)
    async def volume(self):
        url = "https://phx.unusualwhales.com/api/stock_feed"
        df = await get_UW_data(url, last_15min=True)

        if not df.empty:
            # Iterate over each row and post the alert
            for _, row in df.iterrows():
                e = self.make_UW_embed(row)
                await self.volume_channel.send(embed=e)

    @loop(minutes=15)
    async def spacs(self):
        url = "https://phx.unusualwhales.com/api/warrant_alerts"
        df = await get_UW_data(url, last_15min=True)

        if not df.empty:
            # Iterate over each row and post the alert
            for _, row in df.iterrows():
                e = self.make_UW_embed(row)
                await self.spacs_channel.send(embed=e)

    @loop(hours=24)
    async def shorts(self):
        url = "https://phx.unusualwhales.com/api/short_interest_low"
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36",
        }

        data = await get_json_data(url, headers)
        df = pd.DataFrame(data["data"])

        if df.empty:
            return

        # Cast to float
        df["short_interest"] = df["short_interest"].astype(float)

        # Sort on short_interest
        df = df.sort_values(by="short_interest", ascending=False)
        df["float_shares"] = df["float_shares"].astype(float)
        df["float_shares"] = df["float_shares"].apply(lambda x: human_format(x))

        df["outstanding"] = df["outstanding"].astype(float)
        df["outstanding"] = df["outstanding"].apply(lambda x: human_format(x))

        df["short_interest"] = df["short_interest"].astype(str)

        # Combine both in 1 string
        df["float - outstanding"] = df["float_shares"] + " - " + df["outstanding"]

        top20 = df.head(20)

        symbols = "\n".join(top20["symbol"].tolist())
        float_oustanding = "\n".join(top20["float - outstanding"].tolist())
        short_interest = "\n".join(top20["short_interest"].tolist())

        # Only show the top 20 as embed
        e = discord.Embed(
            title=f"Top Short Interest Reported",
            url=f"https://unusualwhales.com/shorts",
            description="",
            color=self.guild.self_role.color,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        e.set_footer(
            # Use the time the alert was created in the footer
            text="\u200b",
            icon_url=data_sources["unusualwhales"]["icon"],
        )

        e.add_field(name="Symbol", value=symbols, inline=True)
        e.add_field(name="Float - Outstanding", value=float_oustanding, inline=True)
        e.add_field(name="Short Interest", value=short_interest, inline=True)

        await self.shorts_channel.purge(limit=1)
        await self.shorts_channel.send(embed=e)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Options(bot))
