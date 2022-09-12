# Standard libraries
from __future__ import annotations
import datetime

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, get_json_data
from util.tv_data import tv
from util.disc_util import get_channel
from util.afterhours import afterHours
from util.formatting import human_format


class Index(commands.Cog):
    """
    This class contains the cog for posting the crypto and stocks indices.
    It can be enabled / disabled in the config under ["LOOPS"]["INDEX"].

    Methods
    -------
    get_feargread() -> tuple[int, str] | None:
        Gets the last 2 Fear and Greed indices from the API.
    crypto() -> None:
        This function will get the current prices of crypto indices on TradingView and the Fear and Greed index.
        It will then post the prices in the configured channel.
    stocks() -> None:
        Posts the stock indices in the configured channel, only posts if the market is open.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["INDEX"]["CRYPTO"]["ENABLED"]:
            self.crypto_channel = get_channel(
                self.bot, config["LOOPS"]["INDEX"]["CRYPTO"]["CHANNEL"]
            )
            self.crypto.start()

        if config["LOOPS"]["INDEX"]["STOCKS"]["ENABLED"]:
            self.stocks_channel = get_channel(
                self.bot, config["LOOPS"]["INDEX"]["STOCKS"]["CHANNEL"]
            )
            self.stocks.start()

    async def get_feargread(self) -> tuple[int, str] | None:
        """
        Gets the last 2 Fear and Greed indices from the API.

        Returns
        -------
        int
            Today's Fear and Greed index.
        str
            The percentual change compared to yesterday's Fear and Greed index.
        """

        response = await get_json_data("https://api.alternative.me/fng/?limit=2")

        if "data" in response.keys():
            today = int(response["data"][0]["value"])
            yesterday = int(response["data"][1]["value"])

            change = round((today - yesterday) / yesterday * 100, 2)
            change = f"+{change}% 📈" if change > 0 else f"{change}% 📉"

            return today, change

    @loop(hours=12)
    async def crypto(self) -> None:
        """
        This function will get the current prices of crypto indices on TradingView and the Fear and Greed index.
        It will then post the prices in the configured channel.

        Returns
        -------
        None
        """
        e = discord.Embed(
            title=f"Crypto Indices",
            description="",
            color=0x131722,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        crypto_indices = ["TOTAL", "BTC.D", "OTHERS.D", "TOTALDEFI.D", "USDT.D"]

        ticker = []
        prices = []
        changes = []

        for index in crypto_indices:
            tv_data = await tv.get_tv_data(index, "crypto")
            if tv_data == False:
                continue
            price, change, _, exchange, _ = tv_data
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

        succes = await self.get_feargread()

        if succes is not None:
            value, change = succes

            ticker.append(
                f"[Fear&Greed](https://alternative.me/crypto/fear-and-greed-index/)"
            )
            prices.append(str(value))
            changes.append(change)

        ticker = "\n".join(ticker)
        prices = "\n".join(prices)
        changes = "\n".join(changes)

        e.add_field(
            name="Index",
            value=ticker,
            inline=True,
        )

        e.add_field(
            name="Value",
            value=prices,
            inline=True,
        )

        e.add_field(
            name="% Change",
            value=changes,
            inline=True,
        )

        e.set_footer(
            text="\u200b",
            icon_url="https://s3.tradingview.com/userpics/6171439-Hlns_orig.png",
        )

        await self.crypto_channel.send(embed=e)

    @loop(hours=2)
    async def stocks(self) -> None:
        """
        Posts the stock indices in the configured channel, only posts if the market is open.

        Returns
        -------
        None
        """

        # Dont send if the market is closed
        if afterHours():
            return

        e = discord.Embed(
            title=f"Stock Indices",
            description="",
            color=0x131722,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        stock_indices = ["SPY", "NDX", "DXY", "PCC", "PCCE", "US10Y", "VIX"]

        ticker = []
        prices = []
        changes = []

        for index in stock_indices:
            tv_data = await tv.get_tv_data(index, "stock")
            if tv_data == False:
                continue
            price, change, _, exchange, _ = tv_data
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
            name="Index",
            value=ticker,
            inline=True,
        )

        e.add_field(
            name="Value",
            value=prices,
            inline=True,
        )
        e.add_field(
            name="% Change",
            value=changes,
            inline=True,
        )

        e.set_footer(
            text="\u200b",
            icon_url="https://s3.tradingview.com/userpics/6171439-Hlns_orig.png",
        )

        await self.stocks_channel.send(embed=e)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Index(bot))
