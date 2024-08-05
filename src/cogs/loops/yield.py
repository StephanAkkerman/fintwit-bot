import datetime
import os

import discord
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from discord.ext import commands
from discord.ext.tasks import loop
from scipy.interpolate import make_interp_spline

from api.tradingview import tv
from constants.config import config
from constants.tradingview import EU_bonds, US_bonds
from util.disc import get_channel, loop_error_catcher


class Yield(commands.Cog):
    """
    This class contains the cog for posting the US and EU yield curve.
    It can be enabled / disabled in the config under ["LOOPS"]["YIELD"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = None
        self.post_curve.start()

    @loop(hours=24)
    @loop_error_catcher
    async def post_curve(self) -> None:
        """
        Posts the US and EU yield curve in the channel specified in the config.
        Charts based on http://www.worldgovernmentbonds.com/country/united-states/

        Returns
        -------
        None
        """
        if self.channel is None:
            self.channel = await get_channel(
                self.bot, config["LOOPS"]["YIELD"]["CHANNEL"]
            )

        plt.style.use("dark_background")  # Set the style first

        mpl.rcParams["axes.spines.right"] = False
        mpl.rcParams["axes.spines.left"] = False
        mpl.rcParams["axes.spines.top"] = False
        mpl.rcParams["axes.spines.bottom"] = False

        mpl.rcParams["axes.edgecolor"] = "white"  # Set edge color to white
        mpl.rcParams["xtick.color"] = "white"  # Set x tick color to white
        mpl.rcParams["ytick.color"] = "white"  # Set y tick color to white
        mpl.rcParams["axes.labelcolor"] = "white"  # Set label color to white
        mpl.rcParams["text.color"] = "white"  # Set text color to white

        await self.plot_US_yield()
        await self.plot_EU_yield()

        # Add gridlines
        plt.grid(axis="y", color="grey", linewidth=0.5, alpha=0.5)
        plt.tick_params(axis="y", which="both", left=False)

        frame = plt.gca()
        frame.axes.get_xaxis().set_major_formatter(lambda x, _: f"{int(x)}Y")

        frame.axes.set_ylim(0)
        frame.axes.get_yaxis().set_major_formatter(lambda x, _: f"{int(x)}%")

        # Set plot parameters
        plt.legend(loc="lower center", ncol=2)
        plt.xlabel("Residual Maturity")

        # Convert to plot to a temporary image
        file_name = "yield.png"
        file_path = os.path.join("temp", file_name)
        plt.savefig(file_path, bbox_inches="tight", dpi=300)
        plt.cla()
        plt.close()

        e = discord.Embed(
            title="US and EU Yield Curve Rates",
            description="",
            color=0x000000,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        file = discord.File(file_path, filename=file_name)
        e.set_image(url=f"attachment://{file_name}")

        await self.channel.purge(limit=1)
        await self.channel.send(file=file, embed=e)

        # Delete yield.png
        os.remove(file_path)

    async def plot_US_yield(self) -> None:
        """
        Gets the US yield curve data from TradingView and plots it.
        """

        years = np.array([0.08, 0.15, 0.25, 0.5, 1, 2, 3, 5, 7, 10, 20, 30])
        yield_percentage = await self.get_yield(US_bonds)

        self.make_plot(years, yield_percentage, "c", "US")

    async def plot_EU_yield(self):
        """
        Gets the EU yield curve data from TradingView and plots it.
        """

        years = np.array(
            [0.25, 0.5, 0.75, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 25, 30]
        )
        yield_percentage = await self.get_yield(EU_bonds)

        self.make_plot(years, yield_percentage, "r", "EU")

    async def get_yield(self, bonds: list) -> list:
        """
        For each bond in the given list, it gets the yield from TradingView.

        Parameters
        ----------
        bonds : list
            The names of the bonds to get the yield from.

        Returns
        -------
        list
            The percentages of the yield for each bond.
        """

        yield_percentage = []
        for bond in bonds:
            no_exch = bond.split(":")[1]
            tv_data = await tv.get_tv_data(no_exch, "forex")
            yield_percentage.append(tv_data[0])

        return yield_percentage

    def make_plot(
        self, years: list, yield_percentage: list, color: str, label: str
    ) -> None:
        """
        Makes a matplotlib plot of the yield curve.
        Each dot is the yield for a specific bond.
        Connects a spline through the dots to make a smooth curve.

        Parameters
        ----------
        years : list
            The years of the yield curve.
        yield_percentage : list
            The yield percentage for each year.
        color : str
            The color of the plotted line.
        label : str
            The label for the plotted line.
        """

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
