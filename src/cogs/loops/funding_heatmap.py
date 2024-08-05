import datetime
import glob
import os

import discord
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from discord.ext import commands
from discord.ext.tasks import loop
from matplotlib.ticker import FuncFormatter
from tqdm import tqdm

from api.binance import BinanceClient
from api.coingecko import get_top_vol_coins
from constants.config import config
from constants.sources import data_sources
from util.disc import get_channel, loop_error_catcher

FIGURE_SIZE = (20, 10)
NUM_COINS = 30
NUM_DAYS = 90
FUNDING_DIR = "data/funding_rate"
BACKGROUND_COLOR = "#0d1117"
TEXT_COLOR = "#b9babc"


class Funding_heatmap(commands.Cog):
    """
    This class contains the cog for posting the Liquidations chart.
    It can be enabled / disabled in the config under ["LOOPS"]["LIQUIDATIONS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = None
        self.post_heatmap.start()

    @loop(hours=24)
    @loop_error_catcher
    async def post_heatmap(self):
        if self.channel is None:
            self.channel = await get_channel(
                self.bot,
                config["LOOPS"]["FUNDING_HEATMAP"]["CHANNEL"],
                config["CATEGORIES"]["CRYPTO"],
            )

        # Load data
        df = await load_funding_rate_data(
            FUNDING_DIR,
        )

        # Prepare heatmap data
        heatmap_data = prepare_heatmap_data(df, NUM_DAYS)

        # Plot heatmap
        plot_heatmap(heatmap_data)

        # Save plot
        file_name = "funding_rate.png"
        file_path = os.path.join("temp", file_name)
        plt.savefig(file_path, bbox_inches="tight", dpi=300)
        plt.cla()
        plt.close()

        e = discord.Embed(
            title="Funding Rate Heatmap",
            description="",
            color=data_sources["coinglass"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            url="https://www.coinglass.com/FundingRateHeatMap",
        )
        file = discord.File(file_path, filename=file_name)
        e.set_image(url=f"attachment://{file_name}")
        e.set_footer(
            text="\u200b",
            icon_url=data_sources["coinglass"]["icon"],
        )

        await self.channel.purge(limit=1)
        await self.channel.send(file=file, embed=e)

        # Delete temp file
        os.remove(file_path)


async def get_all_funding_rates(NUM_COINS: int = 30):
    # TODO: Check if there is new data and save it
    b = BinanceClient()
    symbols = await get_top_vol_coins(NUM_COINS)

    os.makedirs("data/funding_rate", exist_ok=True)

    for symbol in tqdm(symbols, desc="Processing symbols"):
        # tqdm.write(f"Processing symbol: {symbol}")
        df = await b.fund_rating(symbol, rows=10_000)
        # Save the df in data/funding_rate/symbol.csv
        if not df.empty:
            df.to_csv(f"data/funding_rate/{symbol}.csv", index=False)


async def load_funding_rate_data(directory):
    all_files = glob.glob(os.path.join(directory, "*.csv"))

    if all_files == []:
        await get_all_funding_rates()
        all_files = glob.glob(os.path.join(directory, "*.csv"))

    df_list = []

    for file in all_files:
        df = pd.read_csv(file, parse_dates=["calcTime"])

        # Get the latest date of the data
        latest_date = df["calcTime"].max()

        # If the data is older than 8 hours, fetch new data
        if pd.Timestamp.now() - latest_date > pd.Timedelta(hours=12):
            symbol = file.split("/")[-1].split(".")[0]
            # Also remove any backslashes from the symbol
            symbol = symbol.split("\\")[-1]
            b = BinanceClient()
            new_df = await b.fund_rating(symbol, rows=10_000)
            if not new_df.empty:
                new_df.to_csv(file, index=False)
                df = pd.read_csv(file, parse_dates=["calcTime"])

        df_list.append(df)

    all_data = pd.concat(df_list, ignore_index=True)
    return all_data


def prepare_heatmap_data(df, NUM_DAYS: int) -> pd.DataFrame:
    # Filter data for the last NUM_DAYS days
    last_n_days = df["calcTime"].max() - pd.Timedelta(days=NUM_DAYS)
    df = df[df["calcTime"] >= last_n_days]

    # Multiply funding rate with 100 to get percentage
    df.loc[:, "lastFundingRate"] = df["lastFundingRate"].multiply(100)

    # Pivot the data to create a matrix for the heatmap
    heatmap_data = df.pivot(
        index="symbol", columns="calcTime", values="lastFundingRate"
    )

    # Forward fill to handle NaN values
    heatmap_data = heatmap_data.ffill(axis=1)
    # Also do a backward fill to handle NaN values at the start
    heatmap_data = heatmap_data.bfill(axis=1)

    return heatmap_data


def plot_heatmap(data: pd.DataFrame):
    # Set the style for a dark background
    plt.style.use("dark_background")
    sns.set_theme(style="darkgrid")

    # Create a figure and axis with a dark background
    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    fig.patch.set_facecolor(BACKGROUND_COLOR)  # Dark background color for the figure
    ax.set_facecolor(BACKGROUND_COLOR)  # Dark background color for the axes

    # Plot the heatmap
    heatmap = sns.heatmap(
        data,
        cmap="viridis",
        cbar=True,  # Enable the color bar
        ax=ax,
        cbar_kws={
            "orientation": "horizontal"
        },  # Set the color bar orientation to horizontal
        linewidths=0,
    )

    # Customize the text colors
    ax.title.set_color("white")
    ax.xaxis.label.set_color(TEXT_COLOR)
    ax.yaxis.label.set_color(TEXT_COLOR)
    ax.tick_params(colors=TEXT_COLOR, which="both")

    # Setting x-axis labels at 4-day intervals
    datetime_index = data.iloc[0].index
    interval = 24  # each date has 3 values
    xticks = datetime_index[::interval]
    xtick_labels = [date.strftime("%d %b") for date in xticks]

    ax.set_xticks(np.arange(0, len(datetime_index), interval))
    ax.set_xticklabels(xtick_labels, rotation=0, ha="right")

    # Remove x-axis label
    ax.set_xlabel("")
    ax.set_ylabel("")

    # Adjust layout to reduce empty space around the plot
    plt.subplots_adjust(left=0.075, right=0.975, top=0.875, bottom=-0.15)

    # Get the color bar and reposition it below the heatmap
    cbar = heatmap.collections[0].colorbar
    cbar.ax.set_position([0.25, 0.075, 0.5, 0.02])  # [left, bottom, width, height]

    # Customize color bar labels and ticks
    cbar.ax.xaxis.set_ticks_position("bottom")
    cbar.ax.set_xlabel("")
    cbar.ax.tick_params(colors=TEXT_COLOR)

    # Add min and max text annotations
    min_val = data.values.min()
    max_val = data.values.max()
    cbar.ax.text(
        -0.1,
        0.5,
        f"{min_val:.2f}%",
        ha="center",
        va="center",
        color=TEXT_COLOR,
        transform=cbar.ax.transAxes,
    )
    cbar.ax.text(
        1.1,
        0.5,
        f"{max_val:.2f}%",
        ha="center",
        va="center",
        color=TEXT_COLOR,
        transform=cbar.ax.transAxes,
    )

    # Format ticks to show percentage
    def percent_formatter(x, pos) -> str:
        return f"{x:.2f}%"

    cbar.ax.xaxis.set_major_formatter(FuncFormatter(percent_formatter))

    plt.xticks(rotation=0)
    plt.yticks(rotation=0)

    # Add the title in the top left corner
    plt.text(
        -0.06,
        1.125,
        "Funding Rate Heatmap",
        transform=ax.transAxes,
        fontsize=14,
        verticalalignment="top",
        horizontalalignment="left",
        color="white",
        weight="bold",
    )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Funding_heatmap(bot))
