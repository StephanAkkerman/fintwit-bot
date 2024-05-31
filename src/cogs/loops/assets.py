## > Imports
# > Standard libraries
from __future__ import annotations

import asyncio
import datetime

# > 3rd Party Dependencies
import discord
import numpy as np
import pandas as pd
from discord.ext import commands
from discord.ext.tasks import loop

# > Local dependencies
import util.vars
from util.cg_data import get_coin_info
from util.db import update_db
from util.disc_util import get_channel, get_guild, get_user
from util.exchange_data import get_data
from util.formatting import format_change, format_embed_length
from util.vars import config
from util.yf_data import get_stock_info


class Assets(commands.Cog):
    """
    The class is responsible for posting the assets of Discord users.
    You can enabled / disable it in config under ["LOOPS"]["ASSETS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.assets.start()

    async def usd_value(self, asset: str, exchange: str) -> tuple[float, float]:
        """
        Get the USD value of an asset, based on the exchange.

        Parameters
        ----------
        asset : str
            The ticker of the asset, i.e. 'BTC'.
        exchange : str
            The exchange the asset is on, currently only 'binance' and 'kucoin' are supported.

        Returns
        -------
        float
            The worth of this asset in USD.
        """

        usd_val = change = None

        if exchange.lower() != "stock":
            _, _, _, usd_val, change, _ = await get_coin_info(asset)
        else:
            _, _, _, usd_val, change, _ = await get_stock_info(
                asset, do_format_change=False
            )
            if isinstance(usd_val, list):
                usd_val = usd_val[0]
            if isinstance(change, list):
                change = change[0]

        return usd_val, change

    @loop(hours=1)
    async def assets(self) -> None:
        """
        Only do this function at startup and if a new portfolio has been added.
        Checks the account balances of accounts saved in portfolio db, then updates the assets db.

        Parameters
        ----------
        portfolio_db : pd.DataFrame
            The portfolio db or the db for a new user.

        Returns
        -------
        None
        """
        assets_db_columns = {
            "asset": str,
            "buying_price": float,
            "owned": float,
            "exchange": str,
            "id": np.int64,
            "user": str,
            "worth": float,
            "price": float,
            "change": float,
        }

        if util.vars.portfolio_db.empty:
            print("No portfolios in the database.")
            return

        # Drop all crypto assets, so we can update them
        if not util.vars.assets_db.empty:
            crypto_rows = util.vars.assets_db.index[
                util.vars.assets_db["exchange"] != "stock"
            ].tolist()
            assets_db = util.vars.assets_db.drop(index=crypto_rows)
        else:
            # Create a new database
            assets_db = pd.DataFrame(columns=list(assets_db_columns.keys()))

        # Get the assets of each user
        for _, row in util.vars.portfolio_db.iterrows():
            # Add this data to the assets db
            exch_data = await get_data(row)
            assets_db = pd.concat([assets_db, exch_data], ignore_index=True)

        # Ensure that the db knows the right types
        assets_db = assets_db.astype(assets_db_columns)

        # Update the assets db
        update_db(assets_db, "assets")
        util.vars.assets_db = assets_db

        # Post the assets
        await self.post_assets()

    async def update_prices_and_changes(self, new_df: pd.DataFrame) -> pd.DataFrame:
        """
        Updates the prices and changes of the stock assets in the DataFrame.
        """
        # Filter DataFrame to only include rows where exchange is "stock"
        stock_df = new_df[new_df["exchange"] == "stock"]

        # Asynchronously get price and change for each asset
        async def get_price_change(row):
            price, change = await self.usd_value(row["asset"], row["exchange"])
            return {
                "price": 0 if price is None else round(price, 2),
                "change": 0 if change is None else change,
                "worth": (
                    0
                    if price in [None, np.nan]
                    else round(price * float(row["owned"]), 2)
                ),
            }

        # Using asyncio.gather to run all async operations concurrently
        results = await asyncio.gather(
            *(get_price_change(row) for _, row in stock_df.iterrows())
        )

        # Update the DataFrame with the results
        for i, (index, row) in enumerate(stock_df.iterrows()):
            new_df.at[index, "price"] = results[i]["price"]
            new_df.at[index, "change"] = results[i]["change"]
            new_df.at[index, "worth"] = results[i]["worth"]

        return new_df

    async def format_exchange(
        self,
        exchange_df: pd.DataFrame,
        exchange: str,
        e: discord.Embed,
    ) -> discord.Embed:
        """
        Formats the embed used for updating user's assets.

        Parameters
        ----------
        exchange_df : pd.DataFrame
            The dataframe of assets owned by a user.
        exchange : str
            The exchange the assets are on, currently only 'binance' and 'kucoin' are supported.
        e : discord.Embed
            The embed to be formatted.
        old_worth : str
            The worth of the user's assets before the update.
        old_assets : str
            The assets of the user before the update.

        Returns
        -------
        discord.Embed
            The new embed.
        """

        # Necessary to prevent panda warnings
        new_df = exchange_df.copy()

        # Add stock data to the DataFrame
        stock_df = util.vars.assets_db[util.vars.assets_db["exchange"] == "stock"]
        if not stock_df.empty:
            new_df = await self.update_prices_and_changes(new_df)

        # Remove everything after % in change
        # new_df["change"] = new_df["change"].str.split("%").str[0]

        # Set the types (again)
        new_df = new_df.astype(
            {
                "asset": str,
                "buying_price": float,
                "owned": float,
                "exchange": str,
                "id": np.int64,
                "user": str,
                "worth": float,
                "price": float,
                "change": float,  # Make sure this is not the formatted change
            }
        )

        # Format the price change
        new_df["change"] = new_df["change"].apply(lambda x: format_change(x))

        # Format price and change
        new_df["price_change"] = (
            "$"
            + new_df["price"].astype(str)
            + " ("
            + new_df["change"].astype(str)
            + ")"
        )

        # Fill NaN values of worth
        new_df["worth"] = new_df["worth"].fillna(0)

        # Set buying price to float
        new_df["buying_price"] = new_df["buying_price"].astype(float)

        # Add worth_change column
        new_df["worth_change"] = "?"

        # Calculate the worth_change percentage only where buying_price is not 0
        mask = new_df["buying_price"] != 0
        new_df.loc[mask, "worth_change"] = round(
            ((new_df["price"] - new_df["buying_price"]) / new_df["buying_price"] * 100),
            2,
        )

        # Apply format_change to worth_change
        new_df.loc[mask, "worth_change"] = new_df.loc[mask, "worth_change"].apply(
            lambda x: format_change(x)
        )

        # Sort by usd value
        new_df = new_df.sort_values(by=["worth"], ascending=False)

        new_df["worth"] = (
            "$"
            + new_df["worth"].astype(str)
            + " ("
            + new_df["worth_change"].astype(str)
            + ")"
        )

        # Create the list of string values
        assets = "\n".join(new_df["asset"].to_list())
        prices = "\n".join(new_df["price_change"].to_list())
        worth = "\n".join(new_df["worth"].to_list())

        # Ensure that the length is not bigger than allowed
        assets, prices, worth = format_embed_length([assets, prices, worth])

        exchange_title = exchange
        if exchange.lower() in util.vars.custom_emojis.keys():
            exchange_title = f"{exchange} {util.vars.custom_emojis[exchange.lower()]}"

        # These are the new fields added to the embed
        e.add_field(name=exchange_title, value=assets, inline=True)
        e.add_field(name="Price", value=prices, inline=True)
        e.add_field(name="Worth", value=worth, inline=True)

        return e

    async def post_assets(self) -> None:
        """
        Posts the assets of the users that added their portfolio.

        Returns
        -------
        None
        """

        # Use the user name as channel
        for id in util.vars.assets_db["id"].unique():
            # Get the assets of this user
            user_assets = util.vars.assets_db.loc[util.vars.assets_db["id"] == id]

            # Only post if there are assets
            if not user_assets.empty:
                # Get the Discord objects
                channel = await self.get_user_channel(user_assets["user"].values[0])
                disc_user = await self.get_user(user_assets)

                e = discord.Embed(
                    title="",
                    description="",
                    color=0x1DA1F2,
                    timestamp=datetime.datetime.now(datetime.timezone.utc),
                )

                if disc_user:
                    e.set_author(
                        name=disc_user.name + "'s Assets",
                        icon_url=disc_user.display_avatar.url,
                    )

                # Finally, format the embed before posting it
                for exchange in ["Binance", "KuCoin", "Stock"]:
                    exchange_df = user_assets.loc[
                        user_assets["exchange"] == exchange.lower()
                    ]

                    if not exchange_df.empty:
                        e = await self.format_exchange(exchange_df, exchange, e)

                await channel.purge(limit=1)
                await channel.send(embed=e)

    async def get_user_channel(self, name: str) -> discord.TextChannel:
        """
        Based on the username returns the user specific channel.

        Parameters
        ----------
        name : str
            The name of the Discord user.

        Returns
        -------
        discord.TextChannel
            The user specific channel.
        """
        channel_name = config["LOOPS"]["ASSETS"]["CHANNEL_PREFIX"] + name.lower()

        # If this channel does not exist make it
        channel = get_channel(self.bot, channel_name)
        if channel is None:
            guild = get_guild(self.bot)
            channel = await guild.create_text_channel(
                channel_name, category=config["CATEGORIES"]["USERS"]
            )
            print(f"Created channel {channel_name}")

        return channel

    async def get_user(self, assets):
        id = assets["id"].values[0]
        disc_user = self.bot.get_user(id)

        if disc_user is None:
            try:
                disc_user = await get_user(self.bot, id)
            except Exception as e:
                print(f"Could not get user with id: {id}.\n{assets} \nError:", e)

        return disc_user


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Assets(bot))
