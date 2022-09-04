## > Imports
# > Standard libraries
import datetime
from collections import Counter
import json

# > 3rd party dependencies
import pandas as pd

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config
from util.disc_util import get_channel
from util.db import get_db


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

    @loop(hours=1)
    async def overview(self):
        # Get the database
        tweet_db = get_db("tweets")

        if tweet_db.empty:
            return

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
