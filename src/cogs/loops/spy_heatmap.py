import datetime
import os

import discord
import pandas as pd
import plotly.express as px
from discord.ext import commands
from discord.ext.tasks import loop

from api.unusualwhales import get_spy_heatmap
from constants.config import config
from constants.sources import data_sources
from util.afterhours import afterHours
from util.disc import get_channel, loop_error_catcher


class SPY_heatmap(commands.Cog):
    """
    This class contains the cog for posting the S&P 500 heatmap.
    It can be enabled / disabled in the config under ["LOOPS"]["SPY_HEATMAP"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = None
        self.post_heatmap.start()

    @loop(hours=2)
    @loop_error_catcher
    async def post_heatmap(self):
        if afterHours():
            return

        if self.channel is None:
            self.channel = await get_channel(
                self.bot,
                config["LOOPS"]["SPY_HEATMAP"]["CHANNEL"],
                config["CATEGORIES"]["STOCKS"],
            )

        df = await get_spy_heatmap()
        create_treemap(df)

        e = discord.Embed(
            title="The S&P 500 Heatmap",
            description="",
            color=data_sources["unusualwhales"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            url="https://unusualwhales.com/heatmaps",
        )

        file_name = "spy_heatmap.png"
        file_path = os.path.join("temp", file_name)
        file = discord.File(file_path, filename=file_name)
        e.set_image(url=f"attachment://{file_name}")
        e.set_footer(
            text="\u200b",
            icon_url=data_sources["unusualwhales"]["icon"],
        )

        await self.channel.purge(limit=1)
        await self.channel.send(file=file, embed=e)

        # Delete temp file
        os.remove(file_path)


def create_treemap(df: pd.DataFrame, save_img: bool = True) -> None:
    """
    Creates a treemap of the S&P 500 heatmap data.

    Parameters
    ----------
    df : pd.DataFrame
        The input DataFrame containing the S&P 500 heatmap data.
    save_img : bool, optional
        Saves the heatmap as a image, by default False
    """

    # Custom color scale
    color_scale = [
        (0, "#ff2c1c"),  # Bright red at -5%
        (0.5, "#484454"),  # Grey around 0%
        (1, "#30dc5c"),  # Bright green at 5%
    ]

    # Generate the treemap
    fig = px.treemap(
        df,
        path=[px.Constant("Sectors"), "sector", "industry", "ticker"],
        values="marketcap",
        color="percentage_change",
        hover_data=["percentage_change", "ticker", "marketcap"],
        color_continuous_scale=color_scale,
        range_color=(-5, 5),
        color_continuous_midpoint=0,
    )

    # Removes background colors to improve saved image
    fig.update_layout(
        margin=dict(t=30, l=10, r=10, b=10),
        font_size=20,
        coloraxis_colorbar=None,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    fig.data[0].texttemplate = "%{customdata[1]}<br>%{customdata[0]:.2f}%"

    # Set the text position to the middle of the treemap
    # and add a black border around each box
    fig.update_traces(
        textposition="middle center",
        marker=dict(line=dict(color="black", width=1)),
    )

    # Disable the color bar
    fig.update(layout_coloraxis_showscale=False)

    # Save the figure as an image
    # Increase the width and height for better quality
    if save_img:
        fig.write_image(
            file="temp/spy_heatmap.png", format="png", width=1920, height=1080
        )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(SPY_heatmap(bot))
