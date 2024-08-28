from __future__ import annotations

import datetime

import discord
from discord.ext import commands
from discord.ext.tasks import loop

from api.farside import get_etf_inflow
from api.fear_greed import get_feargread
from api.tradingview import tv
from constants.config import config
from constants.sources import data_sources
from constants.tradingview import crypto_indices, forex_indices, stock_indices
from util.afterhours import afterHours
from util.disc import get_channel, loop_error_catcher
from util.formatting import human_format


async def create_embed(title: str, indices: list, data_type: str) -> discord.Embed:
    e = discord.Embed(
        title=title,
        description="",
        color=data_sources["tradingview"]["color"],
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )

    ticker, prices, changes = [], [], []

    for index in indices:
        price, change, _, exchange, _ = await tv.get_tv_data(index, data_type)

        if price == 0:
            continue

        change = round(change, 2)
        change = f"+{change}% 📈" if change > 0 else f"{change}% 📉"

        # Special price formatting for crypto
        if data_type == "crypto" and index in ["TOTAL", "TOTAL2", "TOTAL3"]:
            price = f"{human_format(price)}"
        elif data_type == "stock" and index in ["SPY", "NDX"]:
            price = f"${round(price, 2)}"
        else:
            price = f"{round(price, 2)}"

        ticker.append(
            f"[{index}](https://www.tradingview.com/symbols/{exchange}-{index}/)"
        )
        prices.append(price)
        changes.append(change)

    # Handle special Fear & Greed index for crypto
    if data_type == "crypto":
        fear_greed_data = await get_feargread()
        if fear_greed_data is not None:
            value, change = fear_greed_data
            ticker.append(
                "[Fear&Greed](https://alternative.me/crypto/fear-and-greed-index/)"
            )
            prices.append(str(value))
            changes.append(change)

        # Add etf inflow
        for coin in ["BTC", "ETH"]:
            inflow = await get_etf_inflow(coin)
            ticker.append(f"{coin} ETF Inflow")
            prices.append(f"{inflow}M")
            changes.append("N/A")

    if not ticker or not prices or not changes:
        return None

    e.add_field(name="Index", value="\n".join(ticker), inline=True)
    e.add_field(name="Value", value="\n".join(prices), inline=True)
    e.add_field(name="% Change", value="\n".join(changes), inline=True)

    e.set_footer(text="\u200b", icon_url=data_sources["tradingview"]["icon"])
    return e


class Index(commands.Cog):
    """
    This class contains the cog for posting the crypto and stocks indices.
    It can be enabled / disabled in the config under ["LOOPS"]["INDEX"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["INDEX"]["CRYPTO"]["ENABLED"]:
            self.crypto_channel = None
            self.crypto_indices = [sym.split(":")[1] for sym in crypto_indices]
            self.crypto.start()

        if config["LOOPS"]["INDEX"]["STOCKS"]["ENABLED"]:
            self.stocks_channel = None
            self.stock_indices = [sym.split(":")[1] for sym in stock_indices] + [
                sym.split(":")[1] for sym in forex_indices
            ]
            self.forex_indices = [sym.split(":")[1] for sym in forex_indices]
            self.stocks.start()

    @loop(hours=1)
    @loop_error_catcher
    async def crypto(self) -> None:
        """
        This function will get the current prices of crypto indices on TradingView and the Fear and Greed index.
        It will then post the prices in the configured channel.

        Returns
        -------
        None
        """
        if self.crypto_channel is None:
            self.crypto_channel = await get_channel(
                self.bot,
                config["LOOPS"]["INDEX"]["CHANNEL"],
                config["CATEGORIES"]["CRYPTO"],
            )
        e = await create_embed("Crypto Indices", self.crypto_indices, "crypto")

        await self.crypto_channel.purge(limit=1)
        await self.crypto_channel.send(embed=e)

    @loop(hours=1)
    @loop_error_catcher
    async def stocks(self) -> None:
        """
        Posts the stock indices in the configured channel, only posts if the market is open.

        Returns
        -------
        None
        """
        if self.stocks_channel is None:
            self.stocks_channel = await get_channel(
                self.bot,
                config["LOOPS"]["INDEX"]["CHANNEL"],
                config["CATEGORIES"]["STOCKS"],
            )
        # Dont send if the market is closed
        if afterHours():
            return

        indices = self.stock_indices + self.forex_indices

        stock_e = await create_embed("Stock & Forex Indices", indices, "stock")

        await self.stocks_channel.purge(limit=1)
        await self.stocks_channel.send(embed=stock_e)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Index(bot))
