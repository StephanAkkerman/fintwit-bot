import datetime

# > 3rd party dependencies
import pandas as pd

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, get_json_data
from util.disc_util import get_channel


class Funding(commands.Cog):
    """
    This class is used to handle the funding loop, this can be enabled / disabled in the config, under ["LOOPS"]["FUNDING"].

    Methods
    -------
    funding() -> None:
        This function gets the data from the funding API and posts it in the funding channel.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = get_channel(self.bot, config["LOOPS"]["FUNDING"]["CHANNEL"])

        self.funding.start()

    @loop(hours=4)
    async def funding(self) -> None:
        """
        This function gets the data from the funding API and posts it in the funding channel.

        Returns
        -------
        None
        """

        # Get the JSON data from the Binance API
        binance_data = await get_json_data(
            "https://fapi.binance.com/fapi/v1/premiumIndex"
        )

        # If the call did not work
        if not binance_data:
            print("Could not get funding data...")
            return

        # Cast to dataframe
        df = pd.DataFrame(binance_data)

        # Keep only the USDT pairs
        df = df[df["symbol"].str.contains("USDT")]

        # Remove USDT from the symbol
        df["symbol"] = df["symbol"].str.replace("USDT", "")

        # Set it to numeric
        df["lastFundingRate"] = df["lastFundingRate"].apply(pd.to_numeric)

        # Sort on lastFundingRate, lowest to highest
        sorted = df.sort_values(by="lastFundingRate", ascending=True)

        # Multiply by 100 to get the funding rate in percent
        sorted["lastFundingRate"] = sorted["lastFundingRate"] * 100

        # Round to 4 decimal places
        sorted["lastFundingRate"] = sorted["lastFundingRate"].round(4)

        # Convert them back to string
        sorted = sorted.astype(str)

        # Add percentage to it
        sorted["lastFundingRate"] = sorted["lastFundingRate"] + "%"

        # Post the top 15 lowest
        lowest = sorted.head(15)

        e = discord.Embed(
            title=f"Binance Top 15 Lowest Funding Rates",
            url="",
            description="",
            color=0xF0B90B,
            timestamp=datetime.datetime.utcnow(),
        )

        # Get time to next funding, unix is in milliseconds
        nextFundingTime = int(lowest["nextFundingTime"].tolist()[0]) // 1000
        nextFundingTime = datetime.datetime.fromtimestamp(nextFundingTime)

        # Get difference
        timeToNextFunding = nextFundingTime - datetime.datetime.now()

        # Set datetime and icon
        e.set_footer(
            text=f"Next funding in {str(timeToNextFunding).split('.')[0]}",
            icon_url="https://public.bnbstatic.com/20190405/eb2349c3-b2f8-4a93-a286-8f86a62ea9d8.png",
        )

        lowest_tickers = "\n".join(lowest["symbol"].tolist())
        lowest_rates = "\n".join(lowest["lastFundingRate"].tolist())

        e.add_field(
            name="Coin",
            value=lowest_tickers,
            inline=True,
        )

        e.add_field(
            name="Funding Rate",
            value=lowest_rates,
            inline=True,
        )

        # Post the embed in the channel
        await self.channel.send(embed=e)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Funding(bot))
