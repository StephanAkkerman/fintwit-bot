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
from util.yf_data import get_stock_info
from util.cg_data import get_coin_info
from util.db import update_db
from util.disc_util import get_channel, get_user
from util.vars import config
from util.disc_util import get_guild
from util.formatting import format_embed_length, format_change
from util.exchange_data import get_data

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

    async def usd_value(self, asset: str, exchange: str) -> tuple[float,str]:
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
        
        if exchange != "Stock":
            _, _, _, usd_val, change, _ = await get_coin_info(asset)
        else:
            _, _, _, usd_val, change, _ = await get_stock_info(asset)
            usd_val = usd_val[0]
            change = change[0]
            
        return usd_val, change

    async def assets(self, portfolio_db: pd.DataFrame) -> None:
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

        if portfolio_db.equals(util.vars.portfolio_db):
            # Drop all crypto assets
            old_db = util.vars.assets_db
            if not old_db.empty:
                crypto_rows = old_db.index[old_db["exchange"] != "stock"].tolist()
                
                assets_db = old_db.drop(index=crypto_rows)
            else:
                assets_db = pd.DataFrame(columns=['asset', 'buying_price', 'owned', 'exchange', 'id', 'user'])
        else:
            # Add it to the old assets db, since this call is for a specific person
            assets_db = util.vars.assets_db

        if not portfolio_db.empty:    
            for _, row in portfolio_db.iterrows():
                # Add this data to the assets.db database
                exch_data = await get_data(row)
                
                if exch_data.empty:
                    continue
                
                exch_data['id'] = row['id']
                exch_data['user'] = self.bot.get_user(row["id"])
                exch_data['user'] = exch_data['user'].apply(lambda x: x.name)
                
                # Ensure that the db knows the right types
                exch_data = exch_data.astype(
                    {"asset": str, "buying_price": float, "owned": float, "exchange": str, "id": "int64", "user": str}
                )
                assets_db = pd.concat([assets_db, exch_data], ignore_index=True) 
            
        # Ensure that the db knows the right types
        assets_db = assets_db.astype(
            {"asset": str, "buying_price": float, "owned": float, "exchange": str, "id": "int64", "user": str}
        )
            
        # Update the assets db    
        update_db(assets_db, "assets")
        util.vars.assets_db = assets_db

        self.post_assets.start()

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
        
        # Get the price of the assets
        prices = []
        changes = []
        for _, row in new_df.iterrows():
            price, change = await self.usd_value(row["asset"], exchange)
            
            if price is None:
                price = 0
            if change is None:
                change = 0
                
            prices.append(round(price,2))
            # Add without emoji
            changes.append(change)
            
        new_df["price"] = prices
        new_df["change"] = changes
                
        # Format price and change
        new_df["price_change"] = '$' + new_df["price"].astype(str) + ' (' + new_df["change"] + ')'
            
        # Calculate the most recent worth
        new_df["worth"] = prices * new_df["owned"]

        # Round it to 2 decimals
        new_df = new_df.round({"worth": 2})

        # Drop it if it's worth less than 1$
        new_df = new_df.drop(new_df[new_df.worth < 1].index)        
        
        # Calculate the increase in worth since the original buy
        new_df["worth_change"] = new_df["price"] - new_df["buying_price"]
        new_df["worth_change"] = new_df["worth_change"] / new_df["buying_price"] * 100
        new_df["worth_change"] = new_df["worth_change"].round(2)
        new_df["worth_change"] = new_df["worth_change"].apply(lambda x: format_change(x))

        # Sort by usd value
        new_df = new_df.sort_values(by=["worth"], ascending=False)

        new_df["worth"] = '$' + new_df["worth"].astype(str) + ' (' + new_df["worth_change"] + ')'

        # Create the list of string values
        assets = "\n".join(new_df["asset"].to_list())
        prices = "\n".join(new_df["price_change"].to_list())
        worth = "\n".join(new_df["worth"].to_list())

        # Ensure that the length is not bigger than allowed
        assets, prices, worth = format_embed_length([assets, prices, worth])
        
        # These are the new fields added to the embed
        e.add_field(name=exchange, value=assets, inline=True)
        e.add_field(name="Price", value=prices, inline=True)
        e.add_field(name="Worth", value=worth, inline=True)

        return e

    @loop(hours=1)
    async def post_assets(self) -> None:
        """
        Posts the assets of the users that added their portfolio.

        Returns
        -------
        None
        """

        # Use the user name as channel
        for name in util.vars.assets_db["user"].unique():
            # Get the assets of this user
            user_assets = util.vars.assets_db.loc[util.vars.assets_db["user"] == name]
            
            # Only post if there are assets
            if not user_assets.empty:
                
                # Get the Discord objects
                channel = await self.get_user_channel(name)
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
                for exchange in ["Binance","KuCoin","Stock"]:
                    exchange_df = user_assets.loc[user_assets["exchange"] == exchange.lower()]

                    if not exchange_df.empty:
                        e = await self.format_exchange(exchange_df, exchange, e)

                await channel.purge(limit=1)
                await channel.send(embed=e)
                
    async def get_user_channel(self, name:str) -> discord.TextChannel:
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

        if disc_user == None:
            try:
                disc_user = await get_user(self.bot, id)
            except Exception as e:
                print(f"Could not get user with id: {id}.\n{assets} \nError:", e)
            
        return disc_user

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Assets(bot))
