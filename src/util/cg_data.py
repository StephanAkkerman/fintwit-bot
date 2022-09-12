##> Imports
# > Standard libaries
from __future__ import annotations
from typing import Optional, List

# > Third party libraries
from pycoingecko import CoinGeckoAPI

# Local dependencies
import util.vars
from util.vars import stables, format_change
from util.tv_data import tv

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

    elif len(ids) == 1:
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


def get_coin_exchanges(coin_dict: dict) -> list:
    if "tickers" in coin_dict.keys():
        if "exchange" in coin_dict["tickers"][0].keys():
            return [ticker["exchange"]["name"] for ticker in coin_dict["tickers"]]
        else:
            return []


def get_info_from_dict(coin_dict: dict):
    if coin_dict:
        if "market_data" in coin_dict.keys():
            volume = get_coin_vol(coin_dict)
            price = get_coin_price(coin_dict)

            if "price_change_percentage_24h" in coin_dict["market_data"].keys():
                change = round(
                    coin_dict["market_data"]["price_change_percentage_24h"], 2
                )
            else:
                change = "N/A"

            # Get the exchanges
            exchanges = get_coin_exchanges(coin_dict)

            return volume, price, change, exchanges
    return None, None, None, None


async def get_coin_info(
    ticker: str,
) -> Optional[tuple[float, str, List[str], float, str]]:
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
    """

    cg_coins = util.vars.cg_db

    # Remove formatting from ticker input
    if ticker not in stables:
        for stable in stables:
            if ticker.endswith(stable):
                ticker = ticker[: -len(stable)]

    # Get the id of the ticker
    # Check if the symbol exists
    coin_dict = None
    if ticker in cg_coins["symbol"].values:
        # Check coin by symbol, i.e. "BTC"
        coin_dict, id = get_crypto_info(cg_coins[cg_coins["symbol"] == ticker]["id"])

    if coin_dict is None:
        # As a second options check the TradingView data
        if tv_data := await tv.get_tv_data(ticker, "crypto"):
            # Unpack the data
            price, perc_change, volume, exchange, website = tv_data
            return (
                volume,
                website + "/?coingecko",
                exchange,
                price,
                format_change(perc_change),
            )

        # Third option is to check by id
        elif ticker.lower() in cg_coins["id"].values:
            coin_dict, id = get_crypto_info(
                cg_coins[cg_coins["id"] == ticker.lower()]["id"]
            )

        # Fourth option is to check by name, i.e. "Bitcoin"
        elif ticker in cg_coins["name"].values:
            coin_dict, id = get_crypto_info(cg_coins[cg_coins["name"] == ticker]["id"])

    # Get the information from the dictionary
    total_vol, price, change, exchanges = get_info_from_dict(coin_dict)

    # Return the information
    return (
        total_vol,
        f"https://coingecko.com/en/coins/{id}",
        exchanges,
        price,
        format_change(change),
    )
