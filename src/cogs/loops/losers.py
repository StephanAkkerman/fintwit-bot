# Standard libraries
import datetime

# > 3rd party dependencies
import yahoo_fin.stock_info as si

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config
from util.disc_util import get_channel


class Losers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.losers.start()

    @loop(hours=12)
    async def losers(self):
        e = discord.Embed(
            title=f"Top 50 Losers",
            url="https://finance.yahoo.com/gainers/",
            description="",
            color=0x1DA1F2,
        )
        
        e.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)
        
        losers = si.get_day_losers()[['Symbol', 'Price (Intraday)', '% Change', 'Volume']].head(50)
        
        losers['% Change'] = losers['% Change'].apply(lambda x: f" (+{x}% 📈)" if x > 0 else f"({x}% 📉)")
        losers['Price'] = losers['Price (Intraday)'].astype(str) + losers['% Change']
        
        ticker = "\n".join(losers["Symbol"].tolist())
        prices = "\n".join(losers["Price"].tolist())
        vol = "\n".join(losers['Volume'].astype(int).astype(str).tolist())
       
        if len(ticker) > 1024 or len(prices) > 1024 or len(vol) > 1024:
            # Drop the last
            ticker = "\n".join(ticker[:1024].split("\n")[:-1])
            prices = "\n".join(prices[:1024].split("\n")[:-1])
            vol = "\n".join(vol[:1024].split("\n")[:-1])

        e.add_field(
            name="Coin", value=ticker, inline=True,
        )

        e.add_field(
            name="Price ($)", value=prices, inline=True,
        )

        e.add_field(
            name="Volume ($)", value=vol, inline=True,
        )

        e.set_footer(
            text=f"Today at {datetime.datetime.now().strftime('%H:%M')}",
            icon_url="https://s.yimg.com/cv/apiv2/myc/finance/Finance_icon_0919_250x252.png",
        )

        channel = get_channel(self.bot, config["LOSERS"]["CHANNEL"])

        await channel.send(embed=e)
        
def setup(bot):
    bot.add_cog(Losers(bot))