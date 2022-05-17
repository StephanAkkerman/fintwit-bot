# Standard libraries
import datetime

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, get_json_data
from util.disc_util import get_channel
from util.tv_data import get_tv_data
from util.afterhours import afterHours
from util.formatting import human_format


class Index(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        if config["LOOPS"]["INDEX"]["CRYPTO"]["ENABLED"]:
            self.crypto.start()
            self.crypto_channel = get_channel(self.bot, config["LOOPS"]["INDEX"]["CRYPTO"]["CHANNEL"])
            
        if config["LOOPS"]["INDEX"]["STOCKS"]["ENABLED"]:
            self.stocks.start()
            self.stocks_channel = get_channel(self.bot, config["LOOPS"]["INDEX"]["STOCKS"]["CHANNEL"])

    async def get_feargread(self):
        response = await get_json_data("https://api.alternative.me/fng/?limit=2")

        if "data" in response.keys():
            today = int(response["data"][0]["value"])
            yesterday = int(response["data"][1]["value"])

            change = round((today - yesterday) / yesterday * 100, 2)
            change = f"+{change}% 📈" if change > 0 else f"{change}% 📉"

            return today, change

    @loop(hours=12)
    async def crypto(self):
        e = discord.Embed(title=f"Crypto Indices", 
                          description="",
                          color=0x131722,
                          timestamp = datetime.datetime.utcnow())

        crypto_indices = ["TOTAL", "BTC.D", "OTHERS.D", "TOTALDEFI.D", "USDT.D"]

        ticker = []
        prices = []
        changes = []

        for index in crypto_indices:
            tv_data = get_tv_data(index, "crypto")
            if tv_data == False:
                continue
            price, change, _, exchange = tv_data
            change = round(change, 2)
            change = f"+{change}% 📈" if change > 0 else f"{change}% 📉"

            if index == "TOTAL":
                price = f"{human_format(price)}"
            else:
                price = f"{round(price, 2)}%"

            ticker.append(
                f"[{index}](https://www.tradingview.com/symbols/{exchange}-{index}/)"
            )
            prices.append(price)
            changes.append(change)

        value, change = await self.get_feargread()

        if value:
            ticker.append(
                f"[Fear&Greed](https://alternative.me/crypto/fear-and-greed-index/)"
            )
            prices.append(str(value))
            changes.append(change)

        ticker = "\n".join(ticker)
        prices = "\n".join(prices)
        changes = "\n".join(changes)

        e.add_field(
            name="Index", value=ticker, inline=True,
        )

        e.add_field(
            name="Value", value=prices, inline=True,
        )

        e.add_field(
            name="% Change", value=changes, inline=True,
        )

        e.set_footer(
            icon_url="https://s3.tradingview.com/userpics/6171439-Hlns_orig.png",
        )
        
        await self.crypto_channel.send(embed=e)

    @loop(hours=2)
    async def stocks(self):
        # Dont send if the market is closed
        if afterHours():
            return

        e = discord.Embed(title=f"Stock Indices", 
                          description="", 
                          color=0x131722,
                          timestamp=datetime.datetime.utcnow())

        stock_indices = ["SPY", "NDX", "DXY", "PCC", "PCCE", "US10Y", "VIX"]

        ticker = []
        prices = []
        changes = []

        for index in stock_indices:
            tv_data = get_tv_data(index, "stock")
            if tv_data == False:
                continue
            price, change, _, exchange = tv_data
            change = round(change, 2)
            change = f"+{change}% 📈" if change > 0 else f"{change}% 📉"

            if index in ["SPY", "NDX"]:
                price = f"${round(price, 2)}"
            elif index == "USD10Y":
                price = f"{round(price, 2)}%"
            else:
                price = f"{round(price, 2)}"

            ticker.append(
                f"[{index}](https://www.tradingview.com/symbols/{exchange}-{index}/)"
            )
            prices.append(price)
            changes.append(change)

        ticker = "\n".join(ticker)
        prices = "\n".join(prices)
        changes = "\n".join(changes)

        e.add_field(
            name="Index", value=ticker, inline=True,
        )

        e.add_field(
            name="Value", value=prices, inline=True,
        )
        e.add_field(
            name="% Change", value=changes, inline=True,
        )

        e.set_footer(
            text=f"Today at {datetime.datetime.now().strftime('%H:%M')}",
            icon_url="https://s3.tradingview.com/userpics/6171439-Hlns_orig.png",
        )

        await self.stocks_channel.send(embed=e)


def setup(bot):
    bot.add_cog(Index(bot))