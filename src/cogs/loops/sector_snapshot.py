import datetime
import os

import discord
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from discord.ext import commands
from discord.ext.tasks import loop

from api.barchart import get_data
from constants.config import config
from constants.sources import data_sources
from util.disc import get_channel, loop_error_catcher


class Sector_snapshot(commands.Cog):
    """
    This class contains the cog for posting the sector snapshot.
    It can be enabled / disabled in the config under ["LOOPS"]["SECTOR_SNAPSHOT"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = None
        self.post_snapshot.start()

    @loop(hours=12)
    @loop_error_catcher
    async def post_snapshot(self):
        if self.channel is None:
            self.channel = await get_channel(
                self.bot,
                config["LOOPS"]["SECTOR_SNAPSHOT"]["CHANNEL"],
                config["CATEGORIES"]["STOCKS"],
            )

        df = await get_data()
        plot_data(df)

        # Save plot
        file_name = "sector_snap.png"
        file_path = os.path.join("temp", file_name)
        plt.savefig(file_path, bbox_inches="tight", dpi=300)
        plt.cla()
        plt.close()

        e = discord.Embed(
            title="Percentage Of Large Cap Stocks Above Their Moving Averages",
            description="",
            color=data_sources["barchart"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            url="https://www.barchart.com/stocks/market-performance",
        )
        file = discord.File(file_path, filename=file_name)
        e.set_image(url=f"attachment://{file_name}")
        e.set_footer(
            text="\u200b",
            icon_url=data_sources["barchart"]["icon"],
        )

        await self.channel.purge(limit=1)
        await self.channel.send(file=file, embed=e)

        # Delete temp file
        os.remove(file_path)


def plot_data(df):
    # Define custom colormap for each 10% increment
    colors = [
        (0, "#620101"),  # 0%
        (0.1, "#76030f"),  # 10%
        (0.2, "#801533"),  # 20%
        (0.3, "#620000"),  # 30%
        (0.4, "#74274b"),  # 40%
        (0.5, "#062f5b"),  # 50%
        (0.6, "#174f52"),  # 60%
        (0.7, "#113b35"),  # 70%
        (0.8, "#074510"),  # 80%
        (0.9, "#03360c"),  # 90%
        (1.0, "#012909"),  # 100%
    ]

    # Create the custom colormap
    cmap = mcolors.LinearSegmentedColormap.from_list("custom_cmap", colors)

    # Normalize data to [0, 1] for color mapping
    norm = plt.Normalize(0, 100)

    # Apply custom colormap
    values = df.drop(columns="Name").values
    colors = cmap(norm(values))

    # Create a white color array for the 'Name' column
    name_colors = np.ones((df.shape[0], 1, 4))

    # Concatenate the name colors with the data colors
    colors = np.concatenate((name_colors, colors), axis=1)

    # Create the table
    fig, ax = plt.subplots(figsize=(14, 6))

    # Set the background color of the figure
    fig.patch.set_facecolor("#2e2e2e")

    ax.axis("off")

    # Add % to all values in the DF except Name column
    df = df.map(lambda x: f"{x}%" if isinstance(x, (int, float)) else x)

    # Create the table
    table = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        cellColours=colors,
        cellLoc="center",
        loc="center",
    )

    # Adjust column widths
    table.auto_set_column_width(list(range(df.shape[1])))
    table.scale(1, 2)  # Make the first column wider

    # Style the header
    for key, cell in table.get_celld().items():
        cell.set_text_props(color="w")
        cell.set_edgecolor("#2b2f30")  # Set the grid color to white
        # First row
        if key[0] == 0:
            cell.set_fontsize(10)
            cell.set_text_props(weight="bold")
            cell.set_facecolor("#181a1b")
        elif key[1] == 0:
            cell.set_fontsize(10)
            cell.set_facecolor("#181a1b")
            cell.set_text_props(ha="left")
        else:
            cell.set_fontsize(12)

    table.auto_set_font_size(False)

    # Add the title in the top left corner
    plt.text(
        0.04,
        1.05,
        "Percentage Of Large Cap Stocks Above Their Moving Averages",
        transform=ax.transAxes,
        fontsize=12,
        verticalalignment="top",
        horizontalalignment="left",
        color="white",
        weight="bold",
    )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Sector_snapshot(bot))
