import datetime
import os
from datetime import timedelta

import discord
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from discord.ext import commands
from discord.ext.tasks import loop
from matplotlib.ticker import FuncFormatter
from scipy.optimize import curve_fit

from api.ccxt import fetch_data
from util.disc_util import get_channel, loop_error_catcher
from util.vars import config, data_sources, logger

# Define constants
COLORS_LABELS = {
    "#c00200": "Maximum bubble territory",
    "#d64018": "Sell. Seriously, SELL!",
    "#ed7d31": "FOMO Intensifies",
    "#f6b45a": "Is this a bubble?",
    "#feeb84": "HODL!",
    "#b1d580": "Still cheap",
    "#63be7b": "Accumulate",
    "#54989f": "BUY!",
    "#4472c4": "Fire sale!",
}
BAND_WIDTH = 0.3
NUM_BANDS = 9
FIGURE_SIZE = (15, 7)
BACKGROUND_COLOR = "#0d1117"
EXTEND_MONTHS = 9


class Rainbow_chart(commands.Cog):
    """
    This class contains the cog for posting the Liquidations chart.
    It can be enabled / disabled in the config under ["LOOPS"]["LIQUIDATIONS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel = None
        self.post_rainbow_chart.start()

    @loop(hours=24)
    @loop_error_catcher
    async def post_rainbow_chart(self):
        if self.channel is None:
            self.channel = await get_channel(
                self.bot, config["LOOPS"]["RAINBOW_CHART"]["CHANNEL"]
            )
        # Load data
        raw_data, popt = get_data("data/bitcoin_data.csv")

        # Create plot
        create_plot(raw_data, popt)

        # Save plot
        file_name = "rainbow_chart.png"
        file_path = os.path.join("temp", file_name)
        plt.savefig(file_path, bbox_inches="tight", dpi=300)
        plt.cla()
        plt.close()

        e = discord.Embed(
            title="Bitcoin Rainbow Price Chart",
            description="",
            color=data_sources["coinglass"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            url="https://www.coinglass.com/pro/i/bitcoin-rainbow-chart",
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


def log_func(x, a, b, c):
    """Logarithmic function for curve fitting."""
    return a * np.log(b + x) + c


def get_data(file_path):
    """
    Load and preprocess data from a CSV file.

    Args:
        file_path (str): Path to the CSV file.

    Returns:
        pd.DataFrame: Processed data.
        np.ndarray: Fitted Y data.
    """
    raw_data = pd.read_csv(file_path)
    raw_data["Date"] = pd.to_datetime(raw_data["Date"])

    # Calculate the difference in days between the last date and today
    diff_days = (pd.Timestamp.today() - raw_data["Date"].max()).days

    if diff_days > 1:
        logger.info(f"Data is {diff_days} days old. Updating...")

        # Get new data
        # raw_data = pd.DataFrame(nasdaqdatalink.get("BCHAIN/MKPRU")).reset_index()
        new_data = fetch_data(
            since=raw_data["Date"].max(), limit=diff_days, exchange="binance"
        )

        # Append new data to the existing data
        raw_data = pd.concat([raw_data, new_data])

        # Save new data
        raw_data.to_csv(file_path, index=False)

    raw_data = raw_data[raw_data["Value"] > 0]

    # Prepare data for curve fitting
    xdata = np.array([x + 1 for x in range(len(raw_data))])
    ydata = np.log(raw_data["Value"])

    # Fit the logarithmic curve
    popt, _ = curve_fit(log_func, xdata, ydata)

    return raw_data, popt


def create_plot(raw_data, popt):

    # Create plot
    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    fig.patch.set_facecolor(BACKGROUND_COLOR)
    ax.set_facecolor(BACKGROUND_COLOR)

    # Plot rainbow bands and price data
    plot_rainbow(ax, raw_data, popt)
    plot_price(ax, raw_data)

    # Add halving lines
    add_halving_lines(ax)

    # Configure plot appearance
    configure_plot(ax, raw_data)

    add_legend(ax)


def add_halving_lines(ax):
    """Add vertical lines for Bitcoin halving events."""
    halving_dates = [
        pd.Timestamp("2012-11-28"),  # First halving
        pd.Timestamp("2016-07-09"),  # Second halving
        pd.Timestamp("2020-05-11"),  # Third halving
        pd.Timestamp("2024-04-20"),  # Fourth halving
    ]

    for halving_date in halving_dates:
        ax.axvline(halving_date, color="white", linestyle="-", linewidth=1, alpha=0.5)


def extend_dates(raw_data, months=EXTEND_MONTHS):
    """
    Extend the date range of the data by a specified number of months.

    Args:
        raw_data (pd.DataFrame): Original data.
        months (int): Number of months to extend.

    Returns:
        pd.Series: Extended date range.
    """
    last_date = raw_data["Date"].max()
    extended_dates = pd.date_range(
        start=last_date + timedelta(days=1), periods=months * 30
    )
    return pd.concat([raw_data["Date"], pd.Series(extended_dates)])


def plot_rainbow(ax, raw_data, popt, num_bands=NUM_BANDS, band_width=BAND_WIDTH):
    """
    Plot rainbow bands on the given axis.

    Args:
        ax (matplotlib.axes._subplots.AxesSubplot): Axis to plot on.
        raw_data (pd.DataFrame): Raw data.
        num_bands (int): Number of bands.
        band_width (float): Width of each band.
    """
    extended_dates = extend_dates(raw_data)
    extended_xdata = np.arange(1, len(extended_dates) + 1)
    extended_fitted_ydata = log_func(extended_xdata, *popt)

    legend_handles = []
    for i in range(num_bands):
        i_decrease = 1.5
        lower_bound = np.exp(
            extended_fitted_ydata + (i - i_decrease) * band_width - band_width
        )
        upper_bound = np.exp(extended_fitted_ydata + (i - i_decrease) * band_width)
        color = list(COLORS_LABELS.keys())[::-1][i]
        label = list(COLORS_LABELS.values())[::-1][i]
        ax.fill_between(
            extended_dates, lower_bound, upper_bound, alpha=1, color=color, label=label
        )
        legend_handles.append(
            plt.Line2D([0], [0], color=color, lw=4, label=label)
        )  # Changed to Line2D
    return legend_handles


def plot_price(ax, raw_data):
    """
    Plot Bitcoin price data on the given axis.

    Args:
        ax (matplotlib.axes._subplots.AxesSubplot): Axis to plot on.
        raw_data (pd.DataFrame): Raw data.

    Returns:
        matplotlib.lines.Line2D: The line representing the BTC price.
    """
    return ax.semilogy(
        raw_data["Date"].values,
        raw_data["Value"].values,
        color="white",
        label="BTC Price",
    )[0]


def y_format(y, _):
    """Custom formatter for Y-axis labels."""
    if y < 1:
        return f"${y:.2f}"
    elif y < 10:
        return f"${y:.1f}"
    elif y < 1_000:
        return f"${int(y):,}".replace(",", ".")
    elif y < 1_000_000:
        return f"${y/1_000:.1f}K".replace(".0K", "K").replace(".", ",")
    else:
        return f"${y/1_000_000:.1f}M".replace(".0M", "M").replace(".", ",")


def configure_plot(ax, raw_data):
    """
    Configure the appearance of the plot.

    Args:
        ax (matplotlib.axes._subplots.AxesSubplot): Axis to configure.
        raw_data (pd.DataFrame): Raw data.
    """
    formatter = FuncFormatter(y_format)
    ax.yaxis.set_major_formatter(formatter)
    ax.set_ylim(bottom=0.01)
    ax.set_xlim(
        [
            raw_data["Date"].min(),
            raw_data["Date"].max() + pd.DateOffset(months=EXTEND_MONTHS),
        ]
    )
    ax.tick_params(axis="x", colors="white")
    ax.tick_params(axis="y", colors="white")

    # Set x-axis major ticks to every year
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # Rotate and align the tick labels for better readability
    plt.setp(ax.get_xticklabels(), rotation=0)


def add_legend(ax):
    # Create custom legend handles with square markers, including BTC price
    legend_handles = [
        plt.Line2D(
            [0],
            [0],
            marker="s",
            color=BACKGROUND_COLOR,
            markerfacecolor="white",
            markersize=10,
            label="BTC price",
        )
    ] + [
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
        bbox_to_anchor=(0.5, 1.15),
        ncol=len(legend_handles),
        frameon=False,
        fontsize="small",
        labelcolor="white",
    )

    # Make legend text bold
    for text in legend.get_texts():
        text.set_fontweight("bold")

    # Adjust layout to reduce empty space around the plot
    plt.subplots_adjust(left=0.05, right=0.975, top=0.875, bottom=0.1)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Rainbow_chart(bot))
