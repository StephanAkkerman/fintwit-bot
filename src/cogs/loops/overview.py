## > Imports
# > Standard libraries
from collections import Counter
import json
import datetime

# > Discord dependencies
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
import util.vars
from util.vars import config
from util.disc_util import get_channel
from util.db import update_db


class Overview(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.do_crypto = self.do_stocks = False

        if config["LOOPS"]["OVERVIEW"]["STOCKS"]["ENABLED"]:
            self.stocks_channel = get_channel(
                self.bot, config["LOOPS"]["OVERVIEW"]["STOCKS"]["CHANNEL"]
            )
            self.do_stocks = True

        if config["LOOPS"]["OVERVIEW"]["CRYPTO"]["ENABLED"]:
            self.crypto_channel = get_channel(
                self.bot, config["LOOPS"]["OVERVIEW"]["CRYPTO"]["CHANNEL"]
            )
            self.do_crypto = True

        if (
            config["LOOPS"]["OVERVIEW"]["STOCKS"]["ENABLED"]
            or config["LOOPS"]["OVERVIEW"]["CRYPTO"]["ENABLED"]
        ):
            self.overview.start()

    def clean_db(self, tweet_db):
        # Set the types
        tweet_db = tweet_db.astype(
            {
                "ticker": str,
                "user": str,
                "sentiment": str,
                "category": str,
                "timestamp": "datetime64[ns]",
            }
        )

        tweet_db = tweet_db[
            tweet_db["timestamp"]
            > datetime.datetime.now() - datetime.timedelta(hours=24)
        ]

        # Save the database
        util.vars.tweets_db = tweet_db
        update_db(tweet_db, "tweets")
        
        return tweet_db

    @loop(hours=1)
    async def overview(self):
        # Get the database
        tweet_db = util.vars.tweets_db

        # Remove all entries older than 24h
        if not tweet_db.empty:
            tweet_db = self.clean_db(tweet_db)

        # Make sure that the new db is also not empty
        if not tweet_db.empty:
            await self.make_overview(tweet_db, "stockS")
            await self.make_overview(tweet_db, "crypto")

    async def make_overview(self, tweet_db, keyword):
        # Post the overview for stocks and crypto
        db = tweet_db.loc[tweet_db["category"] == keyword]

        if db.empty:
            return

        # Get the top 10 mentions
        top10 = db["ticker"].value_counts()[:10]

        # Add overview of sentiment for each ticker
        for ticker, count in top10.items():

            # Get the sentiment for the ticker
            sentiment = db.loc[db["ticker"] == ticker]["sentiment"].tolist()

            # Convert sentiment into a single str, i.e. "6🐂 2🦆 2🐻"
            sentiment = json.dumps(dict(Counter(sentiment)))

            # Add count, symbol, sentiment to embed
            print(count, ticker, sentiment)


def setup(bot: commands.bot.Bot) -> None:
    bot.add_cog(Overview(bot))
