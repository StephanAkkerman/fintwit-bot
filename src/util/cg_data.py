##> Imports
# > Standard libaries
from __future__ import annotations
from typing import Optional, List
import numbers

# > Third party libraries
from pycoingecko import CoinGeckoAPI

# Local dependencies
import util.vars
from util.vars import stables, get_json_data
from util.tv_data import tv
from util.formatting import format_change

cg = CoinGeckoAPI()


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
            except Exception:
                pass

    else:
        id = ids.values[0]
        # Try in case the CoinGecko API does not work
        try:
            coin_dict = cg.get_coin_by_id(id)
        except Exception:
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
    base = "N/A"
    exchanges = []
    if "tickers" in coin_dict.keys():
        for info in coin_dict["tickers"]:
            if "base" in info.keys():
                # Somtimes the base is a contract instead of ticker
                if base == "N/A":
                    # > 7, because $KOMPETE
                    if not(info["base"].startswith("0X") and len(info["base"]) > 7):
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
        coin_dict, id = get_crypto_info(util.vars.cg_db[util.vars.cg_db["symbol"] == ticker]["id"])
        
        # Get the information from the dictionary
        if coin_dict:
            total_vol, price, change, exchanges, base = get_info_from_dict(coin_dict)

    # Try other methods if the information sucks
    if total_vol < 50000 or exchanges == [] or change == 'N/A':
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
            coin_dict, id = get_crypto_info(util.vars.cg_db[util.vars.cg_db["name"] == ticker]["id"])

        # Get the information from the dictionary
        total_vol, price, change, exchanges, base = get_info_from_dict(coin_dict)

    # Return the information
    return (
        total_vol,
        f"https://coingecko.com/en/coins/{id}"
        if id
        else "https://coingecko.com/en/coins/id_not_found",
        exchanges,
        price,
        format_change(change) if change else "N/A",
        base,
    )


async def get_trending_coins() -> tuple[list, list, list, list]:
    """
    Gets the trending coins on CoinGecko without using their API.

    Returns
    -------
    tuple[list, list, list, list]
        list
            The tickers of the trending coins, formatted with the website.
        list
            The prices of the trending coins.
        list
            The 24h price changes of the trending coins.
        list
            The volumes of the trending coins.
    """

    html = await get_json_data(
        "https://www.coingecko.com/en/watchlists/trending-crypto", text=True
    )

    # Get the table
    html = html[html.find("<tbody>") : html.find("</tbody>")]

    # Split headlines by <tr> until </tr>
    coins = html.split("<tr>")[1:]

    tickers = []
    prices = []
    changes = []
    volumes = []

    for coin in coins:

        # The price, 1h, 24h, 7d change is stored here
        data = coin.split("<td data-sort=")[1:]

        # This is used for getting the website
        slug = coin[
            coin.find('data-coin-slug="')
            + len('data-coin-slug="') : coin.find('" data-coin-image=')
        ]

        website = f"https://www.coingecko.com/en/coins/{slug}"

        ticker = coin[
            coin.find('data-coin-symbol="')
            + len('data-coin-symbol="') : coin.find('" data-source=')
        ]
        
        price = data[0][: data[0].find('class="td-price price text-right"')].replace(
                "'", ""
            )

        change = data[2][
                : data[2].find(
                    ' class="td-change24h change24h stat-percent text-right col-market">'
                )
            ].replace("'", "")

        volume = data[4][
                data[4].find('data-target="price.price">$')
                + len('data-target="price.price">$') : data[4].find("</span>")
            ].replace(",", "")
        
        # Ensure that the variables are numbers, otherwise fill with 0
        # There is no better way to do this...
        try:
            price = float(price)
        except Exception:
            price = 0
        try:
            change = float(change)
        except Exception:
            change = 0
        try:
            volume = float(volume)
        except Exception:
            volume = 0

        tickers.append(f"[{ticker.upper()}]({website})")
        prices.append(price)
        changes.append(change)
        volumes.append(volume)

    return tickers, prices, changes, volumes
