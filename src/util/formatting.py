# Standard libaries
from math import log, floor
import datetime

# Third party libraries
import pandas as pd
import discord

from util.vars import data_sources


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

    e = discord.Embed(
        title=f"Top {len(df)} {type}",
        url=url,
        description="",
        color=color,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )

    if source == "yahoo":
        # Format the data
        df.rename(columns={"Price (Intraday)": "Price"}, inplace=True)

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

    df = df.astype({"Symbol": str, "Price": float, "% Change": float, "Volume": float})

    df = df.round({"Price": 3, "% Change": 2, "Volume": 0})

    # Format the percentage change
    df["% Change"] = df["% Change"].apply(
        lambda x: f" (+{x}% 📈)" if x > 0 else f" ({x}% 📉)"
    )

    # Post symbol, current price (weightedAvgPrice) + change, volume
    df["Price"] = df["Price"].astype(str) + df["% Change"]

    # Format volume
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
