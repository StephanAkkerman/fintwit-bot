# Standard libaries
import datetime
from math import floor, log

import discord

# Third party libraries
import pandas as pd

from constants.sources import data_sources


def format_change(change: float) -> str:
    """
    Converts a float to a string with a plus sign if the float is positive, and a minus sign if the float is negative.

    Parameters
    ----------
    change : float
        The percentual change of an asset.

    Returns
    -------
    str
        The formatted change.
    """
    if change is None:
        return "N/A"

    if isinstance(change, str):
        # Try to convert to float
        try:
            change = float(change)
        except ValueError:
            change = 0

    # Round to 2 decimals
    change = round(change, 2)

    return f"+{change}% 📈" if change > 0 else f"{change}% 📉"


def human_format(number: float, absolute: bool = False, decimals: int = 0) -> str:
    """
    Takes a number and returns a human readable string.
    Taken from: https://stackoverflow.com/questions/579310/formatting-long-numbers-as-strings-in-python/45846841.

    Parameters
    ----------
    number : float
        The number to be formatted.
    absolute : bool
        If True, the number will be converted to its absolute value.
    decimals : int
        The number of decimals to be used.

    Returns
    -------
    str
        The formatted number as a string.
    """

    # Try to convert to float
    if isinstance(number, str):
        try:
            number = float(number)
        except ValueError:
            number = 0

    if number == 0:
        return "0"

    # https://idlechampions.fandom.com/wiki/Large_number_abbreviations
    units = ["", "K", "M", "B", "t", "q"]
    k = 1000.0
    magnitude = int(floor(log(abs(number), k)))

    if decimals > 0:
        rounded_number = round(number / k**magnitude, decimals)
    else:
        rounded_number = int(number / k**magnitude)

    if absolute:
        rounded_number = abs(rounded_number)

    return f"{rounded_number}{units[magnitude]}"


def format_embed_length(data: list) -> list:
    """
    If the length of the data is greater than 1024 characters, it will be shortened to that amount.

    Parameters
    ----------
    data : list
        The list containing the description for an embed.

    Returns
    -------
    list
        The shortened description.
    """

    for x in range(len(data)):
        if len(data[x]) > 1024:
            data[x] = data[x][:1024].split("\n")[:-1]
            # Fix everything that is not x
            for y in range(len(data)):
                if x != y:
                    data[y] = "\n".join(data[y].split("\n")[: len(data[x])])

            data[x] = "\n".join(data[x])

    return data


# Used in gainers, losers loops
async def format_embed(og_df: pd.DataFrame, type: str, source: str) -> discord.Embed:
    """
    Formats the dataframe to an embed.

    Parameters
    ----------
    df : pd.DataFrame
        A dataframe with the columns:
        Symbol
        Price
        % Change
        Volume
    type : str
        The type used in the title of the embed
    source : str
        The source used for this data

    Returns
    -------
    discord.Embed
        A Discord embed containing the formatted data
    """

    df = og_df.copy()

    if source == "binance":
        url = "https://www.binance.com/en/altcoins/gainers-losers"
        color = data_sources["binance"]["color"]
        icon_url = data_sources["binance"]["icon"]
        name = "Coin"
    elif source == "yahoo":
        url = "https://finance.yahoo.com/most-active"
        color = data_sources["yahoo"]["color"]
        icon_url = data_sources["yahoo"]["icon"]
        name = "Stock"
    elif source == "coingecko":
        url = "https://www.coingecko.com/en/watchlists/trending-crypto"
        color = data_sources["coingecko"]["color"]
        icon_url = data_sources["coingecko"]["icon"]
        name = "Coin"
    elif source == "coinmarketcap":
        url = "https://coinmarketcap.com/trending-cryptocurrencies/"
        color = data_sources["coinmarketcap"]["color"]
        icon_url = data_sources["coinmarketcap"]["icon"]
        name = "Coin"
    elif source.startswith("tradingview"):
        color = data_sources["tradingview"]["color"]
        icon_url = data_sources["tradingview"]["icon"]
        name = "Stock"
        if source == "tradingview-premarket":
            url = "https://www.tradingview.com/markets/stocks-usa/market-movers-active-pre-market-stocks/"
        elif source == "tradingview-afterhours":
            url = "https://www.tradingview.com/markets/stocks-usa/market-movers-active-after-hours-stocks/"

    e = discord.Embed(
        title=f"Top {len(df)} {type}",
        url=url,
        description="",
        color=color,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )

    if source == "yahoo":
        # Format the data
        df.rename(
            columns={
                "regularMarketPrice": "Price",
                "regularMarketChange": "% Change",
                "regularMarketVolume": "Volume",
            },
            inplace=True,
        )

        # Add website to symbol
        df["Symbol"] = (
            "["
            + df["Symbol"]
            + "](https://finance.yahoo.com/quote/"
            + df["Symbol"]
            + ")"
        )

    # Only these columns are necessary
    df = df[["Symbol", "Price", "% Change", "Volume"]]

    if not source.startswith("tradingview"):
        df = df.astype(
            {"Symbol": str, "Price": float, "% Change": float, "Volume": float}
        )
        df = df.round({"Price": 3, "% Change": 2, "Volume": 0})
    else:
        df = df.astype(
            {"Symbol": str, "Price": float, "% Change": float, "Volume": str}
        )
        df = df.round({"Price": 3, "% Change": 2})

    # Apply format_change
    df["% Change"] = df["% Change"].apply(format_change)

    # Post symbol, current price (weightedAvgPrice) + change, volume
    df["Price"] = "$" + df["Price"].astype(str) + " (" + df["% Change"] + ")"

    # Format volume if it is not done already
    if not source.startswith("tradingview"):
        df["Volume"] = df["Volume"].apply(lambda x: "$" + human_format(x))

    ticker = "\n".join(df["Symbol"].tolist())
    prices = "\n".join(df["Price"].tolist())
    vol = "\n".join(df["Volume"].astype(str).tolist())

    # Prevent possible overflow
    ticker, prices, vol = format_embed_length([ticker, prices, vol])

    e.add_field(
        name=name,
        value=ticker,
        inline=True,
    )

    e.add_field(
        name="Price",
        value=prices,
        inline=True,
    )

    e.add_field(
        name="Volume",
        value=vol,
        inline=True,
    )

    # Set empty text as footer, so we can see the icon
    e.set_footer(text="\u200b", icon_url=icon_url)

    return e
