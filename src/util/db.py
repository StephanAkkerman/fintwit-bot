# > Standard library
import datetime
import os
import sqlite3
from collections import defaultdict

import numpy as np
import pandas as pd
from discord.ext import commands
from discord.ext.tasks import loop

import util.vars
from api.coingecko import get_coins_list, rate_limit
from api.nasdaq import tickers_nasdaq
from api.tradingview import get_tv_ticker_data
from constants.logger import logger
from constants.tradingview import all_forex_indices, crypto_indices, stock_indices

# Convert emoji to text
convert_emoji = defaultdict(
    lambda: "neutral", {"🐻": "bear", "🐂": "bull", "🦆": "neutral"}
)


class DB(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        # Check if the data folder exists
        os.makedirs("data", exist_ok=True)

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
        self.set_options_db()

    def set_portfolio_db(self):
        util.vars.portfolio_db = get_db("portfolio")
        if not util.vars.portfolio_db.empty:
            util.vars.portfolio_db["id"] = util.vars.portfolio_db["id"].astype(np.int64)

    def set_assets_db(self):
        util.vars.assets_db = get_db("assets")
        if not util.vars.assets_db.empty:
            util.vars.assets_db["id"] = util.vars.assets_db["id"].astype(np.int64)

    def set_tweets_db(self):
        util.vars.tweets_db = get_db("tweets")

    def set_options_db(self):
        util.vars.options_db = get_db("options")

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
            logger.error(f"Failed to get new nasdaq tickers, error: {e}")
            nasdaq_tickers = get_db("nasdaq_tickers")
            # Convert the dataframe to list
            util.vars.nasdaq_tickers = nasdaq_tickers.iloc[:, 0].tolist()

    # Set the important database variables on startup and refresh every 24 hours
    @loop(hours=24)
    async def set_cg_db(self):
        # Saves all CoinGecko coins, maybe refresh this daily
        coin_list = await get_coins_list()

        if isinstance(coin_list, dict) and rate_limit(coin_list):
            logger.warn(
                "Could not get CoinGecko coins, rate limit reached. Falling back to old data."
            )

            # Get the old data
            cg_coins = get_db("cg_coins")
        else:
            cg_coins = pd.DataFrame(coin_list)

            # Convert the symbol to uppercase
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


def remove_old_rows(db: pd.DataFrame, days: int) -> pd.DataFrame:
    """
    Removes the old rows from the database and return it.
    """

    # Set timestamp column to datetime
    db["timestamp"] = pd.to_datetime(db["timestamp"])

    return db[db["timestamp"] > datetime.datetime.now() - datetime.timedelta(days=days)]


def merge_and_update(
    main_db: pd.DataFrame, new_data: pd.DataFrame, db_name: str
) -> pd.DataFrame:
    merged = pd.concat([main_db, new_data], ignore_index=True)
    update_db(merged, db_name)
    return merged


def clean_old_db(db, days: int = 1) -> pd.DataFrame:
    """
    Cleans the tweets database and returns it.

    Returns
    -------
    pd.Dataframe
        The cleaned tweets database.
    """

    # If the database is empty, do nothing and return
    if db.empty:
        return db

    # Set the types
    try:
        db = remove_old_rows(db, days)
        return db
    except Exception as e:
        logger.error(f"Error in clean_old_db: {e}")
        logger.error(db.to_string())


def update_tweet_db(
    tickers: list, user: str, sentiment: str, categories: list, changes: list
) -> None:
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
        # Remove emoji at end
        change = changes[i]
        if change:
            if "%" in change:
                change = change[:-1]
            else:
                change = "None"
        else:
            change = "None"

        dict_list.append(
            {
                "ticker": tickers[i],
                "user": user,
                "sentiment": convert_emoji[sentiment],
                "category": categories[i],
                "change": change,
            }
        )

    # Convert it to a dataframe
    tweet_db = pd.DataFrame(dict_list)

    # Add current time
    tweet_db["timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    util.vars.tweets_db = clean_old_db(util.vars.tweets_db, 1)
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

    script_dir = os.path.dirname(__file__)
    db_loc = os.path.join(script_dir, "..", "..", "data", f"{database_name}.db")

    try:
        cnx = sqlite3.connect(db_loc)
        return pd.read_sql_query(f"SELECT * FROM {database_name}", cnx)
    except Exception:
        logger.error(f"No {database_name}.db found, returning empty db")
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

    # Convert everything to string to prevent errors
    # Using map on each column
    for column in db.columns:
        db[column] = db[column].map(str)

    try:
        db.to_sql(
            database_name, sqlite3.connect(db_loc), if_exists="replace", index=False
        )
    except Exception as e:
        logger.error(
            f"Error updating {database_name}.db: {e}.\nTried to update database:\n{db.to_string()}"
        )
