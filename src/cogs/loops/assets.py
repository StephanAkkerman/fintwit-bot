## > Imports
# > Standard libraries
from __future__ import annotations
import asyncio
import datetime

# > 3rd Party Dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop
import pandas as pd

# > Local dependencies
import util.vars
from cogs.loops.trades import Binance, KuCoin
from util.yf_data import get_stock_info
from util.cg_data import get_coin_info
from util.db import update_db
from util.disc_util import get_channel, get_user
from util.vars import stables, config
from util.disc_util import get_guild
from util.formatting import format_embed_length


class Assets(commands.Cog):
    """
    The class is responsible for posting the assets of Discord users.
    You can enabled / disable it in config under ["LOOPS"]["ASSETS"].

    Methods
    ----------
    usd_value(asset : str, owned : float, exchange : str) -> float:
        Get the USD value of an asset, based on the exchange.
    assets(db : pd.DataFrame) -> None:
        Checks the account balances of accounts saved in portfolio db, then updates the assets db.
    format_exchange(exchange_df : pd.DataFrame, exchange : str, e : discord.Embed, old_worth : str, old_assets : str) -> discord.Embed:
        Formats the embed used for updating user's assets.
    post_assets() -> None:
        Posts the assets of the users that added their portfolio.
    """

    def __init__(
        self, bot: commands.Bot, db: pd.DataFrame = util.vars.portfolio_db
    ) -> None:
        self.bot = bot

        # Refresh assets
        asyncio.create_task(self.assets(db))

    async def usd_value(self, asset: str, owned: float, exchange: str) -> float:
        """
        Get the USD value of an asset, based on the exchange.

        Parameters
        ----------
        asset : str
            The ticker of the asset, i.e. 'BTC'.
        owned : float
            The amount of the asset owned.
        exchange : str
            The exchange the asset is on, currently only 'binance' and 'kucoin' are supported.

        Returns
        -------
        float
            The worth of this asset in USD.
        """

        usd_val = 0

        # Check the corresponding exchange
        if exchange == "binance":
            usd_val = await Binance(self.bot, None, None).get_usd_price(asset)
        elif exchange == "kucoin":
            usd_val = await KuCoin(self.bot, None, None).get_quote_price(
                asset + "-USDT"
            )

        if usd_val == 0:
            _, _, _, price, _, _ = await get_coin_info(asset)
            return price * owned
        else:
            return usd_val * owned

    async def assets(self, db: pd.DataFrame) -> None:
        """
        Only do this function at startup and if a new portfolio has been added.
        Checks the account balances of accounts saved in portfolio db, then updates the assets db.

        Parameters
        ----------
        db : pd.DataFrame
            The portfolio db or the db for a new user.

        Returns
        -------
        None
        """

        if db.equals(util.vars.portfolio_db):
            # Drop all crypto assets
            old_db = util.vars.assets_db
            crypto_rows = old_db.index[old_db["exchange"] != "stock"].tolist()
            assets_db = old_db.drop(index=crypto_rows)
        else:
            # Add it to the old assets db, since this call is for a specific person
            assets_db = util.vars.assets_db

        # Ensure that the db knows the right types
        assets_db = assets_db.astype(
            {"asset": str, "owned": float, "exchange": str, "id": "int64", "user": str}
        )

        if not db.empty:

            # Divide per exchange
            binance = db.loc[db["exchange"] == "binance"]
            kucoin = db.loc[db["exchange"] == "kucoin"]

            if not binance.empty:
                for _, row in binance.iterrows():
                    # Add this data to the assets.pkl database
                    assets_db = pd.concat(
                        [assets_db, await Binance(self.bot, row, None).get_data()],
                        ignore_index=True,
                    )

            if not kucoin.empty:
                for _, row in kucoin.iterrows():
                    assets_db = pd.concat(
                        [assets_db, await KuCoin(self.bot, row, None).get_data()],
                        ignore_index=True,
                    )

        # Sum values where assets and names are the same
        assets_db = assets_db.astype(
            {"asset": str, "owned": float, "exchange": str, "id": "int64", "user": str}
        )

        # Get USD value of each asset
        for index, row in assets_db.iterrows():

            # Do not check stocks
            if row["exchange"] == "stock":
                continue

            # Stables is always the same in USD
            if row["asset"] in stables:
                if row["owned"] < 1:
                    assets_db.drop(index, inplace=True)
                continue

            # Remove small quantities, 0.005 btc is 20 usd
            if round(row["owned"], 3) == 0:
                assets_db.drop(index, inplace=True)
                continue

            usd_val = await self.usd_value(row["asset"], row["owned"], row["exchange"])

            # Remove assets below threshold
            if usd_val < 1:
                assets_db.drop(index, inplace=True)

        # Update the assets db
        update_db(assets_db, "assets")
        util.vars.assets_db = assets_db

        print("Updated assets database")

        self.post_assets.start()

    async def format_exchange(
        self,
        exchange_df: pd.DataFrame,
        exchange: str,
        e: discord.Embed,
        old_worth: str,
        old_assets: str,
    ) -> tuple[discord.Embed, bool]:
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
        
        old_df = None

        if old_worth and old_assets:
            old_worth = old_worth.replace("$", "")
            old_worth = old_worth.split("\n")
            # Remove the emoji + whitespace
            old_worth = [x[:-2] for x in old_worth]
            
            old_assets = old_assets.split("\n")

            old_df = pd.DataFrame({"asset": old_assets, "old_worth": old_worth})
            old_df["old_worth"] = pd.to_numeric(old_df["old_worth"])

        # Sort and clean the data
        sorted_df = exchange_df.sort_values(by=["owned"], ascending=False)

        # Round by 3 and drop everything that is 0
        sorted_df = sorted_df.round({"owned": 3})
        exchange_df = sorted_df.drop(sorted_df[sorted_df.owned == 0].index)

        usd_values = []
        for sym in exchange_df["asset"].to_list():
            if sym not in stables:
                usd_val = 0
                if exchange == "Binance":
                    usd_val = await Binance(self.bot, None, None).get_usd_price(sym)
                elif exchange == "Kucoin":
                    usd_val = await KuCoin(self.bot, None, None).get_quote_price(
                        sym + "-USDT"
                    )
                elif exchange == "Stocks":
                    usd_val = await get_stock_info(sym)
                    usd_val = usd_val[3][0]

                if usd_val == 0 and exchange != "Stocks":
                    # Exchange is None, because it is not on this exchange
                    usd_val = await self.usd_value(sym, 1, None)
                usd_values.append(usd_val)
            else:
                usd_values.append(1)

        # Add new column for usd values
        exchange_df["usd_value"] = usd_values

        # Multiply it with the owned amount
        exchange_df["usd_value"] = exchange_df["usd_value"] * exchange_df["owned"]

        # Round it to 2 decimals
        exchange_df = exchange_df.round({"usd_value": 2})

        # Sort by usd value
        final_df = exchange_df.sort_values(by=["usd_value"], ascending=False)
        
        # Compare with the old df
        if old_df is not None:
            final_df = pd.merge(final_df, old_df, on="asset")
            final_df["worth_change"] = final_df["usd_value"] - final_df["old_worth"]
            final_df["worth_display"] = final_df["worth_change"].apply(
                lambda row: " 🔴" if row < 0 else (" 🔘" if row == 0 else " 🟢")
            )
            final_df["usd_value"] = "$" + final_df["usd_value"].astype(str) + final_df["worth_display"]
        else:
            final_df["usd_value"] = "$" + final_df["usd_value"].astype(str)

        # Convert owned to string
        final_df["owned"] = final_df["owned"].astype(str)

        # Create the list of string values
        assets = "\n".join(final_df["asset"].to_list())
        owned = "\n".join(final_df["owned"].to_list())
        values = "\n".join(final_df["usd_value"].to_list())

        # Ensure that the length is not bigger than allowed
        assets, owned, values = format_embed_length([assets, owned, values])

        # These are the new fields added to the embed
        e.add_field(name=exchange, value=assets, inline=True)
        e.add_field(name="Quantity", value=owned, inline=True)
        e.add_field(name="Worth", value=values, inline=True)

        # If all rows end with 🔘 don't send the embed
        if old_df is not None:
            if final_df["worth_display"].str.endswith("🔘").all():
                return e, True

        return e, False

    @loop(hours=12)
    async def post_assets(self) -> None:
        """
        Posts the assets of the users that added their portfolio.

        Returns
        -------
        None
        """

        guild = get_guild(self.bot)

        # Use the user name as channel
        names = util.vars.assets_db["user"].unique()

        for name in names:
            channel_name = config["LOOPS"]["ASSETS"]["CHANNEL_PREFIX"] + name.lower()

            # If this channel does not exist make it
            channel = get_channel(self.bot, channel_name)
            if channel is None:
                channel = await guild.create_text_channel(
                    channel_name, category=config["CATEGORIES"]["USERS"]
                )
                print(f"Created channel {channel_name}")

            # Get the data
            assets = util.vars.assets_db.loc[util.vars.assets_db["user"] == name]
            id = assets["id"].values[0]
            disc_user = self.bot.get_user(id)

            if disc_user == None:
                disc_user = await get_user(self.bot, id)

            # Only post if there are assets
            if not assets.empty:
                # Get the old message
                last_msg = await channel.history().find(
                    lambda m: m.author.id == self.bot.user.id
                )
                
                binance_worth = kucoin_worth = stocks_worth = None
                binance_coins = kucoin_coins = stocks_owned = None

                # Gets the old values so we can compare with the new ones
                if last_msg:
                    old_fields = last_msg.embeds[0].to_dict()["fields"]
                    if old_fields[0]["name"] == "Binance":
                        binance_worth = old_fields[2]["value"]
                        binance_coins = old_fields[0]["value"]
                    elif old_fields[0]["name"] == "KuCoin":
                        kucoin_worth = old_fields[2]["value"]
                        kucoin_coins = old_fields[0]["value"]
                    elif old_fields[0]["name"] == "Stocks":
                        stocks_worth = old_fields[2]["value"]
                        stocks_owned = old_fields[0]["value"]

                    if len(old_fields) > 3:
                        if old_fields[3]["name"] == "KuCoin":
                            kucoin_worth = old_fields[5]["value"]
                            kucoin_coins = old_fields[3]["value"]
                        elif old_fields[3]["name"] == "Stocks":
                            stocks_worth = old_fields[5]["value"]
                            stocks_owned = old_fields[3]["value"]

                    if len(old_fields) > 6:
                        if old_fields[6]["name"] == "Stocks":
                            stocks_worth = old_fields[8]["value"]
                            stocks_owned = old_fields[6]["value"]

                e = discord.Embed(
                    title="",
                    description="",
                    color=0x1DA1F2,
                    timestamp=datetime.datetime.now(datetime.timezone.utc),
                )

                e.set_author(
                    name=disc_user.name + "'s Assets",
                    icon_url=disc_user.display_avatar.url,
                )

                # Divide it per exchange
                binance = assets.loc[assets["exchange"] == "binance"]
                kucoin = assets.loc[assets["exchange"] == "kucoin"]
                stocks = assets.loc[assets["exchange"] == "stock"]

                no_changes = []

                # Finally, format the embed before posting it
                if not binance.empty:
                    e, no_change = await self.format_exchange(
                        binance, "Binance", e, binance_worth, binance_coins
                    )
                    no_changes.append(no_change)

                if not kucoin.empty:
                    e, no_change = await self.format_exchange(
                        kucoin, "KuCoin", e, kucoin_worth, kucoin_coins
                    )
                    no_changes.append(no_change)

                if not stocks.empty:
                    e, no_change = await self.format_exchange(
                        stocks, "Stocks", e, stocks_worth, stocks_owned
                    )
                    no_changes.append(no_change)

                # If all in no_changes is True do not send the embed
                if all(no_changes):
                    return

                await channel.purge(limit=1)
                await channel.send(embed=e)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Assets(bot))
