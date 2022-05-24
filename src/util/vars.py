# > 3rd Party Dependencies
import yaml
import aiohttp
import tweepy
import pandas as pd
from pycoingecko import CoinGeckoAPI

# Read config.yaml content
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.full_load(f)

# Set variables
consumer_key = config["TWITTER"]["CONSUMER_KEY"]
consumer_secret = config["TWITTER"]["CONSUMER_SECRET"]
access_token = config["TWITTER"]["ACCESS_TOKEN_KEY"]
access_token_secret = config["TWITTER"]["ACCESS_TOKEN_SECRET"]

# Init API
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)

# Replace key by value
filter_dict = {
    "BITCOIN": "BTC",
    "ETHEREUM": "ETH",
    "ES_F": "ES=F",
    "ES": "ES=F",
    "NQ": "NQ=F",
    "NQ_F": "NQ=F",
}

# Stable coins
stables = ["USDT", "USD", "BUSD", "DAI", "USDTPERP"]

# Saves all CoinGecko coins, maybe refresh this daily
cg = CoinGeckoAPI()
cg_coins = pd.DataFrame(cg.get_coins_list())
cg_coins["symbol"] = cg_coins["symbol"].str.upper()

# Simple function to get website json info
async def get_json_data(url: str, headers: dict = None, text: bool = False) -> dict:
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

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(
            url,
        ) as r:
            try:
                if text:
                    response = await r.text()
                else:
                    response = await r.json()
            except Exception as e:
                print(f"Error with get request for {url}.", "Error:", e)

            # Close the connection
            await session.close()

            return response


async def post_json_data(url: str, headers: dict = None) -> dict:
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

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(
            url,
        ) as r:
            try:
                response = await r.json()
            except Exception as e:
                print(f"Error with get request for {url}.", "Error:", e)

            # Close the connection
            await session.close()

            return response
