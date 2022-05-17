# Standard libraries
import datetime

# > 3rd party dependencies
import yahoo_fin.stock_info as si

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config
from util.disc_util import get_channel
from util.afterhours import afterHours
from util.formatting import format_embed


class Losers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        if config["LOOPS"]["LOSERS"]["STOCKS"]["ENABLED"]:
            self.channel = get_channel(self.bot, config["LOOPS"]["LOSERS"]["STOCKS"]["CHANNEL"])
            self.losers.start()

    @loop(hours=2)
    async def losers(self):
        # Dont send if the market is closed
        if afterHours():
            return

        try:
            losers = si.get_day_losers()[
                ["Symbol", "Price (Intraday)", "% Change", "Volume"]
            ].head(50)
        except Exception:
            print("Failed to get losers")
            return

        losers.rename(columns={"Price (Intraday)": "Price"}, inplace=True)

        e = await format_embed(losers, "Losers", "yahoo")

        await self.channel.send(embed=e)

def setup(bot):
    bot.add_cog(Losers(bot))
