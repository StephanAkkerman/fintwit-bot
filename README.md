# FinTwit-bot

![FinTwit-bot Banner](img/logo/fintwit-banner.png)

---

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Supported versions">
  <img src="https://img.shields.io/github/license/StephanAkkerman/Fintwit_Bot.svg?color=brightgreen" alt="License">
  <a href="https://github.com/psf/black"><img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code style: black"></a>
</p>

This is a Discord bot written in Python, this bot aims to provide an overview of the financial markets discussed on X / Twitter.
Not only data from Twitter is gathered, but other sources are used too, such as Reddit, Binance, Yahoo-Finance, TradingView, and many other related websites.
This bot was written with flexibility in mind, meaning that you can toggle on and off certain features without issues by using the config.yaml file. 

## Installation
```bash
# Clone this repository
git clone https://github.com/StephanAkkerman/fintwit-bot
# Install required packages
pip install -r requirements.txt
```

### Twitter Credentials
To access data from Twitter you need to following these steps:
- To be able to get data from Twitter you need to have an account first.
- After signing in go to your [Twitter Home page](https://twitter.com/home), here you can select either **For You** or **Following**. I suggest selecting **Following** as it makes it easier to manage the Tweets the bot will pull.
- Open DevTools (F12) and go to the Network tab.
- Locate **HomeLatestTimeline**, right click on it and press **Copy as cURL (bash)**.
- Create a new file in the root folder of this project named `curl.txt` and paste the contents there.

### Setup .env
If you open `example.env` you will find the lines that need to be filled in. Start by renaming `example.env` to `.env` so the bot will use this file for you credentials.

#### Creating a Discord bot
For the first part, you can watch this [video (watch until 2:20)](https://www.youtube.com/watch?v=Pbq7vPsHDtc).

Or follow these written instructions:
- Setup your own Discord bot, following this [written tutorial](https://realpython.com/how-to-make-a-discord-bot-python/) or this 
- Give the bot admin rights and all permissions possible, since this is the easiest way to set it up.
- Invite the bot to your server.

At last fill in the lines in the `example.env` file:
- Write your bot token behind `DISCORD_TOKEN:` (line 2)
- Write your server name behind `DISCORD_GUILD:` (line 3)

##### Adding custom emojis (Optional)
The bot uses custom emojis to recognize on which cryptocurrency exchange things can be bought. If you wish to use it, follow these steps:
- Locate the custom emoji pictures [here](https://github.com/StephanAkkerman/fintwit-bot/tree/main/img/emojis).
- Add them to your server ([instructions](https://support.discord.com/hc/en-us/articles/360036479811-Custom-Emojis)).
- You can add any exchange emoji, for instance, FTX, as long as the image is supported by Discord and the name is the same as the exchange.

#### Reddit API Credentials (Optional)
If you do not want to track data from Reddit, feel free to skip this step.
I suggest creating a new account for this too, if you feel uncomfortable leaving your username and password.
- Go to https://old.reddit.com/prefs/apps/ and select **script**.
- The name of the app is needed for `REDDIT_APP_NAME`, click on **make app**.
- This will give you the `REDDIT_PERSONAL_USE` and `REDDIT_SECRET` tokens.
- Finally, fill in your Reddit username and password for `REDDIT_USERNAME` and `REDDIT_PASSWORD`.

## Features
This bot was made with configurability in mind, meaning that every feature listed below can be turned on or off, and be changed easily. If you do not want a feature, just turn it off, all automation and listeners works for your custom roles and channels, so be sure to check out the settings in config_example.yaml and change them to your liking!

### Commands
The following commands can be found under `src/cogs/commands` where you view the Python code for it. These commands can be turned on or off, in the section `COMMANDS` in the config file.
- `/anayze`: Shows an overview of analyst ratings of the specified stock based on [bezinga.com](https://www.benzinga.com).
- `/earnings`: Shows the upcoming earnings data for the specified stock.
- `/(un)follow`: Follows a Twitter user, the bot will then track this user's tweets. Important: This does require setting up Twitter V1 API. If you do not want to do this or cannot get access to the V1 API, then disable this command in the config.
- `/help`: Custom help command, provides help for each command and will show a description for all available commands to you.
- `/portfolio (add, remove, show)`: Add, remove, or show your portfolio settings. Currently only support Binance API keys for tracking your portfolio.
- `/sentiment`: Shows the sentiment of the provided stock, based on [finviz.com](https://finviz.com) data. Uses NLTK's VADER to determine sentiment.
- `/stock (add, remove, show)`: Adds, remove, shows stocks that you want to manually add to your portfolio. This way you can track your stocks just like in Yahoo Finance.

### Automation
In the config file this is also called `LOOPS`, you can customize each channel that these automated messages will get send in. The code for these loops can be found under `src/cogs/loops`. Here is the list of all options that are configurable in the config file, each can be enabled and disabled. 
- Timeline: This is the most important part of the bot, this tracks the timeline of the bot in real-time using Tweepy's Twitter API. It is the core functionality of this bot. As you might have seen in the tweet embed example above, it shows the current price of the ticker in the tweet, it also provides the 4 hour and 1 day technical analysis (TA) provided by TradingVriew. In the config file you can enable / disable if you want to track tweets mentioning crypto, stocks, and forex. There is also the option to track users that publish financial news.
- Assets: This enables the assets overview channels of users that have specified their portfolio with the `/portfolio` command for Binance and `/stock` command for stocks. Each user will have their dedicated channel updating them about their current assets.
- Earnings_Overview: This enables the earnings channel that provides an overview of all earnings a week in advance.
- Events: This enables the overview of important EU and USA related events, which can be found on [investing.com](https://www.investing.com/economic-calendar/).
- Funding: This enables the overview of the top 15 coins with the lowest funding rate on Binance.
- Gainers: This enables the overview for the top 10 (Binance) best performing crypto and (Yahoo Finance) stock in the last 24 hours.
- Ideas: This enables the overview of the the top 10 TradingView ideas on the frontpages of crypto, stocks, and forex.
- Index: This enables the overview of the important indices for crypto, stocks, and forex.
- Liquidations: This enables the plot of total crypto liquidations, provided by [coinglass.com](https://www.coinglass.com/LiquidationData).
- Losers: This enables the overview for the top 10 (Binance) worst performing crypto and (Yahoo Finance) stock in the last 24 hours.
- New_Listings: This enables the alerts for new listings on Binance, Coinbase and KuCoin.
- NFTs: This enables the overview of the top 10 NFTs on [Opensea](https://opensea.io/rankings) and [CoinMarketCap](https://coinmarketcap.com/nft/collections/), the top 10 upcoming NFTs on [CoinMarketCap](https://coinmarketcap.com/nft/upcoming/), and the top blockchain games (Play2Earn games) on [playtoearn.net](https://playtoearn.net/blockchaingames/All-Blockchain/All-Genre/All-Status/All-Device/NFT/nft-crypto-PlayToEarn/nft-required-FreeToPlay).
- Overview: This is the second most important part of the bot, as it provides an overview of all the mentioned in tickers of the past 24 hours, per category.
- Reddit: This enables the posting of the hottest post of the [wallstreetbets subreddit](https://www.reddit.com/r/wallstreetbets/).
- StockTwits: This enables the overview of Trending, Most Active, and Most Watched tickers on [StockTwits](https://stocktwits.com/).
- Trending: This enables the overview of the trending crypto, NFTs, stocks.
- Trades: This enables the Binance websockets for streaming crypto trades of the users that have added their portfolio. It also mentions the stocks added by using the `/stock add` command and the stocks that have been sold when using `/stock remove`.
- Options: The enables the volume and spacs alerts, and an overview of stocks with the highest reported short interest.
- Yield: This enables the plot of the US and EU Yield Curve Rates.
- Selected Traders: This is an automatic feature, which is not specified in the config file. If you name a channel as a Twitter username that you are following, all their tweets will be posted in the dedicated channel as well.

### Listeners
This section is about the other type of automation, which is based on Discord events. 
- On Member Join: When a member joins your server they will get a private message from the bot, where it explains itself.
- On Reaction: If you react with 💸 under a post, it will get reposted in the dedicated highlights channel. If you react with 🐻, 🦆, or 🐂, it will add the tweet text and the sentiment classification to a .csv file. This file can then be used later for training or testing sentiment models.

### Discord Category and Channel Creation
Since there are multiple channels that are about the same topic, we need to put them in different categories so the bot knows where to find this channel. The categories are specified in the config file, feel free to change the names. Below you can find an example showing how we set up our Discord channel.

#### Example of Discord Categories and Channels
<details closed>
<summary>━━ 🔑 Information ━━</summary>

This is an optional category, where the github channel tracks the commits of this repo using the [GitHub webhook for Discord](https://gist.github.com/jagrosh/5b1761213e33fc5b54ec7f6379034a22).
* 🌐┃general
* 💻┃github
* ⌨┃commands

</details>
<details closed>
<summary>━━━ 🐦Twitter ━━━</summary>

* 📰┃news
* 📷┃images
* ❓┃other
* 💸┃highlights

</details>
<details closed>
<summary>━━━ 🎰 Crypto ━━━</summary>

* 📈┃charts
* 💬┃text
* 📊┃index
* 💡┃ideas
* 🔥┃trending
* 🚀┃gainers
* 💩┃losers
* 🏦┃funding
* 🆕┃listings
* 📰┃news
* 💸┃liquidations
* 🏆┃overview

</details>
<details closed>
<summary>━━━ 🐒 NFTs ━━━</summary>

* 🏆┃top
* 🔥┃trending
* 🌠┃upcoming
* 🎮┃p2e

</details>
<details closed>
<summary>━━━ 💵 Stocks ━━━</summary>

* 📈┃charts
* 💬┃text
* 📊┃index
* 💡┃ideas
* 🔥┃trending
* 🚀┃gainers
* 💩┃losers
* 📅┃earnings
* 🎤┃stocktwits
* 🏆┃overview

</details>
<details closed>
<summary>━━━🎯 Options ━━━</summary>

* 🏆┃overview
* 💣┃volume
* 💰┃spacs
* 📉┃shorts

</details>
<details closed>
<summary>━━━ 💱 Forex ━━━</summary>

* 📈┃charts
* 💬┃text
* 📊┃index
* 📣┃events
* 🏢┃yield

</details>
<details closed>
<summary>━━━ 👨 Users ━━━</summary>

* 💲┃trades

</details>
<details closed>
<summary>━━━ 👽 Reddit ━━━</summary>

* 🤑┃wallstreetbets

</details>
<details closed>
<summary>━━ Selected Traders ━━</summary>

This is also optional, but these are one of my favorite traders on Twitter.
* 🐺┃hsakatrades
* 🦁┃anbessa100
* 🔫┃cryptobullet1

</details>

## Contributors
![https://github.com/StephanAkkerman/FinTwit_Bot/graphs/contributors](https://contributors-img.firebaseapp.com/image?repo=StephanAkkerman/FinTwit_Bot)
