# Standard libraries
import datetime

# > 3rd party dependencies
from pycoingecko import CoinGeckoAPI
import yahoo_fin.stock_info as si

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config
from util.disc_util import get_channel
from util.afterhours import afterHours


class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.crypto.start()
        self.stocks.start()

    @loop(hours=12)
    async def crypto(self):
        """Print the top 7 trending cryptocurrencies in dedicated channel"""

        cg = CoinGeckoAPI()

        e = discord.Embed(
            title=f"Trending Crypto",
            url="https://www.coingecko.com/en/discover",
            description="",
            color=0x8CC63F,
        )
        e.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)

        ticker = []
        prices = []
        vol = []

        for coin in cg.get_search_trending()["coins"]:
            coin_dict = cg.get_coin_by_id(coin["item"]["id"])

            website = f"https://coingecko.com/en/coins/{coin['item']['id']}"
            price = coin_dict["market_data"]["current_price"]["usd"]
            price_change = coin_dict["market_data"]["price_change_percentage_24h"]

            ticker.append(f"[{coin['item']['symbol']}]({website})")
            vol.append(str(coin_dict["market_data"]["total_volume"]["usd"]))

            if price_change != None:
                change = round(price_change, 2)
                price_change = f"(+{change}% 📈)" if change > 0 else f"({change}% 📉)"
                prices.append(f"{price} {price_change}")
            else:
                prices.append(price)

        e.add_field(
            name="Coin", value="\n".join(ticker), inline=True,
        )

        e.add_field(
            name="Price ($)", value="\n".join(prices), inline=True,
        )

        e.add_field(
            name="Volume ($)", value="\n".join(vol), inline=True,
        )

        e.set_footer(
            text=f"Today at {datetime.datetime.now().strftime('%H:%M')}",
            icon_url="https://static.coingecko.com/s/thumbnail-007177f3eca19695592f0b8b0eabbdae282b54154e1be912285c9034ea6cbaf2.png",
        )

        channel = get_channel(self.bot, config["TRENDING"]["CRYPTO"]["CHANNEL"])

        await channel.send(embed=e)

    @loop(hours=2)
    async def stocks(self):
        """Print the most activaly traded stocks in dedicated channel"""
        # Dont send if the market is closed
        if afterHours():
           return 

        e = discord.Embed(
            title=f"Trending Stocks",
            url="https://finance.yahoo.com/most-active/",
            description="",
            color=0x720E9E,
        )
        e.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)

        active = si.get_day_most_active().head(50)
        #active['Symbol'] = active['Symbol'].apply(lambda x: f"[{x}](https://finance.yahoo.com/quote/{x}/)")
        active['% Change'] = active['% Change'].apply(lambda x: f" (+{x}% 📈)" if x > 0 else f"({x}% 📉)")
        active['Price'] = active['Price (Intraday)'].astype(str) + active['% Change']
        
        ticker = "\n".join(active["Symbol"].tolist())
        prices = "\n".join(active["Price"].tolist())
        vol = "\n".join(active['Volume'].astype(int).astype(str).tolist())
       
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

        channel = get_channel(self.bot, config["TRENDING"]["STOCKS"]["CHANNEL"])

        await channel.send(embed=e)

def setup(bot):
    bot.add_cog(Trending(bot))
