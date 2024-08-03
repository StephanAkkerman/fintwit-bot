import glob
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from io import BytesIO
from xml.etree import ElementTree

import discord
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import requests
from discord.ext import commands
from discord.ext.tasks import loop
from matplotlib import ticker
from tqdm import tqdm

from util.disc_util import get_channel, loop_error_catcher
from util.formatting import human_format
from util.vars import config, data_sources, logger

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
        ax2.set_ylim(
            bottom=df_price.min().values * 0.95, top=df_price.max().values * 1.05
        )
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
        file_name = "liquidations.png"
        file_path = os.path.join("temp", file_name)
        plt.savefig(file_path, bbox_inches="tight", dpi=300)
        plt.cla()
        plt.close()

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


def get_existing_files() -> list[str]:
    response = requests.get(
        "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/daily/liquidationSnapshot/BTCUSDT/"
    )
    tree = ElementTree.fromstring(response.content)

    files = []
    for content in tree.findall("{http://s3.amazonaws.com/doc/2006-03-01/}Contents"):
        key = content.find("{http://s3.amazonaws.com/doc/2006-03-01/}Key").text
        if key.endswith(".zip"):
            files.append(key)

    return files


def extract_date_from_filename(filename: str) -> str:
    return filename.split("liquidationSnapshot-")[-1].split(".")[0]


def get_local_dates(base_path: str, symbol: str, market: str):
    path_pattern = os.path.join(base_path, symbol, market, "*.csv")
    local_files = glob.glob(path_pattern)
    local_dates = {
        extract_date_from_filename(os.path.basename(file)) for file in local_files
    }
    return local_dates


def download_and_extract_zip(
    symbol: str, date: datetime, market: str = "cm", base_extract_to="./data"
):
    """
    Downloads a ZIP file from the given URL and extracts its contents to a subdirectory named after the symbol.

    Args:
    symbol (str): The symbol to download data for.
    date (datetime): The date for the data.
    market (str): The market type. Defaults to "cm".
    base_extract_to (str): The base directory to extract the contents to. Defaults to "./data".

    Returns:
    None
    """
    # Ensure the base_extract_to directory exists
    os.makedirs(base_extract_to, exist_ok=True)

    # Create a subdirectory for the symbol
    extract_to = os.path.join(base_extract_to, symbol)
    os.makedirs(extract_to, exist_ok=True)

    # Subdirectory for the market
    extract_to = os.path.join(extract_to, market)
    os.makedirs(extract_to, exist_ok=True)

    date_str = date.strftime("%Y-%m-%d")
    url = f"https://data.binance.vision/data/futures/{market}/daily/liquidationSnapshot/{symbol}/{symbol}-liquidationSnapshot-{date_str}.zip"

    try:
        # Step 1: Download the ZIP file
        response = requests.get(url)
        response.raise_for_status()  # Ensure the request was successful

        # Step 2: Extract the contents of the ZIP file
        with zipfile.ZipFile(BytesIO(response.content)) as zip_ref:
            zip_ref.extractall(extract_to)
    except requests.RequestException as e:
        logger.error(f"Failed to download {url}: {e}")
    except zipfile.BadZipFile as e:
        logger.error(f"Failed to extract {url}: {e}")


def get_new_data(
    symbol: str, market: str = "cm", base_extract_to: str = "./data"
) -> set[str]:
    existing_files = get_existing_files()
    existing_dates = {extract_date_from_filename(file) for file in existing_files}

    local_dates = get_local_dates(base_extract_to, symbol, market)
    missing_dates = existing_dates - local_dates

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(
                download_and_extract_zip,
                symbol,
                datetime.strptime(date, "%Y-%m-%d"),
                market,
                base_extract_to,
            )
            for date in missing_dates
        ]
        if futures:
            for future in tqdm(
                as_completed(futures), total=len(futures), desc="Downloading files"
            ):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error occurred: {e}")

    return missing_dates


def convert_timestamp_to_date(timestamp):
    return datetime.utcfromtimestamp(timestamp / 1000).strftime("%Y-%m-%d")


def summarize_liquidations(coin="BTCUSDT", market="um"):
    file_pattern = f"data/{coin}/{market}/*.csv"
    # Read all CSV files matching the pattern
    all_files = glob.glob(file_pattern)

    df_list = []
    for file in all_files:
        df = pd.read_csv(file)
        df_list.append(df)

    # Concatenate all DataFrames into a single DataFrame
    all_data = pd.concat(df_list, ignore_index=True)

    # Remove duplicate rows
    all_data.drop_duplicates(inplace=True)

    # Convert the 'time' column to date
    all_data["date"] = all_data["time"].apply(convert_timestamp_to_date)

    # Calculate total volume in USD
    all_data["volume"] = all_data["original_quantity"] * all_data["average_price"]

    # Summarize the data
    summary = (
        all_data.groupby(["date", "side"])
        .agg(
            total_volume=("volume", "sum"),
            total_liquidations=("original_quantity", "sum"),  # used for avg price
        )
        .reset_index()
    )

    summary["average_price"] = summary["total_volume"] / summary["total_liquidations"]

    # Pivot the summary to have separate columns for buy and sell sides
    pivot_summary = summary.pivot(
        index="date", columns="side", values=["total_volume", "average_price"]
    ).fillna(0)
    pivot_summary.columns = [
        "_".join(col).strip() for col in pivot_summary.columns.values
    ]
    pivot_summary = pivot_summary.rename(
        columns={
            "total_volume_BUY": "Buy Volume (USD)",
            "total_volume_SELL": "Sell Volume (USD)",
            "average_price_BUY": "Average Buy Price",
            "average_price_SELL": "Average Sell Price",
        }
    )

    # Calculate overall average price
    pivot_summary["Average Price"] = (
        pivot_summary["Average Buy Price"] * pivot_summary["Buy Volume (USD)"]
        + pivot_summary["Average Sell Price"] * pivot_summary["Sell Volume (USD)"]
    ) / (pivot_summary["Buy Volume (USD)"] + pivot_summary["Sell Volume (USD)"])

    # Drop individual average price columns if only overall average price is needed
    pivot_summary.drop(
        columns=["Average Buy Price", "Average Sell Price"], inplace=True
    )

    # Rename columns as required
    pivot_summary.rename(
        columns={
            "Buy Volume (USD)": "Shorts",
            "Sell Volume (USD)": "Longs",
            "Average Price": "price",
        },
        inplace=True,
    )

    # Convert the index to datetime and set it as index
    pivot_summary["date"] = pd.to_datetime(pivot_summary.index)
    pivot_summary = pivot_summary.set_index("date")

    # Save it locally
    os.makedirs("data/summary", exist_ok=True)
    os.makedirs(f"data/summary/{coin}", exist_ok=True)
    os.makedirs(f"data/summary/{coin}/{market}", exist_ok=True)
    pivot_summary.to_csv(f"data/summary/{coin}/{market}/liquidation_summary.csv")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Liquidations(bot))
