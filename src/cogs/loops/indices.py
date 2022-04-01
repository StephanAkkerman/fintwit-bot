# Standard libraries
import datetime

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config
from util.disc_util import get_channel
from util.tv_data import get_tv_data
from util.afterhours import afterHours
from util.formatting import human_format

class Indices(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.crypto.start()
        self.stock.start()

    @loop(hours=12)
    async def crypto(self):
        e = discord.Embed(
            title=f"Crypto Indices",
            description="",
            color=0x131722,
        )
        
        e.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)
        
        crypto_indices = ['TOTAL', 'BTC.D',  'OTHERS.D', 'TOTALDEFI.D', 'USDT.D']
        
        ticker = []
        prices = []
        
        for index in crypto_indices:
            tv_data = get_tv_data(index, 'crypto')
            if tv_data == False:
                continue
            price, change, _, exchange = tv_data
            change = round(change, 2)
            change = f" (+{change}% 📈)" if change > 0 else f"({change}% 📉)"
            
            if index == 'TOTAL':
                price = f"{human_format(price)} {change}" 
            else:
                price = f"{round(price, 2)}% {change}"           

            ticker.append(f"[{index}](https://www.tradingview.com/symbols/{exchange}-{index}/)")
            prices.append(price)
                
        ticker = "\n".join(ticker)
        prices = "\n".join(prices)
       
        e.add_field(
            name="Index", value=ticker, inline=True,
        )

        e.add_field(
            name="Value", value=prices, inline=True,
        )

        e.set_footer(
            text=f"Today at {datetime.datetime.now().strftime('%H:%M')}",
            icon_url="https://s3.tradingview.com/userpics/6171439-Hlns_orig.png",
        )

        channel = get_channel(self.bot, config["INDEX"]["CRYPTO"]["CHANNEL"])

        await channel.send(embed=e)
        
    @loop(hours=2)
    async def stock(self):
        # Dont send if the market is closed
        if afterHours():
           return 
        
        e = discord.Embed(
            title=f"Stock Indices",
            description="",
            color=0x131722,
        )
        
        e.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)
        
        stock_indices = ['SPY', 'NDX', 'DXY', 'PCC', 'PCCE', 'US10Y', 'VIX']
        
        ticker = []
        prices = []
                
        for index in stock_indices:
            tv_data = get_tv_data(index, 'stock')
            if tv_data == False:
                continue
            price, change, _, exchange = tv_data
            change = round(change, 2)
            change = f" (+{change}% 📈)" if change > 0 else f"({change}% 📉)"
            
            if index in ['SPY', 'NDX']:
                price = f"${round(price, 2)} {change}"
            elif index == 'USD10Y':
                price = f"{round(price, 2)}% {change}"
            else:
                price = f"{round(price, 2)} {change}"
            
            ticker.append(f"[{index}](https://www.tradingview.com/symbols/{exchange}-{index}/)")
            prices.append(price)
                
        ticker = "\n".join(ticker)
        prices = "\n".join(prices)
       
        e.add_field(
            name="Index", value=ticker, inline=True,
        )

        e.add_field(
            name="Value", value=prices, inline=True,
        )

        e.set_footer(
            text=f"Today at {datetime.datetime.now().strftime('%H:%M')}",
            icon_url="https://s3.tradingview.com/userpics/6171439-Hlns_orig.png",
        )

        channel = get_channel(self.bot, config["INDEX"]["STOCKS"]["CHANNEL"])

        await channel.send(embed=e)
        
def setup(bot):
    bot.add_cog(Indices(bot))