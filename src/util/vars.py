import sys

# > 3rd Party Dependencies
import yaml
import aiohttp
import tweepy
import pandas as pd

# Read config.yaml content
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.full_load(f)

# Set variables
consumer_key = config["TWITTER"]["CONSUMER_KEY"]
consumer_secret = config["TWITTER"]["CONSUMER_SECRET"]
access_token = config["TWITTER"]["ACCESS_TOKEN_KEY"]
access_token_secret = config["TWITTER"]["ACCESS_TOKEN_SECRET"]
bearer_token = config["TWITTER"]["BEARER_TOKEN"]

# Init v1 API
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)

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

# These variables save the TradingView tickers
stocks = None
crypto = None
forex = None
cfd = None

nasdaq_tickers = None

reddit_ids = pd.DataFrame()
ideas_ids = pd.DataFrame()


def format_change(change: float) -> str:
    """
    Converts a float to a string with a plus sign if the float is positive, and a minus sign if the float is negative.

    Parameters
    ----------
    change : float
        The percentual change of an asset.

    Returns
    -------
    str
        The formatted change.
    """

    return f"+{change}% 📈" if change > 0 else f"{change}% 📉"


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
                response = {}

            # Close the connection
            await session.close()

            return response


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

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(url, data=data) as r:
            try:
                response = await r.json(content_type=None)
            except Exception as e:
                print(f"Error with POST request for {url}.", "Error:", e)
                response = {}

            # Close the connection
            await session.close()

            return response
