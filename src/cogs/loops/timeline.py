##> Imports
import asyncio
import json
import datetime
from traceback import format_exc

# > 3rd Party Dependencies
from tweepy.asynchronous import AsyncStream
import numpy as np

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from vars import (
    config,
    consumer_key,
    consumer_secret,
    access_token,
    access_token_secret,
    api,
    get_channel,
    get_emoji,
)
from sentimentanalyis import classify_sentiment
from ticker import classify_ticker


class Timeline(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Call start() to start the stream
        asyncio.create_task(self.start())

    async def start(self):
        printer = Streamer(
            consumer_key, consumer_secret, access_token, access_token_secret, self.bot
        )

        await printer.filter(follow=api.get_friend_ids())


def setup(bot):
    bot.add_cog(Timeline(bot))


class Streamer(AsyncStream):
    def __init__(
        self, consumer_key, consumer_secret, access_token, access_token_secret, bot
    ):

        # Init the parent class
        AsyncStream.__init__(
            self, consumer_key, consumer_secret, access_token, access_token_secret
        )

        # Set the bot for messages
        self.bot = bot

        # Set the channels
        self.timeline = get_channel(self.bot, config["TIMELINE"]["CHANNEL"])

        self.stocks_charts_channel = get_channel(
            self.bot, config["STOCKS"]["CHARTS_CHANNEL"]
        )
        self.stocks_text_channel = get_channel(
            self.bot, config["STOCKS"]["TEXT_CHANNEL"]
        )

        self.crypto_charts_channel = get_channel(
            self.bot, config["CRYPTO"]["CHARTS_CHANNEL"]
        )
        self.crypto_text_channel = get_channel(
            self.bot, config["CRYPTO"]["TEXT_CHANNEL"]
        )

        self.images_channel = get_channel(self.bot, config["IMAGES"]["CHANNEL"])
        self.other_channel = get_channel(self.bot, config["OTHER"]["CHANNEL"])
        
        self.unusual_whales = get_channel(self.bot, "🐳┃unusual_whales")
        
        # Replace key by value
        self.filter_dict = {"BITCOIN" : "BTC",
                            "ETHEREUM" : "ETH",
                            "SPX" : "^SPX",
                            "ES_F" : "ES=F",
                            "DXY" : "DX-Y.NYB"
                           }

        # Set following ids
        self.get_following_ids.start()

    @loop(minutes=15)
    async def get_following_ids(self):
        # Get user ids of people who we are following
        self.following_ids = api.get_friend_ids()

    async def on_data(self, raw_data):
        """
        This method is called whenever data is received from the stream.
        """

        # Convert the string json data to json object
        as_json = json.loads(raw_data)

        # Filter based on users we are following
        # Otherwise shows all tweets (including tweets of people who we are not following)
        if "user" in as_json:
            if as_json["user"]["id"] in self.following_ids:

                # Ignore replies to other pipo
                # Could instead try: ... or as_json['in_reply_to_user_id'] == as_json['user']['id']
                if (
                    as_json["in_reply_to_user_id"] is None
                    or as_json["in_reply_to_user_id"] in self.following_ids
                ):
                    #print(as_json)

                    # Get the user name
                    user = as_json["user"]["screen_name"]

                    # Get other info
                    profile_pic = as_json["user"]["profile_image_url"]

                    # Could also use ['id_sr'] instead
                    url = f"https://twitter.com/{user}/status/{as_json['id']}"

                    (
                        text,
                        tickers,
                        images,
                        retweeted_user,
                        hashtags,
                    ) = await self.get_tweet(as_json)

                    # Replace &amp;
                    text = text.replace("&amp;", "&")
                    text = text.replace("&gt;", ">")

                    # Post the tweet containing the important info
                    try:
                        await self.post_tweet(
                            text,
                            user,
                            profile_pic,
                            url,
                            images,
                            tickers,
                            hashtags,
                            retweeted_user,
                        )
                    except Exception as e:
                        print(
                            f"Error posting tweet of {user} at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
                        )
                        print(format_exc())

    async def post_tweet(
        self, text, user, profile_pic, url, images, tickers, hashtags, retweeted_user
    ):

        # Use 'media' 'url' as url
        # Use 'profile_image_url'' for thumbnail

        e = discord.Embed(
            title=f"{user} tweeted about {', '.join(tickers)}"
            if retweeted_user == None
            else f"{user} 🔁 {retweeted_user} about {', '.join(tickers)}",
            url=url,
            description=text,
            color=0x1DA1F2,
        )

        e.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)
        e.set_thumbnail(url=profile_pic)

        # In case multiple tickers get send
        crypto = 0
        stocks = 0

        # Get the unique values
        symbols = list(set(tickers + hashtags))

        for ticker in symbols:
            
            # Filter beforehand
            if ticker in self.filter_dict.keys():
                ticker = self.filter_dict[ticker]
                
                # Skip doubles (for instance $BTC and #Bitocin)
                if ticker in symbols:
                    continue

            volume, website, exchanges, price, change = classify_ticker(ticker)

            # Check if there is any volume
            if volume is None:

                # If it is a symbol, assume it is crypto (if no match could be found)
                if ticker in tickers:
                    e.add_field(name=f"${ticker}", value="Crypto?")
                    crypto += 1

                    # Go to next in symbols
                    print(
                        f"No crypto or stock match found for ${ticker} in {user}'s tweet at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    )
                    continue
                else:
                    continue

            title = f"${ticker}"

            # Determine if this is a crypto or stock
            if "coingecko" in website:
                crypto += 1
            if "yahoo" in website:
                stocks += 1

            # Format change
            if type(change) == list:
                if len(change) == 2:
                    for i in range(len(change)):
                        if i == 0:
                            description = (
                                f"[AH: ${price[i]} ({change[i]})]({website})\n"
                            )
                        else:
                            description += f"[${price[i]} ({change[i]})]({website})"
                else:
                    description = f"[${price[0]} ({change[0]})]({website})"

            else:
                description = f"[${price} ({change})]({website})"

                # Currently only adds emojis for crypto exchanges
                if "coingecko" in website:
                    if "Binance" in exchanges:
                        title = f"{title} {get_emoji(self.bot, 'binance')}"
                    if "KuCoin" in exchanges:
                        title = f"{title} {get_emoji(self.bot, 'kucoin')}"

            # Add the field with hyperlink
            e.add_field(name=title, value=description, inline=True)

        # If there are any tickers
        if tickers:
            sentiment = classify_sentiment(text)
            prediction = ("🐻 - Bearish", "🐂 - Bullish")[np.argmax(sentiment)]
            e.add_field(
                name="Sentiment",
                value=f"{prediction} ({round(max(sentiment*100),2)}%)",
                inline=True,
            )

        # Set image if an image is included in the tweet
        if images:
            e.set_image(url=images[0])

        e.set_footer(
            text=f"Today at {datetime.datetime.now().strftime('%H:%M')}",
            icon_url="https://abs.twimg.com/icons/apple-touch-icon-192x192.png",
        )
        
        category = None
        if crypto >= stocks:
            category = "crypto"
        elif crypto < stocks:
            category = "stocks"            
        
        await self.upload_tweet(e, category, images, user, retweeted_user)
        
    async def upload_tweet(self, e, category, images, user, retweeted_user):
        """ Upload tweet in the dedicated discord channel """
        
        if user == "unusual_whales" or retweeted_user == "unusual_whales":
            msg = await self.unusual_whales.send(embed=e)
        
        elif category == None and not images:
            msg = await self.other_channel.send(embed=e)
        elif category == None and images:
            msg = await self.images_channel.send(embed=e)
            
        elif category == "crypto" and not images:
            msg = await self.crypto_text_channel.send(embed=e)
        elif category == "crypto" and images:
            msg = await self.crypto_charts_channel.send(embed=e)
            
        elif category == "stocks" and not images:
            msg = await self.stocks_text_channel.send(embed=e)
        else:
            msg = await self.stocks_charts_channel.send(embed=e)
            
            # Send all the other images as a reply
            for i in range(len(images)):
                if i > 0:
                    await self.timeline.send(reference=msg, content=images[i])

        # Do this for every message
        await msg.add_reaction("💸")

        if category != None:
            await msg.add_reaction("🐂")
            await msg.add_reaction("🦆")
            await msg.add_reaction("🐻")
            
    async def get_tweet(self, as_json):
        """Returns the info of the tweet that was quote retweeted"""

        # Check for quote tweet (combine this with user's text)
        if "quoted_status" in as_json:

            # If it is a retweet change format
            if "retweeted_status" in as_json:
                (
                    user_text,
                    user_ticker_list,
                    user_image,
                    user_hashtags,
                ) = await self.standard_tweet_info(as_json["retweeted_status"])
            else:
                (
                    user_text,
                    user_ticker_list,
                    user_image,
                    user_hashtags,
                ) = await self.standard_tweet_info(as_json)

            retweeted_user = as_json['quoted_status']['user']['screen_name']

            text, ticker_list, image, hashtags = await self.standard_tweet_info(
                as_json["quoted_status"]
            )

            # Combine the information
            images = user_image + image
            ticker_list = user_ticker_list + ticker_list
            hashtags = user_hashtags + hashtags

            text = f"{user_text}\n\n[@{retweeted_user}](https://twitter.com/{retweeted_user}):\n{text}"

        # If retweeted check the extended tweet
        elif "retweeted_status" in as_json:

            text, ticker_list, images, hashtags = await self.standard_tweet_info(
                as_json["retweeted_status"]
            )
            retweeted_user = as_json["retweeted_status"]["user"]["screen_name"]

        else:
            text, ticker_list, images, hashtags = await self.standard_tweet_info(
                as_json
            )
            retweeted_user = None

        return text, ticker_list, images, retweeted_user, hashtags

    async def standard_tweet_info(self, as_json):
        """Returns the info of the tweet"""

        images = []

        # If the full text is available, use that
        if "extended_tweet" in as_json:
            text = as_json["extended_tweet"]["full_text"]
            ticker_list = as_json["extended_tweet"]["entities"]

            if "urls" in as_json["extended_tweet"]["entities"]:
                for url in as_json["extended_tweet"]["entities"]["urls"]:
                    text = text.replace(url["url"], url["expanded_url"])

            # Add the media, check extended entities first
            if "extended_entities" in as_json["extended_tweet"]:
                if "media" in as_json["extended_tweet"]["extended_entities"]:
                    for media in as_json["extended_tweet"]["extended_entities"][
                        "media"
                    ]:
                        images.append(media["media_url"])
                        text = text.replace(media["url"], "")

        # Not an extended tweet
        else:
            text = as_json["text"]
            ticker_list = as_json["entities"]

            if "urls" in as_json["entities"]:
                for url in as_json["entities"]["urls"]:
                    text = text.replace(url["url"], url["expanded_url"])

            if "media" in as_json["entities"]:
                for media in as_json["entities"]["media"]:
                    images.append(media["media_url"])
                    text = text.replace(media["url"], "")

        tickers = []
        hashtags = []
        # Process hashtags and tickers
        if "symbols" in ticker_list:
            for symbol in ticker_list["symbols"]:
                tickers.append(f"{symbol['text'].upper()}")
            # Also check the hashtags
            for symbol in ticker_list["hashtags"]:
                hashtags.append(f"{symbol['text'].upper()}")

        return text, tickers, images, hashtags
