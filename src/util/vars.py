import pandas as pd

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
