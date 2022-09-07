# > 3rd party dependencies
import pandas as pd
import sqlite3
from pycoingecko import CoinGeckoAPI

# > Discord dependencies
from discord.ext import commands
from discord.ext.tasks import loop

# > Local dependencies
from util.tv_symbols import crypto_indices, stock_indices
from util.db import update_db
from util.vars import get_json_data


class DB_info:
    def set_cg_db(self, db: pd.DataFrame) -> None:
        self.cg_db = db

    def get_cg_db(self) -> pd.DataFrame:
        return self.cg_db

    def set_tv_stocks(self, db: pd.DataFrame) -> None:
        self.stocks = db

    def set_tv_crypto(self, db: pd.DataFrame) -> None:
        self.crypto = db

    def set_tv_forex(self, db: pd.DataFrame) -> None:
        self.forex = db

    def set_tv_cfd(self, db: pd.DataFrame) -> None:
        self.cfd = db

    def get_tv_stocks(self) -> pd.DataFrame:
        return self.stocks

    def get_tv_crypto(self) -> pd.DataFrame:
        return self.crypto

    def get_tv_forex(self) -> pd.DataFrame:
        return self.forex

    def get_tv_cfd(self) -> pd.DataFrame:
        return self.cfd

    def set_assets_db(self, db: pd.DataFrame) -> None:
        self.assets_db = db

    def get_assets_db(self) -> pd.DataFrame:
        return self.assets_db

    def set_portfolio_db(self, db: pd.DataFrame) -> None:
        self.portfolio_db = db

    def get_portfolio_db(self) -> pd.DataFrame:
        return self.portfolio_db


class DB(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db_info = DB_info()

        # Set the portfolio and assets db
        self.set_portfolio_db()
        self.set_assets_db()

        # Start the loops
        self.set_cg_db.start()
        self.set_tv_db.start()

    def set_portfolio_db(self):
        self.db_info.set_portfolio_db(get_db("portfolio"))

    def set_assets_db(self):
        self.db_info.set_assets_db(get_db("assets"))

    # Set the important database variables on startup and refresh every 24 hours
    @loop(hours=24)
    async def set_cg_db(self):
        # Saves all CoinGecko coins, maybe refresh this daily
        cg = CoinGeckoAPI()
        cg_coins = pd.DataFrame(cg.get_coins_list())
        cg_coins["symbol"] = cg_coins["symbol"].str.upper()

        # Save cg_coins to database
        update_db("cg_crypto", cg_coins)

        # Set cg_coins
        self.db_info.set_cg_db(cg_coins)

    @loop(hours=24)
    async def set_tv_db(self):
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
        tv_forex = await get_json_data("https://scanner.tradingview.com/forex/scan")[
            "data"
        ]
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

        # Set the data
        self.db_info.set_tv_stocks(tv_stocks)
        self.db_info.set_tv_crypto(tv_crypto)
        self.db_info.set_tv_forex(tv_forex)
        self.db_info.set_tv_cfd(tv_cfd)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(DB(bot))


def get_db(database_name: str) -> pd.DataFrame:
    """
    Get the database saved under data/<database_name>.pkl.
    If it does not exist return an empty dataframe.

    Parameters
    ----------
    str
        Name of the database to get.

    Returns
    -------
    pd.DataFrame
        Database saved under data/<database_name>.pkl.
    """

    db_loc = f"data/{database_name}.db"
    cnx = sqlite3.connect(db_loc)

    try:
        return pd.read_sql_query(f"SELECT * FROM {database_name}", cnx)
    except Exception:
        print(f"No {database_name}.db found, returning empty db")
        return pd.DataFrame()


def update_db(db: pd.DataFrame, database_name: str) -> None:
    """
    Update the database saved under data/database_name.pkl using db as the new database.

    Parameters
    ----------
    pd.DatFrame
        Database to use for updating old database.
    str
        Name of the database to update.

    Returns
    -------
    None
    """

    db_loc = f"data/{database_name}.db"
    db.to_sql(database_name, sqlite3.connect(db_loc), if_exists="replace", index=False)
