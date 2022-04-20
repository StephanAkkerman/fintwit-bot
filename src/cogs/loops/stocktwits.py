# > 3rd party dependencies
import aiohttp
import pandas as pd
import datetime

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config
from util.disc_util import get_channel

class StockTwits(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.stocktwits.start()

    async def stocktwits_data(self, keyword):
        # Keyword can be "ts", "m_day", "wl_ct_day"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.stocktwits.com/api/2/charts/" + keyword
            ) as r:
                response = await r.json()
                return response
            
    async def get_data(self, e, keyword):
        # Keyword can be "ts", "m_day", "wl_ct_day"
        data = await self.stocktwits_data(keyword)
        
        table = pd.DataFrame(data["table"][keyword])
        stocks = pd.DataFrame(data["stocks"]).T
        stocks["stock_id"] = stocks.index.astype(int)
        full_df = pd.merge(stocks, table, on="stock_id")
        full_df.sort_values(by="val", ascending=False, inplace=True)
        
        # Format % change
        full_df["change"] = full_df["change"].apply(
                lambda x: f" (+{round(x,2)}% 📈)" if x > 0 else f" ({round(x,2)}% 📉)"
            )
        
        # Format price
        full_df["price"] = full_df["price"].apply(lambda x: round(x,3))
        full_df['price'] = full_df['price'].astype(str) + full_df['change']
        
        # Show Symbol, Price + change, Score / Count
        if keyword == "ts":
            name = "Trending"
            val = "Score"
        elif keyword == "m_day":
            name = "Most Active"
            val = "Count"
        else:
            name = "Most Watched"
            val = "Count"
            
        # Set values as string
        full_df["val"] = full_df["val"].astype(str)
            
        # Get the values as string
        assets = "\n".join(full_df["symbol"].to_list())
        prices = "\n".join(full_df["price"].to_list())
        values = "\n".join(full_df["val"].to_list())
            
        e.add_field(name=name, value=assets, inline=True)
        e.add_field(name="Price", value=prices, inline=True)
        e.add_field(name=val, value=values, inline=True)
        
        return e
        
    @loop(hours=6)
    async def stocktwits(self):

        e = discord.Embed(
            title=f"StockTwits Rankings",
            url="https://stocktwits.com/rankings/trending",
            description="",
            color=0xFFFFFF,
        )
        
        e = await self.get_data(e, "ts")
        e = await self.get_data(e, "m_day")
        e = await self.get_data(e, "wl_ct_day")
        
        # Set datetime and binance icon
        e.set_footer(text=f"Today at {datetime.datetime.now().strftime('%H:%M')}",
                    icon_url="https://pbs.twimg.com/profile_images/1464337316965720069/bZ4-cEg3_400x400.jpg"
        )
        
        channel = get_channel(self.bot, config["STOCKTWITS"]["CHANNEL"])

        await channel.send(embed=e)

def setup(bot):
    bot.add_cog(StockTwits(bot))