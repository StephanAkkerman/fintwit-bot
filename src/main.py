# Python 3.8.11
# Imports

# > 3rd Party Dependencies
import yaml
import twitter
from pycoingecko import CoinGeckoAPI

# Read config.yaml content
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.full_load(f)

# Twitter API:      https://python-twitter.readthedocs.io/en/latest/twitter.html
# https://developer.twitter.com/en/docs/twitter-api/v1/tweets/search/api-reference/get-search-tweets

# CoinGecko API:        https://github.com/man-c/pycoingecko & https://www.coingecko.com/api/documentations/v3
# Lynx API:             https://api.lynx.academy/
# Yahoo Finance API:    https://github.com/ranaroussi/yfinance

api = twitter.Api(
    config["TWITTER"]["CONSUMER_KEY"],
    config["TWITTER"]["CONSUMER_SECRET"],
    config["TWITTER"]["ACCES_TOKEN_KEY"],
    config["TWITTER"]["ACCES_TOKEN_SECRET"],
)

followingIDS = api.GetFriendIDs()

# Get the last 10 tweets of the following and convert them to text (excluding replies)
for id in followingIDS:
    for tweets in api.GetUserTimeline(user_id=id, count=10, exclude_replies=True):
        print(tweets.text)

# Create CoinGecko object
cg = CoinGeckoAPI()

# Create a list of the ticker names ("BTC", "DOGE", etc.)

coinList = cg.get_coins_list()
symbolList = []

for i in coinList:
    symbolList.append(i.get("symbol"))


# Search for ticker, if it exists it is a cryptocurrency
# if ('btc' in symbolList):
#    print ("ja")
