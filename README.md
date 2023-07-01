# FinTwit_Bot
[![Python 3.10.6](https://img.shields.io/badge/python-3.10.6-blue.svg)](https://www.python.org/downloads/release/python-3106/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![MIT License](https://img.shields.io/github/license/StephanAkkerman/Fintwit_Bot.svg?color=brightgreen)](https://opensource.org/licenses/MIT)

---

This is a Discord bot written in Python, with the purpose of providing an overview of the financial markets discussed on Twitter.
The bot is able to distuingish multiple markets based on the tickers mentioned in the tweets and provides detailed information of the financial data discussed in a Tweet. Below you can view what this bot does with a financial tweet.
<details><summary>Tweet Embed</summary><img src="https://github.com/StephanAkkerman/FinTwit_Bot/blob/main/img/tweet_example.png" width="500" /></details>

## Important
To run this bot you need to host it yourself, meaning that you should have something that functions as a server. I use my Raspberry PI for this, but there are many other options available for hosting a Discord bot, such as virtual private servers provided by Google, Amazon, Microsoft, and more.

However, if you do not want to host the bot yourself feel free to join our server. It comes with multiple **premium features** which are not part of this GitHub repository. These features include:
- Sentiment analysis on all Tweets, using a state-of-the-art analysis model.
- Option alerts of unusual option activity.

If you would like to join our server, you can do by [donating](https://github.com/sponsors/StephanAkkerman) to this project or help by contributing something useful.

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

## Installation
### Dependencies
The required packages to run this code can be found in the `requirements.txt` file. To run this file, execute the following code block:
```
$ pip install -r requirements.txt 
```
Alternatively, you can install the required packages manually like this:
```
$ pip install <package>
```

### Making a Discord Bot
This part is about creating the Discord bot, setting up the basics, and inviting it to your server. For the first part you can watch this [video (watch until 2:20)](https://www.youtube.com/watch?v=Pbq7vPsHDtc).

Or follow these written instructions:
- Setup your own Discord bot, following this [written tutorial](https://realpython.com/how-to-make-a-discord-bot-python/) or this 
- Give the bot admin rights and all permissions possible, since this is the easiest way to set it up.
- Invite the bot to your server.

Then you need to add the custom emojis to the server (can be skipped).
- Download the custom emoji pictures [here](https://github.com/StephanAkkerman/FinTwit_Bot/tree/main/emojis).
- Add them to your server ([instructions](https://support.discord.com/hc/en-us/articles/360036479811-Custom-Emojis)).
- You can add any exchange emoji, for instance FTX, as long as the image is supported by Discord and the name is the same name as the exchange.

Last you need to fill in the important information in `config_example.yaml`, so the bot knows which server it should be connected to.
- Open `config_example.yaml` 
- Write your bot token behind `TOKEN:` (line 2)
- Write your server name behind `GUILD_NAME:` (line 3)

### Apply for Twitter Developer Account
- On Twitter's [Developer Portal](https://developer.twitter.com/en/portal/petition/essential/basic-info) you can sign up for a developer account. This is necessary for Tweepy's streaming API.
- Generate a bearer token through your apps Keys and Tokens tab under the [Twitter Developer Portal Projects & Apps page](https://developer.twitter.com/en/portal/projects-and-apps).
- Similarly, the simplest way to authenticate as your developer account is to generate an access token and access token secret through your apps Keys and Tokens tab under the [Twitter Developer Portal Projects & Apps page](https://developer.twitter.com/en/portal/projects-and-apps). You’ll also need the app’s API / consumer key and secret that can be found on that page.

Now you can fill in this information in the `TWITTER` section of `config_example.yaml`.
- Paste the consumer key and consumer secret on lines 7 and 8.
- Paste the bearer token on line 11.
- Past the acces token key and access token secret on line 12 and 13.

### Optional: Create Reddit App
This is necessary to scrape information off of Reddit, if you do not plan to use this functionality you can skip this step. Otherwise you can find all the instructions [here](https://github.com/reddit-archive/reddit/wiki/OAuth2-Quick-Start-Example#first-steps).
- Paste your Reddit username and password on lines 16 and 17.
- Paste your app name, personal use token, and secret key on lines 19 to 21.

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
