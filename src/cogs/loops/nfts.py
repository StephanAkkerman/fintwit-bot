## > Imports
# > Standard library
import re
import datetime
from requests_html import AsyncHTMLSession

# > Third party
import pandas as pd
from bs4 import BeautifulSoup

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# > Local
from util.vars import get_json_data, config
from util.disc_util import get_channel
from util.formatting import format_change

class NFTS(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["NFTS"]["ENABLED"]:
            self.top_channel = get_channel(
                self.bot,
                config["LOOPS"]["NFTS"]["TOP"],
                config["CATEGORIES"]["NFTS"],
            )
            
            self.trending_channel = get_channel(
                self.bot,
                config["LOOPS"]["NFTS"]["TRENDING"],
                config["CATEGORIES"]["NFTS"],
            )
            
            self.upcoming_channel = get_channel(
                self.bot,
                config["LOOPS"]["NFTS"]["UPCOMING"],
                config["CATEGORIES"]["NFTS"],
            )
            
            self.p2e_channel = get_channel(
                self.bot,
                config["LOOPS"]["NFTS"]["P2E"],
                config["CATEGORIES"]["NFTS"],
            )

            self.top_nfts.start()
            self.trending_nfts.start()
            self.upcoming_nfts.start()
            self.top_p2e.start()
            
    @loop(hours=1)
    async def top_nfts(self):
        opensea_top = await get_opensea()
        cmc_top = await top_cmc()
        
        await self.top_channel.purge(limit=2)
        
        for df, name in [(opensea_top, "Opensea"), (cmc_top, "CoinMarketCap")]:
            if name == "Opensea":
                url = "https://opensea.io/rankings"
                color = 0x3685df
                icon_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/2/26/OpenSea_icon.svg/2048px-OpenSea_icon.svg.png"
            elif name == "CoinMarketCap":
                url = "https://coinmarketcap.com/nft/collections/"
                color = 0x0D3EFD
                icon_url = "https://coinmarketcap.com/favicon.ico"
            
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
    async def trending_nfts(self):
        trending = await get_opensea("trending")
        
        e = discord.Embed(
            title=f"Top {len(trending)} Trending NFTs",
            url="https://opensea.io/rankings/trending",
            description="",
            color=0x3685df,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )        
        e.add_field(
            name="NFT",
            value="\n".join(trending["symbol"].tolist()),
            inline=True,
        )

        e.add_field(
            name="Price",
            value="\n".join(trending["price"].tolist()),
            inline=True,
        )

        e.add_field(
            name="Volume",
            value="\n".join(trending["volume"].astype(str).tolist()),
            inline=True,
        )
        
        e.set_footer(text="\u200b", icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/2/26/OpenSea_icon.svg/2048px-OpenSea_icon.svg.png")
        
        await self.trending_channel.purge(limit=1)
        await self.trending_channel.send(embed=e)
    
    @loop(hours=1)
    async def upcoming_nfts(self):
        upcoming = await upcoming_cmc()
        upcoming = upcoming.head(10)
        
        e = discord.Embed(
            title=f"Top {len(upcoming)} Upcoming NFTs",
            url="https://coinmarketcap.com/nft/upcoming/",
            description="",
            color=0x0D3EFD,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        e.set_footer(text="\u200b", icon_url="https://coinmarketcap.com/favicon.ico")
        
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
            name="Start Time",
            value="\n".join(upcoming["start_time"].astype(str).tolist()),
            inline=True,
        )
        
        await self.upcoming_channel.purge(limit=1)
        await self.upcoming_channel.send(embed=e)
    
    @loop(hours=1)
    async def top_p2e(self):
        p2e = await p2e_games()
        
        url = 'https://playtoearn.net/blockchaingames/All-Blockchain/All-Genre/All-Status/All-Device/NFT/nft-crypto-PlayToEarn/nft-required-FreeToPlay'

        e = discord.Embed(
            title=f"Top {len(p2e)} Blockchain Games",
            url=url,
            description="",
            color=0x4792c9,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        e.set_footer(text="\u200b", icon_url="https://playtoearn.net/apple-touch-icon.png")
        
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
        
        await self.p2e_channel.purge(limit=1)
        await self.p2e_channel.send(embed=e)
        
def setup(bot: commands.Bot) -> None:
    bot.add_cog(NFTS(bot))

async def get_opensea(url = ""):
    """
    _summary_

    Parameters
    ----------
    url : str, optional
        Can be either "trending" or empty, by default ""

    Returns
    -------
    _type_
        _description_
    """
    
    html_doc = await get_json_data(f"https://opensea.io/rankings/{url}", headers={'User-Agent': 'Mozilla/5.0'}, text=True)

    html_doc = html_doc[html_doc.find(':pageInfo"}},') + len(':pageInfo"}},'):]
    html_doc = html_doc[:html_doc.find(':edges:10')]

    rows = html_doc.split('"node":{')

    opensea_nfts = []

    for row in rows[1:]:
        
        nft_dict = {}
        
        name = re.search(r"\"name\":\"(.*?)\"", row).group(1)
        slug = re.search(r"\"slug\":\"(.*?)\"", row).group(1)
        price_data = re.findall(r"\"unit\":\"(.*?)\"", row)
        change = re.search(r"\"volumeChange\":(.*?),", row)
        symbol = re.search(r"\"symbol\":\"(.*?)\"", row).group(1)
        
        if len(price_data) == 2:
            floor_price = f"{round(float(price_data[0]),3)} {symbol}"
            volume = price_data[1]
        else:
            floor_price = "?"
            volume = price_data[0]
           
        volume = f"{int(float(volume))} {symbol}"
        change = float(change.group(1))*100
    
        if change != 0:
            if change > 1:
                change = int(change)
            else:
                change = round(change, 2)
            volume = f"{volume} ({format_change(change)})"
            
        nft_dict['symbol'] = f"[{name}](https://opensea.io/collection/{slug})"
        nft_dict['price'] = floor_price
        nft_dict['volume'] = volume
        
        opensea_nfts.append(nft_dict)
        
    return pd.DataFrame(opensea_nfts)

async def top_cmc():
    """
    Forked from: https://github.com/SaeidKalantari/coinmarketcap-nft-web-scraper/blob/3cca9844a835a08bab46988d3a787a8b9af093c6/NFTscrapper.py
    """
    nfts = []

    session = AsyncHTMLSession()
    r = await session.get("https://coinmarketcap.com/nft/collections/")
    rows = r.html.find('tbody tr')

    for row in rows:
        d = {}
        columns = row.find('td')
        
        if columns[1].find('div', first=True) is not None:
            
            url = columns[1].find('a', first=True)
            if url:
                url = url.attrs['href']
                
            name_and_net = columns[1].find('span')
            name = name_and_net[0].text.strip()
            volume_and_change = columns[2].text.split('\n\n')
            avg_price_and_change = columns[5].text.split('\n\n')
            change = avg_price_and_change[1].replace('%', '')
            
            if change != '-':
                price = f"{avg_price_and_change[0]} ({format_change(float(change))})"
            else:
                price = avg_price_and_change[0]
            
            d['symbol'] = f"[{name}]({url})"
            d['volume'] = volume_and_change[0]            
            d['price'] = price
            
            nfts.append(d)

    await session.close()
    return pd.DataFrame(nfts)

async def upcoming_cmc():
    nfts = []

    session = AsyncHTMLSession()
    r = await session.get("https://coinmarketcap.com/nft/upcoming/")
    rows = r.html.find('tbody tr')

    for row in rows:
        d = {}
        columns = row.find('td')
        
        if columns[0].find('div', first=True) is not None:
            name = columns[0].find('span', first=True).text
            url = columns[1].find('a')[2].attrs['href']
            start_time = columns[2].find('span', first=True).text
            sale_info = columns[3].find('span', first=True).text.split('Sale: ')

            d['symbol'] = f"[{name}]({url})"
            d['start_time'] = start_time
            d['price'] = sale_info[-1]
        
            nfts.append(d)
            
    await session.close()
    return pd.DataFrame(nfts)

async def p2e_games():
    URL = 'https://playtoearn.net/blockchaingames/All-Blockchain/All-Genre/All-Status/All-Device/NFT/nft-crypto-PlayToEarn/nft-required-FreeToPlay'

    html = await get_json_data(URL, text=True)
    soup = BeautifulSoup(html, 'html.parser')
    items = soup.find('table', class_='table table-bordered mainlist')

    p2e_games = []

    # Skip header + ad
    iterator = 2
    for item in items.find_all('div', class_='dapp_profilepic dapp_profilepic_list'):
        data = {}
        
        allItems = items.find_all('tr')
        allItems_td = allItems[iterator].find_all('td')
        
        name = allItems_td[2].find('div', class_='dapp_name').find_next('span').text
        url = allItems_td[2].find_next('a')['href']    
        status = allItems_td[6].get_text('title') 
        social_24h_change = allItems_td[10].find_all('span')
        social_24h = social_24h_change[0].text
        social_change = social_24h_change[1].text.replace('%', '')
        
        data['name'] = f"[{name}]({url})"
        data['status'] = status
        data['social'] = f"{social_24h} ({format_change(float(social_change))})"

        p2e_games.append(data)

        iterator += 1
        
        if iterator == 12:
            break
        
    return pd.DataFrame(p2e_games)