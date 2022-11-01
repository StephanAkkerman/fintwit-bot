##> Imports
import asyncio
import datetime
import threading

# > Discord dependencies
import discord
from discord.ext import commands

# > 3rd Party Dependencies
import pandas as pd
import ccxt.pro as ccxt

# Local dependencies
from util.db import get_db
from util.disc_util import get_channel, get_user
from util.vars import config
from util.trades_msg import on_msg

class Trades(commands.Cog):
    """
    This class contains the cog for posting new trades done by users.
    It can be enabled / disabled in the config under ["LOOPS"]["TRADES"].

    Methods
    -------
    trades(db : pd.DataFrame) -> None:
        Starts the websockets for each user in the database.
    """

    def __init__(
        self, bot: commands.Bot, db: pd.DataFrame = get_db("portfolio")
    ) -> None:
        self.bot = bot
        self.trades_channel = get_channel(
            self.bot, config["LOOPS"]["TRADES"]["CHANNEL"]
        )

        # Start getting trades
        asyncio.create_task(self.trades(db))
        
    async def start_sockets(self, exchange, row, user) -> None:
         
        while True:
            try:
                msg = await exchange.watchMyTrades()
                await on_msg(msg, exchange, self.trades_channel, row, user)
            except Exception as e:
                print(f"Error in trade websocket for {row['user']} and {exchange.id}: ", e)

    async def trades(self, db: pd.DataFrame) -> None:
        """
        Starts the websockets for each user in the database.

        Parameters
        ----------
        db : pd.DataFrame
            The database containing all users.
        """

        if not db.empty:

            # Divide per exchange
            binance = db.loc[db["exchange"] == "binance"]
            kucoin = db.loc[db["exchange"] == "kucoin"]

            if not binance.empty:
                for _, row in binance.iterrows():
                    # If using await, it will block other connections
                    asyncio.create_task(
                        self.start_sockets(ccxt.binance({'apiKey': row['key'], 'secret':row['secret']}), 
                                           row,
                                           await get_user(self.bot, row['id']))
                    )
                    print(f"Started Binance socket for {row['user']}")

            if not kucoin.empty:
                for _, row in kucoin.iterrows():
                    asyncio.create_task(
                        self.start_sockets(ccxt.kucoin({'apiKey': row['key'], 'secret':row['secret'], 'password': row['passphrase']}), 
                                           row,
                                           await get_user(self.bot, row['id']))
                    )
                    print(f"Started KuCoin socket for {row['user']}")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Trades(bot))
