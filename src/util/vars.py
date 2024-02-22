import sys
import os
import json

# > 3rd Party Dependencies
import yaml
import aiohttp
import pandas as pd

# Read config.yaml content
config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
with open(config_path, "r", encoding="utf-8") as f:
    config = yaml.full_load(f)

guild_name = (
    os.getenv("DEBUG_GUILD")
    if len(sys.argv) > 1 and sys.argv[1] == "-test"
    else os.getenv("DISCORD_GUILD")
)

# Replace key by value
filter_dict = {
    "BITCOIN": "BTC",
    "BTCD": "BTC.D",
    "ETHEREUM": "ETH",
    "ES_F": "ES=F",
    "ES": "ES=F",
    "NQ": "NQ=F",
    "NQ_F": "NQ=F",
    "CL_F": "CL=F",
    "APPL": "AAPL",
    "DEFI": "DEFIPERP",
    "NVIDIA": "NVDA",
}

icon_url = (
    "https://raw.githubusercontent.com/StephanAkkerman/fintwit-bot/main/img/icons/"
)
data_sources = {
    "twitter": {"color": 0x1DA1F2, "icon": icon_url + "twitter.png"},
    "yahoo": {"color": 0x720E9E, "icon": icon_url + "yahoo.png"},
    "binance": {"color": 0xF0B90B, "icon": icon_url + "binance.png"},
    "investing": {"color": 0xDC8F02, "icon": icon_url + "investing.png"},
    "coingecko": {"color": 0x8AC14B, "icon": icon_url + "coingecko.png"},
    "opensea": {"color": 0x3685DF, "icon": icon_url + "opensea.png"},
    "coinmarketcap": {"color": 0x0D3EFD, "icon": icon_url + "cmc.ico"},
    "playtoearn": {"color": 0x4792C9, "icon": icon_url + "playtoearn.png"},
    "tradingview": {"color": 0x131722, "icon": icon_url + "tradingview.png"},
    "coinglass": {"color": 0x000000, "icon": icon_url + "coinglass.png"},
    "kucoin": {"color": 0x24AE8F, "icon": icon_url + "kucoin.png"},
    "coinbase": {"color": 0x245CFC, "icon": icon_url + "coinbase.png"},
    "unusualwhales": {"color": 0x000000, "icon": icon_url + "unusualwhales.png"},
    "reddit": {"color": 0xFF3F18, "icon": icon_url + "reddit.png"},
    "nasdaqtrader": {"color": 0x0996C7, "icon": icon_url + "nasdaqtrader.png"},
    "stocktwits": {"color": 0xFFFFFF, "icon": icon_url + "stocktwits.png"},
    "cryptocraft": {"color": 0x634C7B, "icon": icon_url + "cryptocraft.png"},
}

# Stable coins
# Could update this on startup:
# https://www.binance.com/bapi/composite/v1/public/promo/cmc/cryptocurrency/category?id=604f2753ebccdd50cd175fc1&limit=10
# Get info stored in ["data"]["body"]["data"]["coins"] to get this list
stables = [
    "USDT",
    "USDC",
    "BUSD",
    "DAI",
    "FRAX",
    "TUSD",
    "USDP",
    "USDD",
    "USDN",
    "FEI",
    "USD",
    "USDTPERP",
    "EUR",
]

# Init global database vars
assets_db = None
portfolio_db = None
cg_db = None
tweets_db = None
options_db = None
latest_tweet_id = 0

# These variables save the TradingView tickers
stocks = None
crypto = None
forex = None
cfd = None

nasdaq_tickers = None

reddit_ids = pd.DataFrame()
ideas_ids = pd.DataFrame()
classified_tickers = pd.DataFrame()

custom_emojis = {}


async def get_json_data(
    url: str,
    headers: dict = None,
    cookies: dict = None,
    json_data: dict = None,
    text: bool = False,
) -> dict:
    """
    Asynchronous function to get JSON data from a website.

    Parameters
    ----------
    url : str
        The URL to get the data from.
    headers : dict, optional
        The headers send with the get request, by default None.

    Returns
    -------
    dict
        The response as a dict.
    """

    try:
        async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
            async with session.get(url, json=json_data) as r:
                if text:
                    return await r.text()
                else:
                    return await r.json()
    except aiohttp.ClientError as e:
        print(f"Error with get request for {url}.\nError: {e}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {url}.\nError: {e}")
    return {}


async def post_json_data(
    url: str,
    headers: dict = None,
    data: dict = None,
    json: dict = None,
) -> dict:
    """
    Asynchronous function to post JSON data from a website.

    Parameters
    ----------
    url : str
        The URL to get the data from.
    headers : dict, optional
        The headers send with the post request, by default None.

    Returns
    -------
    dict
        The response as a dict.
    """

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(url, data=data, json=json) as r:
                return await r.json(content_type=None)
    except Exception as e:
        print(f"Error with POST request for {url}.", "Error:", e)

    return {}
