##> Imports
import asyncio

import ccxt.pro as ccxt

# > 3rd Party Dependencies
import pandas as pd

# > Discord dependencies
from discord.ext import commands

import util.vars

# Local dependencies
from constants.config import config
from constants.logger import logger
from util.db import get_db, update_db
from util.disc import get_channel, get_user, loop_error_catcher
from util.trades_msg import on_msg


class Trades(commands.Cog):
    """
    This class contains the cog for posting new trades done by users.
    It can be enabled / disabled in the config under ["LOOPS"]["TRADES"].
    """

    def __init__(
        self, bot: commands.Bot, db: pd.DataFrame = get_db("portfolio")
    ) -> None:
        self.bot = bot
        self.trades_channel = None
        # Start getting trades
        asyncio.create_task(self.trades(db))

    async def start_sockets(self, exchange, row, user) -> None:
        while True:
            try:
                msg = await exchange.watchMyTrades()
                await on_msg(msg, exchange, self.trades_channel, row, user)
            except ccxt.base.errors.AuthenticationError:
                # Send message to user and delete from database
                logger.error(row)
                break

            except Exception as e:
                # Maybe do: await exchange.close() and restart the socket
                logger.error(
                    f"Error in trade websocket for {row['user']} and {exchange.id}: {e}"
                )

    @loop_error_catcher
    async def trades(self, db: pd.DataFrame) -> None:
        """
        Starts the websockets for each user in the database.

        Parameters
        ----------
        db : pd.DataFrame
            The database containing all users.
        """
        if self.trades_channel is None:
            self.trades_channel = await get_channel(
                self.bot, config["LOOPS"]["TRADES"]["CHANNEL"]
            )

        tasks = []
        exchanges = []

        if not db.empty:
            # Divide per exchange
            binance = db.loc[db["exchange"] == "binance"]
            kucoin = db.loc[db["exchange"] == "kucoin"]

            if not binance.empty:
                for i, row in binance.iterrows():
                    # If using await, it will block other connections
                    exchange = ccxt.binance(
                        {"apiKey": row["key"], "secret": row["secret"]}
                    )
                    user = await get_user(self.bot, row["id"])

                    # Make sure that the API keys are valid
                    try:
                        exchange.fetch_balance()
                    except Exception:
                        # Send message to user and delete from database
                        await user.send(
                            "Your Binance API key is invalid, we have removed it from our database."
                        )

                        # Get the portfolio
                        util.vars.portfolio_db.drop(i, inplace=True)

                        update_db(util.vars.portfolio_db, "portfolio")

                        logger.debug(f"Removed Binance API key for {row['user']}")

                    task = asyncio.create_task(self.start_sockets(exchange, row, user))
                    tasks.append(task)
                    exchanges.append(exchange)
                    logger.info(f"Started Binance socket for {row['user']}")

            if not kucoin.empty:
                for _, row in kucoin.iterrows():
                    exchange = ccxt.kucoin(
                        {
                            "apiKey": row["key"],
                            "secret": row["secret"],
                            "password": row["passphrase"],
                        }
                    )
                    task = asyncio.create_task(
                        self.start_sockets(
                            exchange, row, await get_user(self.bot, row["id"])
                        )
                    )
                    tasks.append(task)
                    exchanges.append(exchange)
                    logger.debug(f"Started KuCoin socket for {row['user']}")

        # After 24 hours close the exchange and start again
        await asyncio.sleep(24 * 60 * 60)

        logger.debug("Stopping all sockets")
        for task, exchange in zip(tasks, exchanges):
            task.cancel()
            await exchange.close()
            await asyncio.sleep(10)

            # Restart the socket
            await self.trades(db)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Trades(bot))
