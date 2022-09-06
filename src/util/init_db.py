# > Standard libaries
import requests

# > 3rd party dependencies
import pandas as pd
from pycoingecko import CoinGeckoAPI

# > Local dependencies
from util.tv_symbols import crypto_indices, stock_indices
from util.db import update_db
from util.vars import get_json_data

# Set the important database variables on startup and refresh every 24 hours
def set_cg_db():
    # Saves all CoinGecko coins, maybe refresh this daily
    cg = CoinGeckoAPI()
    cg_coins = pd.DataFrame(cg.get_coins_list())
    cg_coins["symbol"] = cg_coins["symbol"].str.upper()

    # Save cg_coins to database
    update_db("cg_crypto", cg_coins)


async def set_tv_db():
    """
    Gets the data from TradingView and saves it to the database.
    """

    # Get the current symbols and exchanges on TradingView
    tv_stocks = await get_json_data("https://scanner.tradingview.com/america/scan")[
        "data"
    ]
    tv_crypto = await get_json_data("https://scanner.tradingview.com/crypto/scan")[
        "data"
    ]
    tv_forex = await get_json_data("https://scanner.tradingview.com/forex/scan")["data"]
    tv_cfd = await get_json_data("https://scanner.tradingview.com/cfd/scan")["data"]

    # Convert the data to pandas dataframes
    tv_stocks = pd.DataFrame(tv_stocks).drop(columns=["d"])
    tv_stocks = pd.concat(
        [tv_stocks, pd.DataFrame(stock_indices, columns=["s"])]
    )  # Add the indices to the df
    tv_stocks[["exchange", "stock"]] = tv_stocks["s"].str.split(":", 1, expand=True)

    tv_crypto = pd.DataFrame(tv_crypto).drop(columns=["d"])
    tv_crypto = pd.concat([tv_crypto, pd.DataFrame(crypto_indices, columns=["s"])])
    tv_crypto[["exchange", "stock"]] = tv_crypto["s"].str.split(":", 1, expand=True)

    tv_forex = pd.DataFrame(tv_forex).drop(columns=["d"])
    tv_forex[["exchange", "stock"]] = tv_forex["s"].str.split(":", 1, expand=True)

    tv_cfd = pd.DataFrame(tv_cfd).drop(columns=["d"])
    tv_cfd[["exchange", "stock"]] = tv_cfd["s"].str.split(":", 1, expand=True)

    # Save the data to the database
    for db, name in [
        (tv_stocks, "tv_stocks"),
        (tv_crypto, "tv_crypto"),
        (tv_forex, "tv_forex"),
        (tv_cfd, "tv_cfd"),
    ]:
        update_db(db, name)
