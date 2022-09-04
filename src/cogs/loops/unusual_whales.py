# Standard libraries
import datetime
import pandas as pd
import time
import inspect

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, get_json_data
from util.disc_util import get_channel, get_tagged_users
from util.afterhours import afterHours


class UW(commands.Cog):
    """
    This class contains the cog for posting the latest Unusual Whales alerts.
    It can be enabled / disabled in the config under ["LOOPS"]["UNUSUAL_WHALES"].

    Methods
    -------
    set_emojis() -> None
        This function gets and sets the emojis for the UW alerts.
    UW_data() -> dict:
        Get the alerts data of the last 5 minutes.
    alerts() -> None
        This function posts the Unusual Whales alerts on Discord.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji_dict = {}

        self.channel = get_channel(
            self.bot, config["LOOPS"]["UNUSUAL_WHALES"]["CHANNEL"]
        )

        self.alerts.start()

    async def set_emojis(self) -> None:
        """
        This function gets and sets the emojis for the UW alerts.
        It gets the emojis used by Unusual Whales and stores them in a dictionary.

        Returns
        -------
        None
        """

        # Use https://phx.unusualwhales.com/api/tags/all to get the emojis

        # Necessary header
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36"
        }

        # Get the emojis and store them in emoji_dict
        self.emoji_dict = await get_json_data(
            "https://phx.unusualwhales.com/api/tags/all", headers
        )

    async def UW_data(self) -> dict:
        """
        Get the alerts data of the last 5 minutes.

        Returns
        -------
        dict
            Dictionary object of the JSON data from the Unusual Whales API.
        """

        # start_date and expiry_start_data depends on how often the function is called
        last_5_min = int((time.time() - (5 * 60)) * 1000)

        # Check the last 5 minutes on the API
        url = f"https://phx.unusualwhales.com/api/option_quotes?offset=0&sort=timestamp&search=&sector=&tag=&end_date=9999999999999&start_date={last_5_min}&expiry_start_date={last_5_min}&expiry_end_date=9999999999999&min_ask=0&max_ask=9999999999999&volume_direction=desc&expiry_direction=desc&alerted_direction=desc&oi_direction=desc&normal=true"

        # Use the token in the header
        headers = {
            "authorization": config["LOOPS"]["UNUSUAL_WHALES"]["TOKEN"],
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36",
        }

        return await get_json_data(url, headers)

    @loop(minutes=5)
    async def alerts(self) -> None:
        """
        This function posts the Unusual Whales alerts on Discord.

        Returns
        -------
        None
        """

        # Check if the market is open
        if afterHours():
            return

        # Get the emojis if not already done
        if self.emoji_dict == {}:
            await self.set_emojis()

        df = pd.DataFrame(await self.UW_data())

        if df.empty:
            return

        # Only keep the important information
        df = df[
            [
                "timestamp",
                "id",
                "ticker_symbol",
                "option_type",
                "strike_price",  # Also named underlying
                "expires_at",
                "stock_price",
                "bid",
                "ask",
                "min_ask",
                "max_ask",
                "volume",
                "implied_volatility",
                "sector",
                "tags",
                "tier",
                "is_recommended",
                "open_interest",
            ]
        ]

        # For each ticker in the df send a message
        for _, row in df.iterrows():

            # Only use the first letter of the option type
            option_type = row["option_type"][0].upper()

            # Calculate the percentual difference between current price and strike price
            difference = round(
                (float(row["stock_price"]) - float(row["strike_price"]))
                / float(row["strike_price"])
                * 100,
                2,
            )

            emojis = ""
            for tag in row["tags"]:
                try:
                    emojis += self.emoji_dict[tag]["emoji"]
                # In case emoji_dict is empty
                except KeyError:
                    print(f"Could not find emoji for {tag}")

            # Create the embed
            e = discord.Embed(
                title=f"${row['ticker_symbol']} {row['expires_at']} {option_type} ${row['strike_price']}",
                url=f"https://unusualwhales.com/alerts/{row['id']}",
                # Use inspect.cleandoc() to remove the indentation
                description=inspect.cleandoc(
                    f"""
                    {emojis}
                    Bid-Ask: ${row['bid']} - ${row['ask']}
                    Interest: {row['open_interest']}
                    Volume: {row['volume']}
                    IV: {row['implied_volatility']}
                    % Diff: {difference}
                    Underlying: ${row['stock_price']}
                    Sector: {row['sector']}
                    Tier: {row['tier']}
                    Recommended: {row['is_recommended']}
                    """
                ),
                color=0xE40414 if option_type == "P" else 0x3CC474,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )

            e.set_footer(
                # Use the time the alert was created in the footer
                text=f"Alerted at {row['timestamp'].split('T')[1].split('Z')[0]}",
                icon_url="https://blog.unusualwhales.com/content/images/2021/08/logo.8f570f66-1.png",
            )

            await self.channel.send(content=get_tagged_users([row["ticker_symbol"]]), embed=e)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(UW(bot))
