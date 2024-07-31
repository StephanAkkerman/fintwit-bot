##> Imports
# > Standard libaries
from __future__ import annotations

import numbers
import os
import pickle
import time
from io import StringIO
from typing import List, Optional

import pandas as pd
import tls_client
from bs4 import BeautifulSoup

# > Third party libraries
from pycoingecko import CoinGeckoAPI

# Local dependencies
import util.vars
from util.formatting import format_change
from util.tv_data import tv
from util.vars import logger, stables

cg = CoinGeckoAPI()
session = tls_client.Session(
    client_identifier="chrome112", random_tls_extension_order=True
)


def get_crypto_info(ids):
    if len(ids) > 1:
        id = None
        best_vol = 0
        coin_dict = None
        for symbol in ids.values:
            # Catch potential errors
            try:
                coin_info = cg.get_coin_by_id(symbol)
                if "usd" in coin_info["market_data"]["total_volume"]:
                    volume = coin_info["market_data"]["total_volume"]["usd"]
                    if volume > best_vol:
                        best_vol = volume
                        id = symbol
                        coin_dict = coin_info
            except Exception as e:
                logger.error(f"Error getting coin info for {symbol}, Error: {e}")
                pass

    else:
        id = ids.values[0]
        # Try in case the CoinGecko API does not work
        try:
            coin_dict = cg.get_coin_by_id(id)
        except Exception as e:
            logger.error(f"Error getting coin info for {id}, Error: {e}")
            return None, None

    return coin_dict, id


def get_coin_vol(coin_dict: dict) -> float:
    if "total_volume" in coin_dict["market_data"].keys():
        if "usd" in coin_dict["market_data"]["total_volume"].keys():
            return coin_dict["market_data"]["total_volume"]["usd"]
        else:
            return 1


def get_coin_price(coin_dict: dict) -> float:
    if "current_price" in coin_dict["market_data"].keys():
        if "usd" in coin_dict["market_data"]["current_price"].keys():
            return coin_dict["market_data"]["current_price"]["usd"]
        else:
            return 0


def get_coin_exchanges(coin_dict: dict) -> tuple[str, list]:
    base = None
    exchanges = []
    if "tickers" in coin_dict.keys():
        for info in coin_dict["tickers"]:
            if "base" in info.keys():
                # Somtimes the base is a contract instead of ticker
                if base is None:
                    # > 7, because $KOMPETE
                    if not (info["base"].startswith("0X") or len(info["base"]) > 7):
                        base = info["base"]

            if "market" in info.keys():
                exchanges.append(info["market"]["name"])

    return base, exchanges


def get_info_from_dict(coin_dict: dict):
    if coin_dict:
        if "market_data" in coin_dict.keys():
            volume = get_coin_vol(coin_dict)
            price = get_coin_price(coin_dict)

            change = None
            if "price_change_percentage_24h" in coin_dict["market_data"].keys():
                if isinstance(
                    coin_dict["market_data"]["price_change_percentage_24h"],
                    numbers.Number,
                ):
                    change = round(
                        coin_dict["market_data"]["price_change_percentage_24h"], 2
                    )

            # Get the exchanges
            base, exchanges = get_coin_exchanges(coin_dict)

            return volume, price, change, exchanges, base
    return 0, None, None, None, None


async def get_coin_info(
    ticker: str,
) -> Optional[tuple[float, str, List[str], float, str, str]]:
    """
    Gets the volume, website, exchanges, price, and change of the coin.
    This can only be called maximum 50 times per minute.

    Parameters
    ----------
    ticker : str
        The ticker of the coin.

    Returns
    -------
    float
        The volume of the coin.
    str
        The website of the coin.
    list[str]
        The exchanges of the coin.
    float
        The price of the coin.
    str
        The 24h price change of the coin.
    str
        The base symbol of the coin, e.g. BTC, ETH, etc.
    """

    id = change = None
    total_vol = 0
    exchanges = []
    change = "N/A"

    # Remove formatting from ticker input
    if ticker not in stables:
        for stable in stables:
            if ticker.endswith(stable):
                ticker = ticker[: -len(stable)]

    # Get the id of the ticker
    # Check if the symbol exists
    coin_dict = None
    if ticker in util.vars.cg_db["symbol"].values:
        # Check coin by symbol, i.e. "BTC"
        logger.debug(f"Cg_data ticker: {ticker}")
        coin_dict, id = get_crypto_info(
            util.vars.cg_db[util.vars.cg_db["symbol"] == ticker]["id"]
        )

        # Get the information from the dictionary
        if coin_dict:
            total_vol, price, change, exchanges, base = get_info_from_dict(coin_dict)

    # Try other methods if the information sucks
    if total_vol < 50000 or exchanges == [] or change == "N/A":
        # As a second options check the TradingView data
        price, perc_change, volume, exchange, website = await tv.get_tv_data(
            ticker, "crypto"
        )
        if volume != 0:
            return (
                volume,
                website,
                exchange,
                price,
                format_change(perc_change) if perc_change else "N/A",
                ticker,
            )

        # Third option is to check by id
        elif ticker.lower() in util.vars.cg_db["id"].values:
            coin_dict, id = get_crypto_info(
                util.vars.cg_db[util.vars.cg_db["id"] == ticker.lower()]["id"]
            )

        # Fourth option is to check by name, i.e. "Bitcoin"
        elif ticker in util.vars.cg_db["name"].values:
            coin_dict, id = get_crypto_info(
                util.vars.cg_db[util.vars.cg_db["name"] == ticker]["id"]
            )

        # Get the information from the dictionary
        total_vol, price, change, exchanges, base = get_info_from_dict(coin_dict)

    # remove duplicates and suffix 'exchange'
    if exchanges:
        exchanges = [x.lower().replace(" exchange", "") for x in exchanges]
        exchanges = list(set(exchanges))

    # Look into this!
    if total_vol != 0 and base is None:
        logger.debug("No base symbol found for:", ticker)
        base = ticker

    # Return the information
    return (
        total_vol,
        (
            f"https://coingecko.com/en/coins/{id}"
            if id
            else "https://coingecko.com/en/coins/id_not_found"
        ),
        exchanges,
        price,
        format_change(change) if change else "N/A",
        base,
    )


async def get_trending_coins() -> pd.DataFrame:
    """
    Gets the trending coins on CoinGecko without using their API.

    Returns
    -------
    DataFrame
        Symbol
            The tickers of the trending coins, formatted with the website.
        Price
            The prices of the trending coins.
        % Change
            The 24h price changes of the trending coins.
        Volume
            The volumes of the trending coins.
    """

    html = session.get(
        "https://www.coingecko.com/en/highlights/trending-crypto",
    )

    soup = BeautifulSoup(html.text, "html.parser")

    try:
        table = soup.find("table")

        if table is None:
            logger.error("Error getting trending coingecko coins, no table found.")
            return pd.DataFrame()

        # Try converting the table to pandas
        df = pd.read_html(StringIO(str(table)))[0]

        # Drop first row
        df = df.drop(0)

        # Split the "Coin" column into "Symbol" and "Name"
        # The last word is the symbol, the rest is the name
        df["Symbol"] = df["Coin"].apply(lambda x: x.split(" ")[-1])
        df["Name"] = df["Coin"].apply(lambda x: " ".join(x.split(" ")[:-1]))

        # Add website column to the dataframe
        df["Website"] = df["Name"].apply(
            lambda x: f"https://www.coingecko.com/en/coins/{x.lower().replace(' ', '-')}"
        )

        # Add website to Symbol using format: [Symbol](Website)
        df["Symbol"] = "[" + df["Symbol"] + "](" + df["Website"] + ")"

        # Replace NaN values in '24h Volume' with values from 'Mkt Cap'
        df["24h Volume"] = df["24h Volume"].fillna(df["Market Cap"])

        # Fix volume if it contains a %
        df.loc[df["24h Volume"].str.contains("%"), "24h Volume"] = df["Market Cap"]

        # Rename 24h to % Change and 24h Volume to Volume
        df.rename(columns={"24h": "% Change", "24h Volume": "Volume"}, inplace=True)

        # Remove $, %, and commas from the columns
        # TODO: maybe find something that removes all non-numerical characters
        df["Price"] = df["Price"].apply(
            lambda x: x.replace("$", "").replace(",", "").replace("Buy ", "")
        )
        df["% Change"] = df["% Change"].apply(lambda x: x.replace("%", ""))
        df["Volume"] = df["Volume"].apply(lambda x: x.replace("$", "").replace(",", ""))

        return df

    except Exception as e:
        logger.error(f"Error getting trending coingecko coins. Error: {e}")
        return pd.DataFrame()


async def get_top_categories() -> pd.DataFrame | None:
    html = session.get("https://www.coingecko.com/en/categories").text

    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("table")

    if table is None:
        logger.error("Error getting top categories from CoinGecko, no table found.")
        return

    data = []
    for tr in table.find_all("tr")[1:]:
        coin_data = {}

        for i, td in enumerate(tr.find_all("td")):
            # i == 0 -> rank

            # Category column (including name and link)
            if i == 1:
                coin_data["Name"] = td.find("a").text
                coin_data["Link"] = "https://www.coingecko.com/" + td.find("a")["href"]

            # 24h
            if i == 4:
                coin_data["24h Change"] = td["data-sort"]

            # Market cap
            if i == 6:
                coin_data["Market Cap"] = td["data-sort"]

            if i == 7:
                coin_data["Volume"] = td["data-sort"]

        if coin_data != {}:
            data.append(coin_data)

    return pd.DataFrame(data)


def get_top_vol_coins(length: int = 50) -> list:
    CACHE_FILE = "data/top_vol_coins_cache.pkl"
    CACHE_EXPIRATION = 24 * 60 * 60  # 24 hours in seconds
    # List of symbols to exclude
    STABLE_COINS = [
        "OKBUSDT",
        "DAIUSDT",
        "USDTUSDT",
        "USDCUSDT",
        "BUSDUSDT",
        "TUSDUSDT",
        "PAXUSDT",
        "EURUSDT",
        "GBPUSDT",
        "CETHUSDT",
        "WBTCUSDT",
    ]

    # Check if the cache file exists and is not expired
    os.makedirs(CACHE_FILE.split("/")[0], exist_ok=True)
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "rb") as f:
            cache_data = pickle.load(f)
            cache_time = cache_data["timestamp"]
            if time.time() - cache_time < CACHE_EXPIRATION:
                # Return the cached data if it's not expired
                logger.debug("Using cached top volume coins")
                return cache_data["data"][:length]

    # Fetch fresh data if the cache is missing or expired
    df = pd.DataFrame(cg.get_coins_markets("usd"))["symbol"].str.upper() + "USDT"

    sorted_volume = df[~df.isin(STABLE_COINS)]
    top_vol_coins = sorted_volume.tolist()

    # Save the result to the cache
    with open(CACHE_FILE, "wb") as f:
        pickle.dump({"timestamp": time.time(), "data": top_vol_coins}, f)

    return top_vol_coins[:length]
