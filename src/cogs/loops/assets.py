import asyncio

# > 3rd Party Dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop
import pandas as pd

# Local dependencies
from cogs.loops.exchange_data import Binance, KuCoin
from util.ticker import get_stock_info
from util.db import get_db, update_db
from util.disc_util import get_channel, get_user
from util.vars import config
from util.disc_util import get_guild
 
 
class Assets(commands.Cog):    
    def __init__(self, bot, db=get_db('portfolio')):
        self.bot = bot
        self.trades_channel = get_channel(self.bot, config["TRADES"]["CHANNEL"])  
        
        # Refresh assets
        asyncio.create_task(self.assets(db))
        
    async def assets(self, db):
        """ 
        Only do this function at startup and if a new portfolio has been added
        Checks the account balances of accounts saved in portfolio db, then updates the assets db
        Posts an overview of everyone's assets in their asset channel
        """
        
        if db.equals(get_db('portfolio')):
            # Drop all crypto assets
            old_db = get_db('assets')
            crypto_rows = old_db.index[old_db['exchange'] != 'stock'].tolist()
            assets_db = old_db.drop(index=crypto_rows)
        else:
            # Add it to the old assets db, since this call is for a specific person
            assets_db = get_db('assets')
            
        # Ensure that the db knows the right types
        assets_db = assets_db.astype({'asset':str, 'owned':float, 'exchange':str, 'id':'int64', 'user':str})
            
        if not db.empty:
            
            # Divide per exchange
            binance = db.loc[db['exchange'] == 'binance']
            kucoin = db.loc[db['exchange'] == 'kucoin']
            
            if not binance.empty:
                for _, row in binance.iterrows():
                    # Add this data to the assets.pkl database                    
                    assets_db = pd.concat([assets_db, await Binance(self.bot, row, None).get_data()], ignore_index=True)
                        
            if not kucoin.empty:
                for _, row in kucoin.iterrows():                    
                    assets_db = pd.concat([assets_db, await KuCoin(self.bot, row, None).get_data()], ignore_index=True)
                    
        # Sum values where assets and names are the same
        assets_db = assets_db.astype({'asset':'string', 'owned':'float64', 'exchange':'string', 'id':'int64', 'user':'string'})
                    
        # Update the assets db
        update_db(assets_db, 'assets')
        print("Updated assets database")
        
        self.post_assets.start()

    @loop(hours=12)
    async def post_assets(self):        
        assets_db = get_db('assets')
        guild = get_guild(self.bot)
        
        # Use the user name as channel
        names = assets_db['user'].unique()
            
        for name in names:
            channel_name = '🌟┃' + name.lower()
                        
            # If this channel does not exist make it
            channel = get_channel(self.bot, channel_name)
            if channel is None:
                channel = await guild.create_text_channel(channel_name)
                print(f"Created channel {channel_name}")
                
            # Get the data
            assets = assets_db.loc[assets_db['user'] == name]
            id = assets['id'].values[0]
            disc_user = self.bot.get_user(id)
            
            if disc_user == None:
                disc_user = await get_user(self.bot, id)
            
            if not assets.empty:
                e = discord.Embed(
                    title="",
                    description="",
                    color=0x1DA1F2,
                )

                e.set_author(name=disc_user.name + "'s Assets", icon_url=disc_user.avatar_url)
                
                # Divide it per exchange
                binance = assets.loc[assets['exchange'] == 'binance']
                kucoin = assets.loc[assets['exchange'] == 'kucoin']
                stocks = assets.loc[assets['exchange'] == 'stock']
                
                # Add the binance info
                if not binance.empty:
                    # Sort and clean the data
                    sorted_binance = binance.sort_values(by=['owned'], ascending=False)
                    sorted_binance = sorted_binance.round({'owned':3})
                    binance = sorted_binance.drop(sorted_binance[sorted_binance.owned == 0].index)
                                        
                    b_assets = "\n".join(binance['asset'].to_list())
                    b_owned_floats = binance['owned'].to_list()
                    b_owned = "\n".join(str(x) for x in b_owned_floats)
                    
                    if len(b_assets) > 1024:
                        b_assets = b_assets[:1024].split("\n")[:-1]
                        b_owned = "\n".join(b_owned.split("\n")[:len(b_assets)])
                        b_assets = "\n".join(b_assets)
                    elif len(b_owned) > 1024:
                        b_owned = b_owned[:1024].split("\n")[:-1]
                        b_assets = "\n".join(b_assets.split("\n")[:len(b_owned)])
                        b_owned = "\n".join(b_owned)
                    
                    usd_values = []
                    for sym in b_assets.split("\n"):
                        if sym != 'USDT':
                            usd_values.append(await Binance(self.bot, None, None).get_usd_price(sym))
                        else:
                            usd_values.append(1)

                    values = ['$'+str(round(x*y,2)) for x,y in zip(b_owned_floats, usd_values)]
                    values = "\n".join(values)
                    
                    e.add_field(name="Binance", value=b_assets, inline=True)
                    e.add_field(name="Quantity", value=b_owned, inline=True)
                    e.add_field(name="Worth", value=values, inline=True)
                
                if not kucoin.empty:
                    sorted_kucoin = kucoin.sort_values(by=['owned'], ascending=False)
                    sorted_kucoin = sorted_kucoin.round({'owned':3})
                    kucoin = sorted_kucoin.drop(sorted_kucoin[sorted_kucoin.owned == 0].index)
                    
                    k_assets = "\n".join(kucoin['asset'].to_list())
                    k_owned_floats = kucoin['owned'].to_list()
                    k_owned = "\n".join(str(x) for x in k_owned_floats)

                    if len(k_assets) > 1024:
                        k_assets = k_assets[:1024].split("\n")[:-1]
                        k_owned = "\n".join(k_owned.split("\n")[:len(k_assets)])
                        k_assets = "\n".join(k_assets)
                    elif len(k_owned) > 1024:
                        k_owned = k_owned[:1024].split("\n")[:-1]
                        k_assets = "\n".join(k_assets.split("\n")[:len(k_owned)])
                        k_owned = "\n".join(k_owned)
                    
                    usd_values = []
                    for sym in k_assets.split("\n"):
                        if sym != 'USDT':
                            usd_values.append(await KuCoin(self.bot, None, None).get_quote_price(sym+'-USDT'))
                        else:
                            usd_values.append(1)
                            
                    values = ['$'+str(round(x*y,2)) for x,y in zip(k_owned_floats, usd_values)]
                    values = "\n".join(values)
                    
                    e.add_field(name="Kucoin", value=k_assets, inline=True)
                    e.add_field(name="Quantity", value=k_owned, inline=True)
                    e.add_field(name="Worth", value=values, inline=True)
                    
                if not stocks.empty:
                    stocks = stocks.sort_values(by=['owned'], ascending=False)
                    
                    stocks_assets = "\n".join(stocks['asset'].to_list())
                    stocks_owned_floats = stocks['owned'].to_list()
                    stocks_owned = "\n".join(str(x) for x in stocks_owned_floats)

                    if len(stocks_assets) > 1024:
                        stocks_assets = stocks_assets[:1024].split("\n")[:-1]
                        stocks_owned = "\n".join(stocks_owned.split("\n")[:len(stocks_assets)])
                        stocks_assets = "\n".join(stocks_assets)
                    elif len(stocks_owned) > 1024:
                        stocks_owned = stocks_owned[:1024].split("\n")[:-1]
                        stocks_assets = "\n".join(stocks_assets.split("\n")[:len(stocks_owned)])
                        stocks_owned = "\n".join(stocks_owned)
                    
                    usd_values = []
                    for sym in stocks_assets.split("\n"):
                        # Check what the current price is
                        usd_values.append(get_stock_info(sym)[3][0])
                            
                    values = ['$'+str(round(x*y,2)) for x,y in zip(stocks_owned_floats, usd_values)]
                    values = "\n".join(values)
                    
                    e.add_field(name="Stocks", value=stocks_assets, inline=True)
                    e.add_field(name="Quantity", value=stocks_owned, inline=True)
                    e.add_field(name="Worth", value=values, inline=True)
                    
                await channel.send(embed=e)  
                
def setup(bot):
    bot.add_cog(Assets(bot))