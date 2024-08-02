import datetime
import os

import discord
import pandas as pd
import plotly.express as px
from discord.ext import commands
from discord.ext.tasks import loop

from util.afterhours import afterHours
from util.disc_util import get_channel
from util.vars import config, data_sources, get_json_data


class SPY_heatmap(commands.Cog):
    """
    This class contains the cog for posting the S&P 500 heatmap.
    It can be enabled / disabled in the config under ["LOOPS"]["SPY_HEATMAP"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = None

        if config["LOOPS"]["SPY_HEATMAP"]["ENABLED"]:
            self.post_heatmap.start()

    @loop(hours=2)
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


async def get_spy_heatmap(date: str = "one_day") -> pd.DataFrame:
    """
    Fetches the S&P 500 heatmap data from Unusual Whales API.

    Parameters
    ----------
    date : str, optional
        Options are: one_day, after_hours, yesterday, one_week, one_month, ytd, one_year, by default "one_day"

    Returns
    -------
    pd.DataFrame
        The S&P 500 heatmap data as a DataFrame.
    """
    data = await get_json_data(
        f"https://phx.unusualwhales.com/api/etf/SPY/heatmap?date_range={date}",
        headers={
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36"
        },
    )

    # Create DataFrame
    df = pd.DataFrame(data["data"])

    # Convert relevant columns to numeric types
    df["call_premium"] = pd.to_numeric(df["call_premium"])
    df["close"] = pd.to_numeric(df["close"])
    df["high"] = pd.to_numeric(df["high"])
    df["low"] = pd.to_numeric(df["low"])
    df["marketcap"] = pd.to_numeric(df["marketcap"])
    df["open"] = pd.to_numeric(df["open"])
    df["prev_close"] = pd.to_numeric(df["prev_close"])
    df["put_premium"] = pd.to_numeric(df["put_premium"])

    # Add change column
    df["percentage_change"] = (df["close"] - df["prev_close"]) / df["prev_close"] * 100

    # Drop rows where the marketcap == 0
    df = df[df["marketcap"] > 0]

    return df


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
