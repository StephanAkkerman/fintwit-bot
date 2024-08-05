import os
from datetime import datetime, timedelta, timezone

import discord
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from discord.ext import commands
from discord.ext.tasks import loop
from matplotlib import ticker

from api.binance import get_new_data, summarize_liquidations
from constants.config import config
from constants.logger import logger
from constants.sources import data_sources
from util.disc import get_channel, loop_error_catcher
from util.formatting import human_format

BACKGROUND_COLOR = "#0d1117"
FIGURE_SIZE = (15, 7)
COLORS_LABELS = {"#d9024b": "Shorts", "#45bf87": "Longs", "#f0b90b": "Price"}


class Liquidations(commands.Cog):
    """
    This class contains the cog for posting the Liquidations chart.
    It can be enabled / disabled in the config under ["LOOPS"]["LIQUIDATIONS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = None
        self.post_liquidations.start()

    @loop(hours=24)
    @loop_error_catcher
    async def post_liquidations(self):
        """
        Copy chart like https://www.coinglass.com/LiquidationData
        """
        if self.channel is None:
            self.channel = await get_channel(
                self.bot, config["LOOPS"]["LIQUIDATIONS"]["CHANNEL"]
            )
        file_name: str = "liquidations.png"
        file_path = os.path.join("temp", file_name)
        await liquidations_chart(file_name)

        e = discord.Embed(
            title="Total Liquidations",
            description="",
            color=data_sources["coinglass"]["color"],
            timestamp=datetime.now(timezone.utc),
            url="https://www.coinglass.com/LiquidationData",
        )
        file = discord.File(file_path, filename=file_name)
        e.set_image(url=f"attachment://{file_name}")
        e.set_footer(
            text="\u200b",
            icon_url=data_sources["coinglass"]["icon"],
        )

        await self.channel.purge(limit=1)
        await self.channel.send(file=file, embed=e)

        # Delete yield.png
        os.remove(file_path)


async def liquidations_chart(file_name: str = "liquidations.png"):
    coin = "BTCUSDT"
    market = "um"
    new_data = get_new_data(coin, market=market)
    if new_data:
        logger.info(f"Downloaded {len(new_data)} new files.")
        # Recreate the summaryf
        summarize_liquidations(coin=coin, market=market)
    # Load the summary
    df = pd.read_csv(
        f"data/summary/{coin}/{market}/liquidation_summary.csv",
        index_col=0,
        parse_dates=True,
    )

    if df is None or df.empty:
        return

    df_price = df[["price"]].copy()
    df_without_price = df.drop("price", axis=1)
    df_without_price["Shorts"] = df_without_price["Shorts"] * -1

    # This plot has 2 axes
    fig, ax1 = plt.subplots()
    fig.patch.set_facecolor(BACKGROUND_COLOR)
    ax1.set_facecolor(BACKGROUND_COLOR)

    ax2 = ax1.twinx()

    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=14))

    ax1.bar(
        df_without_price.index,
        df_without_price["Shorts"],
        label="Shorts",
        color="#d9024b",
    )

    ax1.bar(
        df_without_price.index,
        df_without_price["Longs"],
        label="Longs",
        color="#45bf87",
    )

    ax1.get_yaxis().set_major_formatter(
        ticker.FuncFormatter(lambda x, _: f"${human_format(x, absolute=True)}")
    )

    # Set price axis
    ax2.plot(df_price.index, df_price, color="#edba35", label="BTC Price")
    ax2.set_xlim([df_price.index[0], df_price.index[-1]])
    ax2.set_ylim(bottom=df_price.min().values * 0.95, top=df_price.max().values * 1.05)
    ax2.get_yaxis().set_major_formatter(lambda x, _: f"${human_format(x)}")

    # Add combined legend using the custom add_legend function
    add_legend(ax2)

    # Add gridlines
    plt.grid(axis="y", color="grey", linestyle="-.", linewidth=0.5, alpha=0.5)

    # Remove spines
    ax1.spines["top"].set_visible(False)
    ax1.spines["bottom"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.spines["left"].set_visible(False)
    ax1.tick_params(left=False, bottom=False, right=False, colors="white")

    ax2.spines["top"].set_visible(False)
    ax2.spines["bottom"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.spines["left"].set_visible(False)
    ax2.tick_params(left=False, bottom=False, right=False, colors="white")

    # Fixes first and last bar not showing
    ax1.set_xlim(
        left=df_without_price.index[0] - timedelta(days=1),
        right=df_without_price.index[-1] + timedelta(days=1),
    )
    ax2.set_xlim(
        left=df_without_price.index[0] - timedelta(days=1),
        right=df_without_price.index[-1] + timedelta(days=1),
    )

    # Set correct size
    fig.set_size_inches(FIGURE_SIZE)

    # Add the title in the top left corner
    plt.text(
        -0.025,
        1.125,
        "Total Liquidations Chart",
        transform=ax1.transAxes,
        fontsize=14,
        verticalalignment="top",
        horizontalalignment="left",
        color="white",
        weight="bold",
    )

    # Convert to plot to a temporary image
    file_path = os.path.join("temp", file_name)
    plt.savefig(file_path, bbox_inches="tight", dpi=300)
    plt.cla()
    plt.close()


def add_legend(ax):
    # Create custom legend handles with square markers, including BTC price
    legend_handles = [
        plt.Line2D(
            [0],
            [0],
            marker="s",
            color=BACKGROUND_COLOR,
            markerfacecolor=color,
            markersize=10,
            label=label,
        )
        for color, label in zip(
            list(COLORS_LABELS.keys()), list(COLORS_LABELS.values())
        )
    ]

    # Add legend
    legend = ax.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.0),
        ncol=len(legend_handles),
        frameon=False,
        fontsize="small",
        labelcolor="white",
    )

    # Make legend text bold
    for text in legend.get_texts():
        text.set_fontweight("bold")

    # Adjust layout to reduce empty space around the plot
    plt.subplots_adjust(left=0.05, right=0.95, top=0.875, bottom=0.1)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Liquidations(bot))
