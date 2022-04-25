# Standard libraries
import datetime

# > 3rd party dependencies
from pycoingecko import CoinGeckoAPI
import yahoo_fin.stock_info as si
import pandas as pd

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop
from util.formatting import human_format

# Local dependencies
from util.vars import config, get_json_data
from util.disc_util import get_channel
from util.afterhours import afterHours
from util.formatting import format_embed


class Trending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.coingecko.start()
        self.cmc.start()
        
        self.stocks.start()
                
    @loop(hours=12)
    async def cmc(self):
        cmc_data = await get_json_data("https://api.coinmarketcap.com/data-api/v3/topsearch/rank")
        
        # Convert to dataframe
        cmc_df = pd.DataFrame(cmc_data["data"]["cryptoTopSearchRanks"])
        
        # Only save [[symbol, price + pricechange, volume]]
        cmc_df = cmc_df[["symbol", "slug", "priceChange"]]
        
        # Rename symbol
        cmc_df.rename(columns={"symbol" : "Symbol"}, inplace=True)
        
        # Add website to symbol
        cmc_df["Website"] = "https://coinmarketcap.com/currencies/" + cmc_df["slug"]
        # Format the symbol
        cmc_df["Symbol"] = "[" + cmc_df["Symbol"] + "](" + cmc_df["Website"] + ")"
        
        # Get important information from priceChange dictionary
        cmc_df["Price"] = cmc_df["priceChange"].apply(lambda x: x["price"])
        cmc_df["% Change"] = cmc_df["priceChange"].apply(lambda x: x["priceChange24h"])
        cmc_df["Volume"] = cmc_df["priceChange"].apply(lambda x: x["volume24h"])
        
        print("Formatting embed")
        e = await format_embed(cmc_df, "Trending On CoinMarketCap", "coinmarketcap")

        print("Getting channel")
        channel = get_channel(self.bot, config["TRENDING"]["CRYPTO"]["CHANNEL"])

        await channel.send(embed=e)
        print("Send cmc embed")

    @loop(hours=12)
    async def coingecko(self):
        """Prints the top 7 trending cryptocurrencies in dedicated channel"""

        cg = CoinGeckoAPI()

        e = discord.Embed(
            title=f"Trending Crypto on CoinGecko",
            url="https://www.coingecko.com/en/discover",
            description="",
            color=0x8CC63F,
        )

        ticker = []
        prices = []
        price_changes = []
        vol = []

        for coin in cg.get_search_trending()["coins"]:
            coin_dict = cg.get_coin_by_id(coin["item"]["id"])

            website = f"https://coingecko.com/en/coins/{coin['item']['id']}"
            price = coin_dict["market_data"]["current_price"]["usd"]
            price_change = coin_dict["market_data"]["price_change_percentage_24h"]

            ticker.append(f"[{coin['item']['symbol']}]({website})")
            vol.append(coin_dict["market_data"]["total_volume"]["usd"])
            prices.append(price)
            price_changes.append(price_change)

        # Convert to dataframe
        df = pd.DataFrame(
            {
                "Symbol": ticker,
                "Price": prices,
                "% Change": price_changes,
                "Volume": vol,
            }
        )
        
        e = await format_embed(df, "Trending On CoinGecko", "coingecko")

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
        # active['Symbol'] = active['Symbol'].apply(lambda x: f"[{x}](https://finance.yahoo.com/quote/{x}/)")
        active["% Change"] = active["% Change"].apply(
            lambda x: f" (+{x}% 📈)" if x > 0 else f"({x}% 📉)"
        )
        active["Price"] = active["Price (Intraday)"].astype(str) + active["% Change"]
        active["Price"] = active["Price"].apply(lambda x: "$" + x)
        active["Volume"] = active["Volume"].apply(lambda x: "$" + human_format(x))

        ticker = "\n".join(active["Symbol"].tolist())
        prices = "\n".join(active["Price"].tolist())
        vol = "\n".join(active["Volume"].tolist())

        if len(ticker) > 1024 or len(prices) > 1024 or len(vol) > 1024:
            # Drop the last
            ticker = "\n".join(ticker[:1024].split("\n")[:-1])
            prices = "\n".join(prices[:1024].split("\n")[:-1])
            vol = "\n".join(vol[:1024].split("\n")[:-1])

        e.add_field(
            name="Coin", value=ticker, inline=True,
        )

        e.add_field(
            name="Price", value=prices, inline=True,
        )

        e.add_field(
            name="Volume", value=vol, inline=True,
        )

        e.set_footer(
            text=f"Today at {datetime.datetime.now().strftime('%H:%M')}",
            icon_url="https://s.yimg.com/cv/apiv2/myc/finance/Finance_icon_0919_250x252.png",
        )

        channel = get_channel(self.bot, config["TRENDING"]["STOCKS"]["CHANNEL"])

        await channel.send(embed=e)


def setup(bot):
    bot.add_cog(Trending(bot))
