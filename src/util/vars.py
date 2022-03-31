# > 3rd Party Dependencies
import yaml
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
    "SPX": "^SPX",
    "ES_F": "ES=F",
    "ES": "ES=F",
    "DXY": "DX-Y.NYB",
    "NQ": "NQ=F",
    "NQ_F": "NQ=F",
}

# Stable coins
stables = ['USDT', 'USD', 'BUSD', 'DAI', 'USDTPERP']

# Saves all CoinGecko coins, maybe refresh this daily
cg = CoinGeckoAPI()
cg_coins = pd.DataFrame(cg.get_coins_list())
cg_coins["symbol"] = cg_coins["symbol"].str.upper()