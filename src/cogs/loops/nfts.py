import datetime

import discord
import pandas as pd
from discord.ext import commands
from discord.ext.tasks import loop

from api.cmc import top_cmc, upcoming_cmc
from api.coingecko import cg
from api.opensea import get_opensea
from api.play2earn import p2e_games
from constants.config import config
from constants.logger import logger

# > Local
from constants.sources import data_sources
from util.disc import get_channel, loop_error_catcher
from util.formatting import format_change


class NFTS(commands.Cog):
    """
    This class contains the cog for posting the top NFTs.
    It can be configured in the config.yaml file under ["LOOPS"]["NFTS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["NFTS"]["ENABLED"]:
            if config["LOOPS"]["NFTS"]["TOP"]:
                self.top_channel = None
                self.top_nfts.start()

            if config["LOOPS"]["NFTS"]["UPCOMING"]:
                self.upcoming_channel = None
                self.upcoming_nfts.start()

            if config["LOOPS"]["NFTS"]["P2E"]:
                self.p2e_channel = None
                self.top_p2e.start()

        if config["LOOPS"]["TRENDING"]["NFTS"]:
            self.trending_channel = None
            self.trending_nfts.start()

    @loop(hours=1)
    @loop_error_catcher
    async def top_nfts(self):
        if self.top_channel is None:
            self.top_channel = await get_channel(
                self.bot,
                config["LOOPS"]["NFTS"]["TOP"]["CHANNEL"],
                config["CATEGORIES"]["NFTS"],
            )
        opensea_top = await get_opensea()
        cmc_top = await top_cmc()

        await self.top_channel.purge(limit=2)

        for df, name in [(opensea_top, "Opensea"), (cmc_top, "CoinMarketCap")]:
            if df.empty:
                logger.warn("No top NFTs found for " + name)
                return

            if "symbol" not in df.columns:
                return

            if name == "Opensea":
                url = "https://opensea.io/rankings"
                color = data_sources["opensea"]["color"]
                icon_url = data_sources["opensea"]["icon"]
            elif name == "CoinMarketCap":
                url = "https://coinmarketcap.com/nft/collections/"
                color = data_sources["coinmarketcap"]["color"]
                icon_url = data_sources["coinmarketcap"]["icon"]

            e = discord.Embed(
                title=f"Top {len(df)} {name} NFTs",
                url=url,
                description="",
                color=color,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )

            e.add_field(
                name="NFT",
                value="\n".join(df["symbol"].tolist()),
                inline=True,
            )

            e.add_field(
                name="Price",
                value="\n".join(df["price"].tolist()),
                inline=True,
            )

            e.add_field(
                name="Volume",
                value="\n".join(df["volume"].astype(str).tolist()),
                inline=True,
            )

            # Set empty text as footer, so we can see the icon
            e.set_footer(text="\u200b", icon_url=icon_url)

            await self.top_channel.send(embed=e)

    @loop(hours=1)
    @loop_error_catcher
    async def trending_nfts(self):
        if self.trending_channel is None:
            self.trending_channel = await get_channel(
                self.bot,
                config["LOOPS"]["TRENDING"]["CHANNEL"],
                config["CATEGORIES"]["NFTS"],
            )
        await self.trending_channel.purge(limit=2)

        await self.opensea_trending()
        await self.gc_trending()

    async def opensea_trending(self):
        trending = await get_opensea("trending")

        e = discord.Embed(
            title=f"{len(trending)} Trending OpenSea NFTs",
            url="https://opensea.io/rankings/trending",
            description="",
            color=data_sources["opensea"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        if "symbol" in trending.columns:
            e.add_field(
                name="NFT",
                value="\n".join(trending["symbol"].tolist()),
                inline=True,
            )

        if "price" in trending.columns:
            e.add_field(
                name="Price",
                value="\n".join(trending["price"].tolist()),
                inline=True,
            )

        if "volume" in trending.columns:
            e.add_field(
                name="Volume",
                value="\n".join(trending["volume"].astype(str).tolist()),
                inline=True,
            )

        e.set_footer(
            text="\u200b",
            icon_url=data_sources["opensea"]["icon"],
        )

        await self.trending_channel.send(embed=e)

    async def gc_trending(self):
        df = pd.DataFrame(cg.get_search_trending()["nfts"])

        # Add URL
        df["url"] = "https://www.coingecko.com/en/nft/" + df["id"]
        df["NFT"] = "[" + df["name"] + "]" + "(" + df["url"] + ")"

        df["price"] = (
            df["floor_price_in_native_currency"].round(3).astype(str)
            + " "
            + df["native_currency_symbol"].str.upper()
        )
        df["floor price increase"] = (
            df["floor_price_24h_percentage_change"].round().apply(format_change)
        )

        e = discord.Embed(
            title=f"{len(df)} Trending CoinGecko NFTs",
            url="https://www.coingecko.com/en/nft",
            description="",
            color=data_sources["coingecko"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        e.add_field(
            name="NFT",
            value="\n".join(df["NFT"].tolist()),
            inline=True,
        )

        e.add_field(
            name="Floor Price",
            value="\n".join(df["price"].tolist()),
            inline=True,
        )

        e.add_field(
            name="Floor Price Increase",
            value="\n".join(df["floor price increase"].tolist()),
            inline=True,
        )

        e.set_footer(
            text="\u200b",
            icon_url=data_sources["coingecko"]["icon"],
        )

        await self.trending_channel.send(embed=e)

    @loop(hours=1)
    @loop_error_catcher
    async def upcoming_nfts(self):
        if self.upcoming_channel is None:
            self.upcoming_channel = await get_channel(
                self.bot,
                config["LOOPS"]["NFTS"]["UPCOMING"]["CHANNEL"],
                config["CATEGORIES"]["NFTS"],
            )
        upcoming = await upcoming_cmc()

        if upcoming.empty:
            logger.warn("No upcoming NFTs found")
            return

        if "symbol" not in upcoming.columns:
            return

        upcoming = upcoming.head(10)

        e = discord.Embed(
            title=f"Top {len(upcoming)} Upcoming NFTs",
            url="https://coinmarketcap.com/nft/upcoming/",
            description="",
            color=data_sources["coinmarketcap"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        e.add_field(
            name="NFT",
            value="\n".join(upcoming["symbol"].tolist()),
            inline=True,
        )

        e.add_field(
            name="Price",
            value="\n".join(upcoming["price"].tolist()),
            inline=True,
        )

        e.add_field(
            name="Drop Type",
            value="\n".join(upcoming["dropType"].tolist()),
            inline=True,
        )
        e.set_footer(text="\u200b", icon_url=data_sources["coinmarketcap"]["icon"])

        await self.upcoming_channel.purge(limit=1)
        await self.upcoming_channel.send(embed=e)

    @loop(hours=1)
    @loop_error_catcher
    async def top_p2e(self):
        if self.p2e_channel is None:
            self.p2e_channel = await get_channel(
                self.bot,
                config["LOOPS"]["NFTS"]["P2E"]["CHANNEL"],
                config["CATEGORIES"]["NFTS"],
            )
        try:
            p2e = await p2e_games()
        except Exception as e:
            logger.error(f"Error fetching PlayToEarn data: {e}")
            return

        if p2e.empty:
            return

        url = "https://playtoearn.net/blockchaingames/All-Blockchain/All-Genre/All-Status/All-Device/NFT/nft-crypto-PlayToEarn/nft-required-FreeToPlay"

        e = discord.Embed(
            title=f"Top {len(p2e)} Blockchain Games",
            url=url,
            description="",
            color=data_sources["playtoearn"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        e.add_field(
            name="Game",
            value="\n".join(p2e["name"].tolist()),
            inline=True,
        )

        e.add_field(
            name="Social 24h",
            value="\n".join(p2e["social"].tolist()),
            inline=True,
        )

        e.add_field(
            name="Status",
            value="\n".join(p2e["status"].tolist()),
            inline=True,
        )

        e.set_footer(
            text="\u200b",
            icon_url=data_sources["playtoearn"]["icon"],
        )

        await self.p2e_channel.purge(limit=1)
        await self.p2e_channel.send(embed=e)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(NFTS(bot))
