# Standard libraries
import datetime
import pandas as pd
import time
import asyncio

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, get_json_data
from util.disc_util import get_channel, tag_user
from util.afterhours import afterHours

class UW(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji_dict = {}

        self.channel =  get_channel(self.bot, config["UNUSUAL_WHALES"]["CHANNEL"])
        asyncio.create_task(self.set_emojis())

        self.alerts.start()
        
    async def set_emojis(self):
        # Use https://phx.unusualwhales.com/api/tags/all to get the emojis
        
        headers = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36"
                  }
        self.emoji_dict = await get_json_data("https://phx.unusualwhales.com/api/tags/all", headers)
        
    async def UW_data(self):
        # start_date and expiry_start_data depends on how often the function is called
        last_5_min = int((time.time() - (5 * 60)) * 1000)

        url = f"https://phx.unusualwhales.com/api/option_quotes?offset=0&sort=timestamp&search=&sector=&tag=&end_date=9999999999999&start_date={last_5_min}&expiry_start_date={last_5_min}&expiry_end_date=9999999999999&min_ask=0&max_ask=9999999999999&volume_direction=desc&expiry_direction=desc&alerted_direction=desc&oi_direction=desc&normal=true"

        headers = {"authorization": config["UNUSUAL_WHALES"]["TOKEN"],
                   "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36"
                   }
        
        return await get_json_data(url, headers)

    @loop(minutes=5)
    async def alerts(self):
        
        # Check if the market is open
        if afterHours():
            return

        df = pd.DataFrame(await self.UW_data())

        if df.empty:
            return
        
        # Format the dataframe
        df = df[['timestamp',
                 'id',
                 'ticker_symbol', 
                 'option_type', 
                 'strike_price', # Also named underlying
                 'expires_at', 
                 'stock_price', 
                 'bid', 
                 'ask',
                 'min_ask',
                 'max_ask',
                 'volume', 
                 'implied_volatility', 
                 'sector',  
                 'tags', 
                 'tier',
                 'is_recommended',
                 'open_interest',
                 ]]
        
        # For each ticker in the df send a message
        for _, row in df.iterrows():
            
            option_type = row['option_type'][0].upper()
            difference = (float(row['stock_price']) - float(row['strike_price'])) / float(row['strike_price']) * 100
            
            emojis = ""
            for tag in row['tags']:
                emojis += self.emoji_dict[tag]['emoji']
            
            # Create the embed
            e = discord.Embed(
                title=f"${row['ticker_symbol']} {row['expires_at']} {option_type} ${row['strike_price']}",
                url=f"https://unusualwhales.com/alerts/{row['id']}",
                description=f"""{emojis}
                Bid-Ask: ${row['bid']} - ${row['ask']}
                Interest: {row['open_interest']}
                Volume: {row['volume']}
                IV: {row['implied_volatility']}
                % Diff: {difference}
                Underlying: ${row['stock_price']}
                Sector: {row['sector']}
                Tier: {row['tier']}
                """,
                color=0xe40414 if option_type == 'P' else 0x3cc474,
                timestamp=datetime.datetime.utcnow(),
            )
            
            timestamp = row['timestamp'].split("T")[1].split('Z')[0]
        
            e.set_footer(
            text=f"Alerted at {timestamp}",
            icon_url="https://blog.unusualwhales.com/content/images/2021/08/logo.8f570f66-1.png",
            )
            
            msg = await self.channel.send(embed=e)
            
            tag_user(msg, self.channel, [row['ticker_symbol']])
                
def setup(bot):
    bot.add_cog(UW(bot))