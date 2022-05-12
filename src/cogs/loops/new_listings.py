import asyncio

# > 3rd party dependencies
import aiohttp
import datetime

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config
from util.disc_util import get_channel

class Binance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.old_symbols = []

        asyncio.create_task(self.set_old_symbols())
        self.new_listings.start()
        
    async def set_old_symbols(self):
        # Get the exchange info
        self.old_symbols = await self.get_data()
                        
    async def get_data(self):
        async with aiohttp.ClientSession() as session:
            # https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#exchange-information
            async with session.get(
                "https://api.binance.com/api/v3/exchangeInfo"
            ) as r:
                response = await r.json()
                
                # Get the symbols
                symbols = [x["symbol"] for x in response["symbols"]]
                
                return symbols
                                
    @loop(hours=6)
    async def new_listings(self):
        
        # Check if there have been new listings
        new_symbols = await self.get_data()
        new_listings = []
        
        if self.old_symbols == []:
            await self.set_old_symbols()

        # If there is a new symbol, send a message
        if len(new_symbols) > len(self.old_symbols):
            new_listings = list(set(new_symbols) - set(self.old_symbols))
        
        # If symbols got removed do nothing
        if len(new_symbols) < len(self.old_symbols):            
            # Update old_symbols
            self.old_symbols = new_symbols      
            return
        
        # Update old_symbols
        self.old_symbols = new_symbols
                
        for ticker in new_listings:

            e = discord.Embed(
                title=f"Binance Lists {ticker}",
                url=f"https://www.binance.com/en/trade/{ticker}",
                description="",
                color=0xF0B90B,
            )
            
            # Set datetime and binance icon
            e.set_footer(text=f"Today at {datetime.datetime.now().strftime('%H:%M')}",
                        icon_url="https://public.bnbstatic.com/20190405/eb2349c3-b2f8-4a93-a286-8f86a62ea9d8.png"
            )
            
            channel = get_channel(self.bot, config["NEW_LISTINGS"]["CHANNEL"])

            await channel.send(embed=e)
            
class KuCoin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.old_symbols = []

        asyncio.create_task(self.set_old_symbols())
        self.new_listings.start()
        
    async def set_old_symbols(self):
        # Get the exchange info
        self.old_symbols = await self.get_data()        
            
    async def get_data(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.kucoin.com/api/v1/symbols"
            ) as r:
                response = await r.json()
                
                # Get the symbols
                symbols = [x["symbol"] for x in response["data"]]
                
                return symbols
                    
    @loop(hours=6)
    async def new_listings(self):
        
        # Check if there have been new listings
        new_symbols = await self.get_data()
        new_listings = []
        
        if self.old_symbols == []:
            await self.set_old_symbols()
                
        # If there is a new symbol, send a message
        if len(new_symbols) > len(self.old_symbols):
            new_listings = list(set(new_symbols) - set(self.old_symbols))
            print(new_listings)
        
        # If symbols got removed do nothing
        if len(new_symbols) < len(self.old_symbols):
            # Update old_symbols
            self.old_symbols = new_symbols      
            return
        
        # Update old_symbols
        self.old_symbols = new_symbols
                
        for ticker in new_listings:

            e = discord.Embed(
                title=f"KuCoin Lists {ticker}",
                url=f"https://www.kucoin.com/trade/{ticker}",
                description="",
                color=0x24AE8F,
            )
            
            # Set datetime and binance icon
            e.set_footer(text=f"Today at {datetime.datetime.now().strftime('%H:%M')}",
                        icon_url="https://yourcryptolibrary.com/wp-content/uploads/2021/12/Kucoin-exchange-logo-1.png"
            )
            
            channel = get_channel(self.bot, config["NEW_LISTINGS"]["CHANNEL"])

            await channel.send(embed=e)
        
class CoinBase(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.old_symbols = []

        asyncio.create_task(self.set_old_symbols())
        self.new_listings.start()
        
    async def set_old_symbols(self):
        # Get the exchange info
        self.old_symbols = await self.get_data()        
            
    async def get_data(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.exchange.coinbase.com/currencies"
            ) as r:
                response = await r.json()
                
                # Get the symbols
                symbols = [x["id"] for x in response]
                
                return symbols
                    
    @loop(hours=6)
    async def new_listings(self):
        
        # Check if there have been new listings
        new_symbols = await self.get_data()
        new_listings = []
        
        if self.old_symbols == []:
            await self.set_old_symbols()
                                
        # If there is a new symbol, send a message
        if len(new_symbols) > len(self.old_symbols):
            new_listings = list(set(new_symbols) - set(self.old_symbols))

        # If symbols got removed do nothing
        if len(new_symbols) < len(self.old_symbols):
            # Update old_symbols
            self.old_symbols = new_symbols      
            return
        
        # Update old_symbols
        self.old_symbols = new_symbols
                
        for ticker in new_listings:

            e = discord.Embed(
                title=f"CoinBase Lists {ticker}",
                url=f"https://pro.coinbase.com/trade/{ticker}",
                description="",
                color=0x0052ff,
            )
            
            # Set datetime and binance icon
            e.set_footer(text=f"Today at {datetime.datetime.now().strftime('%H:%M')}",
                        icon_url="https://pbs.twimg.com/profile_images/1484586799921909764/A9yYenz3.png"
            )
            
            channel = get_channel(self.bot, config["NEW_LISTINGS"]["CHANNEL"])

            await channel.send(embed=e)

def setup(bot):
    # This could be made nicer using a class for the functions and Binance and KuCoin inheriting that class
    bot.add_cog(Binance(bot))
    bot.add_cog(KuCoin(bot))
    bot.add_cog(CoinBase(bot))