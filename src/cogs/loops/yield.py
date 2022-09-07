# > Standard libraries
import os
import datetime

# > 3rd Party Dependencies
import matplotlib.pyplot as plt
from scipy.interpolate import make_interp_spline
import numpy as np

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, tv
from util.disc_util import get_channel

class Yield(commands.Cog):
    """
    This class contains the cog for posting the US and EU yield curve.
    It can be enabled / disabled in the config under ["LOOPS"]["YIELD"].

    Methods
    -------
    set_emojis() -> None
        This function gets and sets the emojis for the UW alerts.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = get_channel(self.bot, config["LOOPS"]["YIELD"]["CHANNEL"])

        self.post_curve.start()

    @loop(hours=24)
    async def post_curve(self):

        await self.plot_US_yield()
        await self.plot_EU_yield()

        # Set plot parameters
        plt.legend()
        plt.ylabel("Yield (%)")
        plt.xlabel("Years")

        # Convert to plot to a temporary image
        plt.savefig("yield.png", bbox_inches="tight")

        e = discord.Embed(
            title="US and EU Yield Curve Rates",
            description="",
            color=0xFFFFFF,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        file = discord.File("yield.png")
        e.set_image(url="attachment://yield.png")

        await self.channel.send(file=file, embed=e)

        # Delete yield.png
        os.remove("yield.png")

    async def plot_US_yield(self):

        years = np.array([0.08, 0.15, 0.25, 0.5, 1, 2, 3, 5, 7, 10, 20, 30])
        yield_percentage = await self.get_yield(tv.US_bonds)

        self.make_plot(years, yield_percentage, "b", "US")

    async def plot_EU_yield(self):
        years = np.array(
            [0.25, 0.5, 0.75, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 25, 30]
        )
        yield_percentage = await self.get_yield(tv.EU_bonds)

        self.make_plot(years, yield_percentage, "r", "EU")

    async def get_yield(self, bonds):

        yield_percentage = []
        for bond in bonds:
            no_exch = bond.split(":")[1]
            tv_data = await tv.get_tv_data(no_exch, "stock")
            yield_percentage.append(tv_data[0])

        return yield_percentage

    def make_plot(self, years, yield_percentage, color, label):

        new_X = np.linspace(years.min(), years.max(), 500)

        # Interpolation
        spl = make_interp_spline(years, yield_percentage, k=3)
        smooth = spl(new_X)

        # Make the plot
        plt.rcParams["figure.figsize"] = (10, 5)  # Set the figure size
        plt.plot(new_X, smooth, color, label=label)
        plt.plot(years, yield_percentage, f"{color}o")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Yield(bot))
