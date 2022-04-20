# > 3rd party dependencies
import yahoo_fin.stock_info as si
import aiohttp
import pandas as pd

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config
from util.disc_util import get_channel
from util.afterhours import afterHours
from util.formatting import format_embed
class Gainers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.stocks.start()
        self.crypto.start()
        
    async def binance_data(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.binance.com/api/v3/ticker/24hr"
            ) as r:
                response = await r.json()
                return response
        
    @loop(hours=2)
    async def crypto(self):
        binance_data = await self.binance_data()
        
        # If the call did not work
        if not binance_data:
            return
        
        # Cast to dataframe
        df = pd.DataFrame(binance_data)
        
        # Keep only the USDT pairs
        df = df[df['symbol'].str.contains('USDT')]
        
        # Remove USDT from the symbol
        df['symbol'] = df['symbol'].str.replace('USDT', '')
        
        df[["priceChangePercent", "weightedAvgPrice", "volume"]] = df[["priceChangePercent", "weightedAvgPrice", "volume"]].apply(pd.to_numeric)
        
        # Sort on priceChangePercent
        sorted = df.sort_values(by="priceChangePercent", ascending=False)
                        
        sorted.rename(columns={'symbol' : 'Symbol', 
                               'priceChangePercent' : '% Change', 
                               'weightedAvgPrice' : 'Price', 
                               'volume' : 'Volume'}, inplace=True)
                
        # Post the top 10 highest
        gainers = sorted.head(10)
                 
        # Post the top 10 lowest
        losers = sorted.tail(10)
        losers = losers.iloc[::-1]

        # Format the embed
        e_gainers = await format_embed(gainers, 'Gainers', 'binance')
        e_losers = await format_embed(losers, 'Losers', 'binance')
        
        gainers_channel = get_channel(self.bot, config["GAINERS"]["CRYPTO"]["CHANNEL"])
        losers_channel = get_channel(self.bot, config["LOSERS"]["CRYPTO"]["CHANNEL"])
        
        # Post the embed in the channel
        await gainers_channel.send(embed=e_gainers)
        await losers_channel.send(embed=e_losers)
        

    @loop(hours=2)
    async def stocks(self):

        # Dont send if the market is closed
        if afterHours():
            return

        e = discord.Embed(
            title=f"Top 50 Gainers",
            url="https://finance.yahoo.com/gainers/",
            description="",
            color=0x720E9E,
        )

        gainers = si.get_day_gainers()[
            ["Symbol", "Price (Intraday)", "% Change", "Volume"]
        ].head(50)

        gainers.rename(columns={'Price (Intraday)' : 'Price'}, inplace=True)
        
        e = await format_embed(gainers, 'Gainers', 'yahoo')

        channel = get_channel(self.bot, config["GAINERS"]["STOCKS"]["CHANNEL"])

        await channel.send(embed=e)


def setup(bot):
    bot.add_cog(Gainers(bot))
