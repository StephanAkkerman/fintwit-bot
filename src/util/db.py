# > Standard library
import datetime

# > 3rd party dependencies
import pandas as pd
import sqlite3
from pycoingecko import CoinGeckoAPI
from yahoo_fin.stock_info import tickers_nasdaq
import numpy as np

# > Discord dependencies
from discord.ext import commands
from discord.ext.tasks import loop

# > Local dependencies
import util.vars
from util.tv_symbols import crypto_indices, stock_indices, all_forex_indices
from util.tv_data import get_tv_ticker_data


class DB(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        # Start loops
        self.set_tv_db.start()
        self.set_cg_db.start()
        self.set_nasdaq_tickers.start()
        
        # Set the portfolio and assets db
        self.set_portfolio_db()
        self.set_assets_db()
        self.set_tweets_db()
        self.set_reddit_ids_db()
        self.set_ideas_ids_db()
        self.set_classified_tickers_db()

    def set_portfolio_db(self):
        util.vars.portfolio_db = get_db("portfolio")

    def set_assets_db(self):
        assets_db = get_db("assets")
        assets_db["id"] = assets_db["id"].astype(np.int64)
        util.vars.assets_db = assets_db

    def set_tweets_db(self):
        util.vars.tweets_db = get_db("tweets")

    def set_reddit_ids_db(self):
        util.vars.reddit_ids = get_db("reddit_ids")
        
    def set_ideas_ids_db(self):
        util.vars.ideas_ids = get_db("ideas_ids")
        
    def set_classified_tickers_db(self):
        util.vars.classified_tickers = get_db("classified_tickers")

    @loop(hours=24)
    async def set_nasdaq_tickers(self):
        try:
            util.vars.nasdaq_tickers = tickers_nasdaq()
            update_db(pd.DataFrame(util.vars.nasdaq_tickers), "nasdaq_tickers")

        except Exception as e:
            print("Failed to get new nasdaq tickers, error:", e)
            nasdaq_tickers = get_db("nasdaq_tickers")
            # Convert the dataframe to list
            util.vars.nasdaq_tickers = nasdaq_tickers.iloc[:, 0].tolist()

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
            "https://scanner.tradingview.com/forex/scan", all_forex_indices
        )

        # tv_cfd = await get_tv_ticker_data("https://scanner.tradingview.com/cfd/scan")

        # Save the data to the database
        for db, name in [
            (tv_stocks, "tv_stocks"),
            (tv_crypto, "tv_crypto"),
            (tv_forex, "tv_forex"),
            # (tv_cfd, "tv_cfd"),
        ]:
            if not db.empty:
                update_db(db, name)

                if name == "tv_stocks":
                    util.vars.stocks = db
                elif name == "tv_crypto":
                    util.vars.crypto = db
                elif name == "tv_forex":
                    util.vars.forex = db
                # elif name == "tv_cfd":
                #    util.vars.cfd = db


def setup(bot: commands.Bot) -> None:
    bot.add_cog(DB(bot))

def remove_old_rows(db: pd.DataFrame, days : int) -> pd.DataFrame:
    """
    Removes the old rows from the database and return it.
    """
    
    # Set timestamp column to datetime
    db["timestamp"] = pd.to_datetime(db["timestamp"])
    
    return db[db["timestamp"] > datetime.datetime.now() - datetime.timedelta(days=days)]

def merge_and_update(main_db : pd.DataFrame, new_data : pd.DataFrame, db_name : str) -> pd.DataFrame:
    merged = pd.concat([main_db, new_data], ignore_index=True)
    update_db(merged, db_name)
    return merged

def clean_tweets_db() -> None:
    """
    Cleans the tweets database and returns it.

    Returns
    -------
    pd.Dataframe
        The cleaned tweets database.
    """

    # If the database is empty, do nothing and return
    if util.vars.tweets_db.empty:
        return util.vars.tweets_db

    # Set the types
    util.vars.tweets_db = util.vars.tweets_db.astype(
        {
            "ticker": str,
            "user": str,
            "sentiment": str,
            "category": str,
            "timestamp": "datetime64[ns]",
        }
    )

    util.vars.tweets_db = remove_old_rows(util.vars.tweets_db, 1)


def update_tweet_db(tickers: list, user: str, sentiment: str, categories: list) -> None:
    """
    Updates thet tweet database variable using the info provided.

    Parameters
    ----------
    tickers : list
        The list of tickers.
    user : str
        The name of the user.
    sentiment : str
        The sentiment of the tweet.
    categories : list
        The categories of the tickers.
    """

    # Prepare new data
    dict_list = []

    for i in range(len(tickers)):
        dict_list.append(
            {
                "ticker": tickers[i],
                "user": user,
                "sentiment": sentiment,
                "category": categories[i],
            }
        )

    # Convert it to a dataframe
    tweet_db = pd.DataFrame(dict_list)

    # Add current time
    tweet_db["timestamp"] = datetime.datetime.now()
    
    clean_tweets_db()
    util.vars.tweets_db = merge_and_update(util.vars.tweets_db, tweet_db, "tweets")

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
