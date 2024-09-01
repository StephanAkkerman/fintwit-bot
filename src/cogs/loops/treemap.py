import datetime
import os

import discord
import pandas as pd
import plotly.express as px
from discord.ext import commands
from discord.ext.tasks import loop

from api.coin360 import get_treemap
from constants.config import config
from constants.sources import data_sources
from util.disc import get_channel, loop_error_catcher


class Treemap(commands.Cog):
    """
    This class contains the cog for posting the S&P 500 heatmap.
    It can be enabled / disabled in the config under ["LOOPS"]["SPY_HEATMAP"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = None
        self.file_name = "treemap.png"
        self.dir = "temp"
        self.post_treemap.start()

    @loop(hours=2)
    @loop_error_catcher
    async def post_treemap(self):
        if self.channel is None:
            self.channel = await get_channel(
                self.bot,
                config["LOOPS"]["TREEMAP"]["CHANNEL"],
                config["CATEGORIES"]["CRYPTO"],
            )

        await self.make_treemap()

        e = discord.Embed(
            title="Cryptocurrency Treemap",
            description="",
            color=data_sources["coin360"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            url="https://coin360.com/",
        )

        file_path = os.path.join(self.dir, self.file_name)
        file = discord.File(file_path, filename=self.file_name)
        e.set_image(url=f"attachment://{self.file_name}")
        e.set_footer(
            text="\u200b",
            icon_url=data_sources["coin360"]["icon"],
        )

        await self.channel.purge(limit=1)
        await self.channel.send(file=file, embed=e)

        # Delete temp file
        os.remove(file_path)

    async def make_treemap(self) -> None:
        response = await get_treemap()

        # Get the categories
        categories: dict = response["categories"]

        # Flatten the data to repeat rows for each category in 'ca'
        expanded_data = []

        for entry in response["data"]:
            # Determine the categories to use
            category_list = entry.get("ca", ["Others"])

            for category in category_list:
                new_entry = entry.copy()
                new_entry["ca"] = categories.get(category, {"title": "Others"})["title"]
                expanded_data.append(new_entry)

        # Create a dataframe from the expanded data
        df = pd.DataFrame(expanded_data)

        # Create custom text that includes the name, percentage change, and price
        df["text"] = (
            '<span style="font-size:20px"><b>'
            + df["s"]
            + "</b></span>"  # Name in larger font and bold
            + "<br>"
            + '<span style="font-size:16px">'
            + "$"
            + df["p"].round(2).astype(str)
            + "</span>"  # Price in smaller font
            + "<br>"
            + '<span style="font-size:16px">'
            + df["ch"].round(2).astype(str)
            + "%</span>"  # Percentage change in smaller font
        )
        # Create the treemap
        fig = px.treemap(
            df,
            path=["ca", "n"],  # Divide by category and then by coin name
            values="mc",  # The size of each block is determined by market cap
            color="ch",  # Color by the percentage change in price
            hover_data=["p", "v", "ts"],  # Information to show on hover
            color_continuous_scale=[
                (0, "#ed7171"),  # Bright red at -5%
                (0.5, "grey"),  # Grey around 0%
                (1, "#80c47c"),  # Bright green at 5%
            ],
            range_color=(-1, 1),
            color_continuous_midpoint=0,
            custom_data=["text"],  # Provide the custom text data for display
        )

        # Removes background colors to improve saved image
        fig.update_layout(
            margin=dict(t=30, l=10, r=10, b=10),
            font_size=20,
            coloraxis_colorbar=None,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

        # Adjust the layout for better visualization of the text
        fig.update_traces(
            texttemplate="%{customdata[0]}",  # Use the custom HTML-styled data for the text template
            textposition="middle center",  # Center the text in the middle of each block
            textfont=dict(color="white"),  # Set all text color to white
            marker=dict(
                line=dict(color="black", width=1)
            ),  # Add a black border around each block for better visibility
        )

        # Disable the color bar
        fig.update(layout_coloraxis_showscale=False)

        # Save the figure as an image
        # Increase the width and height for better quality
        fig.write_image(
            file=os.path.join(self.dir, self.file_name),
            format="png",
            width=1920,
            height=1080,
        )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Treemap(bot))
