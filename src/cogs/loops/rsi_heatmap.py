import datetime
import os

import discord
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from discord.ext import commands
from discord.ext.tasks import loop
from tradingview_ta import get_multiple_analysis

from util.cg_data import get_top_vol_coins
from util.disc_util import get_channel
from util.vars import config, data_sources, logger

FIGURE_SIZE = (12, 10)
BACKGROUND_COLOR = "#0d1117"
RANGES = {
    "Overbought": (70, 100),
    "Strong": (60, 70),
    "Neutral": (40, 60),
    "Weak": (30, 40),
    "Oversold": (0, 30),
}
COLORS_LABELS = {
    "Oversold": "#1d8b7a",
    "Weak": "#144e48",
    "Neutral": "#0d1117",
    "Strong": "#681f28",
    "Overbought": "#c32e3b",
}
SCATTER_COLORS = {
    "Oversold": "#1e9884",
    "Weak": "#165952",
    "Neutral": "#78797a",
    "Strong": "#79212c",
    "Overbought": "#cf2f3d",
}


class RSI_heatmap(commands.Cog):
    """
    This class contains the cog for posting the Liquidations chart.
    It can be enabled / disabled in the config under ["LOOPS"]["LIQUIDATIONS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["RSI_HEATMAP"]["ENABLED"]:
            self.channel = None
            self.post_rsi_heatmap.start()

    @loop(hours=24)
    async def post_rsi_heatmap(
        self, num_coins: int = 100, time_frame: str = "1d"
    ) -> None:
        if self.channel is None:
            self.channel = await get_channel(
                self.bot, config["LOOPS"]["RSI_HEATMAP"]["CHANNEL"]
            )
        top_vol = get_top_vol_coins(num_coins)
        rsi_data = get_RSI(top_vol, time_frame=time_frame)
        old_rsi_data = get_closest_to_24h(time_frame=time_frame)

        # Create lists of labels and RSI values
        rsi_symbols = list(rsi_data.keys())
        rsi_values = list(rsi_data.values())

        # Calculate the average RSI value
        average_rsi = np.mean(rsi_values)

        # Create the scatter plot
        fig, ax = plt.subplots(figsize=FIGURE_SIZE)

        # Set the background color
        fig.patch.set_facecolor(BACKGROUND_COLOR)
        ax.set_facecolor(BACKGROUND_COLOR)

        # Define the color for each RSI range
        color_map = []
        for k in RANGES:
            color_map.append((*RANGES[k], COLORS_LABELS[k], k))

        # Fill the areas with the specified colors and create custom legend
        for i, (start, end, color, symbol) in enumerate(color_map):
            ax.fill_between(
                [0, len(rsi_symbols) + 2], start, end, color=color, alpha=0.35
            )

            # Adjust the Y position for the first and last labels
            if i == 0:
                y_pos = start + 5  # Move down a bit from the top
            elif i == len(color_map) - 1:
                y_pos = end - 5  # Move up a bit from the bottom
            else:
                y_pos = (start + end) / 2  # Center for other labels

            # Add text to the right of the plot with the label (overbought, etc.)
            ax.text(
                len(rsi_symbols) + 1.5,  # X position (to the right of the plot)
                y_pos,  # Y position
                symbol.upper(),  # Text to display
                va="center",  # Vertical alignment
                ha="right",  # Horizontal alignment
                fontsize=15,  # Font size
                color="grey",  # Text color
            )

        # Plot each point with a white border for visibility
        for i, symbol in enumerate(rsi_symbols):
            # These are the dots on the plot
            ax.scatter(
                i + 1,
                rsi_values[i],
                color=get_color_for_rsi(rsi_values[i]),
                s=100,
            )
            # Add the symbol text
            ax.annotate(
                symbol,
                (i + 1, rsi_values[i]),
                color="#b9babc",
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
            )
            # Add line connecting the old and new RSI values
            if symbol in old_rsi_data:
                # Compare the previous RSI value with the current one
                rsi_diff = rsi_values[i] - old_rsi_data[symbol]

                # Set the color based on the difference
                line_color = "#1f9986" if rsi_diff > 0 else "#e23343"

                # Draw the line connecting the old and new RSI values
                ax.plot(
                    [i + 1, i + 1],
                    [old_rsi_data[symbol], rsi_values[i]],
                    color=line_color,
                    linestyle="--",
                    linewidth=0.75,  # Adjust the value to make the lines thinner
                )

        # Draw the average RSI line and add the annotation
        ax.axhline(
            xmin=0,
            xmax=1,
            y=average_rsi,
            color="#d58c3c",
            linestyle="--",
            linewidth=0.75,
        )
        ax.text(
            len(rsi_symbols) + 1.5,  # Increase to move the text to the right
            average_rsi,
            f"AVG RSI: {average_rsi:.2f}",
            color="#d58c3c",
            va="bottom",
            ha="right",
            fontsize=15,
        )

        # Set the color of the tick labels to white
        ax.tick_params(colors="#a9aaab", which="both", length=0)

        # Set the y-axis limits based on RSI values
        ax.set_ylim(20, 80)

        # Extend the xlim to make room for the annotations
        ax.set_xlim(0, len(rsi_symbols) + 2)

        # Remove the x-axis ticks since we're annotating each point
        ax.set_xticks([])

        add_legend(ax)

        # Set the color of the spines to match the background color or make them invisible
        for spine in ax.spines.values():
            spine.set_edgecolor(BACKGROUND_COLOR)

        # Add the title in the top left corner
        plt.text(
            -0.025,
            1.125,
            "Crypto Market RSI Heatmap",
            transform=ax.transAxes,
            fontsize=14,
            verticalalignment="top",
            horizontalalignment="left",
            color="white",
            weight="bold",
        )

        file_name = "rsi_heatmap.png"
        file_path = os.path.join("temp", file_name)
        plt.savefig(file_path, bbox_inches="tight", dpi=300)
        plt.cla()
        plt.close()

        e = discord.Embed(
            title="Crypto Market RSI Heatmap",
            description="",
            color=data_sources["coinglass"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            url="https://www.coinglass.com/pro/i/RsiHeatMap",
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


def get_color_for_rsi(rsi_value: float) -> dict:
    for label, (low, high) in RANGES.items():
        if low <= rsi_value < high:
            return SCATTER_COLORS[label]
    return None


def plot_rsi_heatmap(num_coins: int = 100, time_frame: str = "1d") -> None:
    top_vol = get_top_vol_coins(num_coins)
    rsi_data = get_RSI(top_vol, time_frame=time_frame)
    old_rsi_data = get_closest_to_24h(time_frame=time_frame)

    # Create lists of labels and RSI values
    rsi_symbols = list(rsi_data.keys())
    rsi_values = list(rsi_data.values())

    # Calculate the average RSI value
    average_rsi = np.mean(rsi_values)

    # Create the scatter plot
    fig, ax = plt.subplots(figsize=FIGURE_SIZE)

    # Set the background color
    fig.patch.set_facecolor(BACKGROUND_COLOR)
    ax.set_facecolor(BACKGROUND_COLOR)

    # Define the color for each RSI range
    color_map = []
    for k in RANGES:
        color_map.append((*RANGES[k], COLORS_LABELS[k], k))

    # Fill the areas with the specified colors and create custom legend
    for i, (start, end, color, symbol) in enumerate(color_map):
        ax.fill_between([0, len(rsi_symbols) + 2], start, end, color=color, alpha=0.35)

        # Adjust the Y position for the first and last labels
        if i == 0:
            y_pos = start + 5  # Move down a bit from the top
        elif i == len(color_map) - 1:
            y_pos = end - 5  # Move up a bit from the bottom
        else:
            y_pos = (start + end) / 2  # Center for other labels

        # Add text to the right of the plot with the label (overbought, etc.)
        ax.text(
            len(rsi_symbols) + 1.5,  # X position (to the right of the plot)
            y_pos,  # Y position
            symbol.upper(),  # Text to display
            va="center",  # Vertical alignment
            ha="right",  # Horizontal alignment
            fontsize=15,  # Font size
            color="grey",  # Text color
        )

    # Plot each point with a white border for visibility
    for i, symbol in enumerate(rsi_symbols):
        # These are the dots on the plot
        ax.scatter(
            i + 1,
            rsi_values[i],
            color=get_color_for_rsi(rsi_values[i]),
            s=100,
        )
        # Add the symbol text
        ax.annotate(
            symbol,
            (i + 1, rsi_values[i]),
            color="#b9babc",
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
        )
        # Add line connecting the old and new RSI values
        if symbol in old_rsi_data:
            # Compare the previous RSI value with the current one
            rsi_diff = rsi_values[i] - old_rsi_data[symbol]

            # Set the color based on the difference
            line_color = "#1f9986" if rsi_diff > 0 else "#e23343"

            # Draw the line connecting the old and new RSI values
            ax.plot(
                [i + 1, i + 1],
                [old_rsi_data[symbol], rsi_values[i]],
                color=line_color,
                linestyle="--",
                linewidth=0.75,  # Adjust the value to make the lines thinner
            )

    # Draw the average RSI line and add the annotation
    ax.axhline(
        xmin=0, xmax=1, y=average_rsi, color="#d58c3c", linestyle="--", linewidth=0.75
    )
    ax.text(
        len(rsi_symbols) + 1.5,  # Increase to move the text to the right
        average_rsi,
        f"AVG RSI: {average_rsi:.2f}",
        color="#d58c3c",
        va="bottom",
        ha="right",
        fontsize=15,
    )

    # Set the color of the tick labels to white
    ax.tick_params(colors="#a9aaab", which="both", length=0)

    # Set the y-axis limits based on RSI values
    ax.set_ylim(20, 80)

    # Extend the xlim to make room for the annotations
    ax.set_xlim(0, len(rsi_symbols) + 2)

    # Remove the x-axis ticks since we're annotating each point
    ax.set_xticks([])

    add_legend(ax)

    # Set the color of the spines to match the background color or make them invisible
    for spine in ax.spines.values():
        spine.set_edgecolor(BACKGROUND_COLOR)

    # Add the title in the top left corner
    plt.text(
        -0.025,
        1.125,
        "Crypto Market RSI Heatmap",
        transform=ax.transAxes,
        fontsize=14,
        verticalalignment="top",
        horizontalalignment="left",
        color="white",
        weight="bold",
    )

    plt.show()


def add_legend(ax: plt.Axes) -> None:
    # Create custom legend handles with square markers, including BTC price
    adjusted_colors = list(COLORS_LABELS.values())
    # Change NEUTRAL color to grey
    adjusted_colors[2] = "#808080"
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
            adjusted_colors,
            [label.upper() for label in list(COLORS_LABELS.keys())],
        )
    ]

    # Add legend
    legend = ax.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.05),
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


def get_RSI(coins: list, exchange: str = "BINANCE", time_frame: str = "1d") -> dict:
    # Format symbols exchange:symbol
    symbols = [f"{exchange.upper()}:{symbol}" for symbol in coins]

    analysis = get_multiple_analysis(
        symbols=symbols, interval=time_frame, screener="crypto"
    )

    # For each symbol get the RSI
    rsi_dict = {}
    for symbol in symbols:
        if analysis[symbol] is None:
            continue
        clean_symbol = symbol.replace(f"{exchange.upper()}:", "")
        clean_symbol = clean_symbol.replace("USDT", "")
        rsi_dict[clean_symbol] = analysis[symbol].indicators["RSI"]

    # Save the RSI data to a CSV file
    save_RSI(rsi_dict, time_frame)

    return rsi_dict


def get_closest_to_24h(
    file_path: str = "data/rsi_data.csv", time_frame: str = "1d"
) -> dict:
    # Read the CSV file into a DataFrame
    if not os.path.isfile(file_path):
        logger.error(f"No data found in {file_path}")
        return {}

    df = pd.read_csv(file_path)

    # Filter on the timeframe
    df = df[df["Time Frame"] == time_frame]

    # Convert the 'Date' column to datetime
    df["Date"] = pd.to_datetime(df["Date"])

    # Calculate the time difference from 24 hours ago
    target_time = datetime.datetime.now() - datetime.timedelta(hours=24)
    df["Time_Diff"] = abs(df["Date"] - target_time)

    # Find the minimum time difference
    min_time_diff = df["Time_Diff"].min()

    # Filter rows that have the minimum time difference
    closest_rows = df[df["Time_Diff"] == min_time_diff]

    # Convert the filtered rows to a dictionary with symbols as keys and RSI as values
    result = closest_rows.set_index("Symbol")["RSI"].to_dict()

    return result


def save_RSI(
    rsi_dict: dict, time_frame: str, file_path: str = "data/rsi_data.csv"
) -> None:
    # Convert the RSI dictionary to a DataFrame
    df = pd.DataFrame(list(rsi_dict.items()), columns=["Symbol", "RSI"])

    # Add the current date to the DataFrame
    df["Date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df["Time Frame"] = time_frame

    # Check if the file exists
    if os.path.isfile(file_path):
        # Append data to the existing CSV file
        df.to_csv(file_path, mode="a", header=False, index=False)
    else:
        # Save the DataFrame to a new CSV file with header
        df.to_csv(file_path, index=False)

    logger.debug(f"RSI data saved to {file_path}")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(RSI_heatmap(bot))
