import datetime

import discord
import pandas as pd
from discord.ext import commands
from discord.ext.tasks import loop

import util.vars
from api.tradingview_ideas import scraper
from constants.config import config
from constants.sources import data_sources
from util.db import update_db
from util.disc import get_channel, get_tagged_users, loop_error_catcher


class TradingView_Ideas(commands.Cog):
    """
    This class contains the cog for posting the latest Trading View ideas.
    It can be enabled / disabled in the config under ["LOOPS"]["TV_IDEAS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["IDEAS"]["CRYPTO"]["ENABLED"]:
            self.crypto_channel = None
            self.crypto_ideas.start()

        if config["LOOPS"]["IDEAS"]["STOCKS"]["ENABLED"]:
            self.stocks_channel = None
            self.stock_ideas.start()

        if config["LOOPS"]["IDEAS"]["FOREX"]["ENABLED"]:
            self.forex_channel = None
            self.forex_ideas.start()

    def add_id_to_db(self, id: str) -> None:
        """
        Adds the given id to the database.
        """

        util.vars.ideas_ids = pd.concat(
            [
                util.vars.ideas_ids,
                pd.DataFrame(
                    [
                        {
                            "id": id,
                            "timestamp": datetime.datetime.now(),
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    async def send_embed(self, df: pd.DataFrame, type: str) -> None:
        """
        Creates an embed based on the given DataFrame and type.
        Then sends this embed in the designated channel.

        Parameters
        ----------
        df : pd.DataFrame
            The dataframe with the ideas.
        type : str
            The type of ideas, either "stocks" or "crypto".

        Returns
        -------
        None
        """

        # Get the database
        if not util.vars.ideas_ids.empty:
            # Set the types
            util.vars.ideas_ids = util.vars.ideas_ids.astype(
                {
                    "id": str,
                    "timestamp": "datetime64[ns]",
                }
            )

            # Only keep ids that are less than 72 hours old
            util.vars.ideas_ids = util.vars.ideas_ids[
                util.vars.ideas_ids["timestamp"]
                > datetime.datetime.now() - datetime.timedelta(hours=72)
            ]

        counter = 1
        for _, row in df.iterrows():
            if not util.vars.ideas_ids.empty:
                if row["Url"] in util.vars.ideas_ids["id"].tolist():
                    counter += 1
                    continue

            self.add_id_to_db(row["Url"])

            if row["Label"] == "Long":
                color = 0x3CC474
            elif row["Label"] == "Short":
                color = 0xE40414
            else:
                color = 0x808080

            e = discord.Embed(
                title=row["Title"],
                url=row["Url"],
                description=row["Description"],
                color=color,
                timestamp=row["Timestamp"],
            )

            e.set_image(url=row["ImageURL"])

            e.add_field(
                name="Symbol",
                value=row["Symbol"] if row["Symbol"] is not None else "None",
                inline=True,
            )
            e.add_field(name="Timeframe", value=row["Timeframe"], inline=True)
            e.add_field(name="Prediction", value=row["Label"], inline=True)

            e.set_footer(
                text=f"👍 {row['Likes']} | 💬 {row['Comments']}",
                icon_url=data_sources["tradingview"]["icon"],
            )

            if type == "stocks":
                channel = self.stocks_channel
            elif type == "crypto":
                channel = self.crypto_channel
            elif type == "forex":
                channel = self.forex_channel

            await channel.send(content=get_tagged_users([row["Symbol"]]), embed=e)

            counter += 1

            # Only show the top 10 ideas
            if counter == 11:
                break
        # Write to db
        update_db(util.vars.ideas_ids, "ideas_ids")

    @loop(hours=24)
    @loop_error_catcher
    async def crypto_ideas(self) -> None:
        """
        This function posts the crypto Trading View ideas.

        Returns
        -------
        None
        """
        if self.crypto_channel is None:
            self.crypto_channel = await get_channel(
                self.bot,
                config["LOOPS"]["IDEAS"]["CHANNEL"],
                config["CATEGORIES"]["CRYPTO"],
            )

        df = await scraper("crypto")
        await self.send_embed(df, "crypto")

    @loop(hours=24)
    @loop_error_catcher
    async def stock_ideas(self) -> None:
        """
        This function posts the stocks Trading View ideas.

        Returns
        -------
        None
        """
        if self.stocks_channel is None:
            self.stocks_channel = await get_channel(
                self.bot,
                config["LOOPS"]["IDEAS"]["CHANNEL"],
                config["CATEGORIES"]["STOCKS"],
            )
        df = await scraper("stocks")
        await self.send_embed(df, "stocks")

    @loop(hours=24)
    @loop_error_catcher
    async def forex_ideas(self) -> None:
        """
        This function posts the forex Trading View ideas.

        Returns
        -------
        None
        """
        if self.forex_channel is None:
            self.forex_channel = await get_channel(
                self.bot,
                config["LOOPS"]["IDEAS"]["CHANNEL"],
                config["CATEGORIES"]["FOREX"],
            )
        df = await scraper("currencies")
        await self.send_embed(df, "forex")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(TradingView_Ideas(bot))
