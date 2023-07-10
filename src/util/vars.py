import sys
import json

# > 3rd Party Dependencies
import yaml
import aiohttp
import pandas as pd

# Read config.yaml content
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.full_load(f)

guild_name = (
    config["DEBUG"]["GUILD_NAME"]
    if len(sys.argv) > 1 and sys.argv[1] == "-test"
    else config["DISCORD"]["GUILD_NAME"]
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
    url: str, headers: dict = None, cookies: dict = None, text: bool = False
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
            async with session.get(url) as r:
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
            async with session.post(url, data=data) as r:
                return await r.json(content_type=None)
    except Exception as e:
        print(f"Error with POST request for {url}.", "Error:", e)

    return {}
