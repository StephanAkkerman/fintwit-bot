# > Standard library
import datetime
import asyncio
import time

# > 3rd party dependencies
import pandas as pd
import sqlite3
from pycoingecko import CoinGeckoAPI

# > Discord dependencies
from discord.ext import commands
from discord.ext.tasks import loop

# > Local dependencies
import util.vars
from util.tv_symbols import crypto_indices, stock_indices
from util.tv_data import get_tv_ticker_data


class DB(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        # Start loops
        self.set_tv_db.start()
        self.set_cg_db.start()

        # Set the portfolio and assets db
        self.set_portfolio_db()
        self.set_assets_db()
        self.set_tweets_db()

    def set_portfolio_db(self):
        util.vars.portfolio_db = get_db("portfolio")

    def set_assets_db(self):
        util.vars.assets_db = get_db("assets")

    def set_tweets_db(self):
        util.vars.tweets_db = get_db("tweets")

    # Set the important database variables on startup and refresh every 24 hours
    @loop(hours=24)
    async def set_cg_db(self):
        # Saves all CoinGecko coins, maybe refresh this daily
        cg = CoinGeckoAPI()
        cg_coins = pd.DataFrame(cg.get_coins_list())
        cg_coins["symbol"] = cg_coins["symbol"].str.upper()

        # Save cg_coins to database
        update_db(cg_coins, "cg_coins")

        # Set cg_coins
        util.vars.cg_db = cg_coins

    async def start_tv_loop(self):
        """Start the TV loop after 24h"""
        time.sleep(60 * 60 * 24)
        self.set_tv_db.start()

    @loop(hours=24)
    async def set_tv_db(self):
        """
        Gets the data from TradingView and saves it to the database.
        """

        # In case the function below fails
        util.vars.stocks = get_db("tv_stocks")
        util.vars.crypto = get_db("tv_crypto")
        util.vars.forex = get_db("tv_forex")
        util.vars.cfd = get_db("tv_cfd")

        # Get the current symbols and exchanges on TradingView
        tv_stocks = await get_tv_ticker_data(
            "https://scanner.tradingview.com/america/scan", stock_indices
        )
        tv_crypto = await get_tv_ticker_data(
            "https://scanner.tradingview.com/crypto/scan", crypto_indices
        )
        tv_forex = await get_tv_ticker_data(
            "https://scanner.tradingview.com/forex/scan"
        )
        tv_cfd = await get_tv_ticker_data("https://scanner.tradingview.com/cfd/scan")

        # Save the data to the database
        for db, name in [
            (tv_stocks, "tv_stocks"),
            (tv_crypto, "tv_crypto"),
            (tv_forex, "tv_forex"),
            (tv_cfd, "tv_cfd"),
        ]:
            if not db.empty:
                update_db(db, name)

                if name == "tv_stocks":
                    util.vars.stocks = db
                elif name == "tv_crypto":
                    util.vars.crypto = db
                elif name == "tv_forex":
                    util.vars.forex = db
                elif name == "tv_cfd":
                    util.vars.cfd = db


def setup(bot: commands.Bot) -> None:
    bot.add_cog(DB(bot))


def update_tweet_db(tickers: list, user: str, sentiment: str, category: str) -> None:

    # Prepare new data
    dict_list = []
    for ticker in tickers:
        dict_list.append(
            {
                "ticker": ticker,
                "user": user,
                "sentiment": sentiment.split(" - ")[0],
                "category": category,
            }
        )

    # Convert it to a dataframe
    tweet_db = pd.DataFrame(dict_list)

    # Add current time
    tweet_db["timestamp"] = datetime.datetime.now()

    # Get the old database
    old_db = util.vars.tweets_db

    # Merge with the old database
    if not old_db.empty:

        # Add tweet to database
        tweet_db = pd.concat([old_db, tweet_db])

    # Reset the index
    tweet_db = tweet_db.reset_index(drop=True)

    # Save database
    update_db(tweet_db, "tweets")
    util.vars.tweets_db = tweet_db


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
