##> Imports
import asyncio
import json
import sys
import re
import datetime

# > 3rd Party Dependencies
from tweepy.asynchronous import AsyncStream 
import numpy as np

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop
from discord.enums import DefaultAvatar

# Local dependencies
from vars import config, consumer_key, consumer_secret, access_token, access_token_secret, api, get_channel, get_emoji
from sentimentanalyis import classify_sentiment
from ticker import classify_ticker

class Timeline(commands.Cog):
    def __init__(self, bot):
        self.bot = bot    
        
        # Call start() to start the stream
        asyncio.create_task(self.start())
        
    async def start(self):
        printer = Streamer(consumer_key, 
                           consumer_secret,
                           access_token,
                           access_token_secret,
                           self.bot)
                                                
        await printer.filter(follow = api.get_friend_ids())

def setup(bot):
    bot.add_cog(Timeline(bot))

class Streamer(AsyncStream):
    def __init__(self, consumer_key, consumer_secret, access_token, access_token_secret, bot):
        
        # Init the parent class
        AsyncStream.__init__(self, consumer_key, consumer_secret, access_token, access_token_secret)
        
        # Set the bot for messages
        self.bot = bot
        
        # Set the channels
        self.timeline = get_channel(self.bot,config["TIMELINE"]["CHANNEL"])
        
        self.stocks_charts_channel = get_channel(self.bot,config["STOCKS"]["CHARTS_CHANNEL"])
        self.stocks_text_channel = get_channel(self.bot,config["STOCKS"]["TEXT_CHANNEL"])
        
        self.crypto_charts_channel = get_channel(self.bot,config["CRYPTO"]["CHARTS_CHANNEL"])
        self.crypto_text_channel = get_channel(self.bot,config["CRYPTO"]["TEXT_CHANNEL"])
        
        self.other_channel = get_channel(self.bot,config["OTHER"]["CHANNEL"])
        
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
        if 'user' in as_json:
            if as_json['user']['id'] in self.following_ids:
                                
                # Ignore replies to other pipo
                # Could instead try: ... or as_json['in_reply_to_user_id'] == as_json['user']['id']
                if as_json['in_reply_to_user_id'] is None or as_json['in_reply_to_user_id'] in self.following_ids:
                    
                    # If the full text is available, use that
                    if "extended_tweet" in as_json:
                        text = as_json["extended_tweet"]["full_text"]
                    else:
                        text = as_json["text"]
                        
                    # If retweeted check the extended tweet
                    if "retweeted_status" in as_json:
                        if "extended_tweet" in as_json["retweeted_status"]:
                            text = as_json["retweeted_status"]["extended_tweet"]["full_text"]
                        
                    # Get the user name
                    user = as_json["user"]["screen_name"]
                    
                    # Get other info
                    profile_pic = as_json["user"]["profile_image_url"]
                    
                    # Could also use ['id_sr'] instead
                    url = f"https://twitter.com/{user}/status/{as_json['id']}"
                    
                    # Ticker is saved under 'entities', 'symbols'
                    tickers = []
                    if 'symbols' in as_json['entities']:
                        for symbol in as_json['entities']['symbols']:
                            tickers.append(f"{symbol['text'].upper()}")
                                                                    
                    # If the media_url is available send that      
                    images = []
                    
                    # First check for extended media
                    if "extended_entities" in as_json:
                        if "media" in as_json["extended_entities"]:
                            for media in as_json["extended_entities"]["media"]:
                                images.append(media["media_url"])
                        
                    else:
                        # Maybe check if extended_tweet is available
                        if "extended_tweet" in as_json:
                            if "media" in as_json["extended_tweet"]["entities"]:
                                for media in as_json["extended_tweet"]["entities"]["media"]:
                                    images.append(media["media_url"])
                        else:
                            if "media" in as_json["entities"]:
                                for media in as_json["entities"]["media"]:
                                    images.append(media["media_url"])
                        
                    # If there are images
                    if images:
                        # This also removes other links that are not https://t.co/
                        text = re.sub(r'http\S+', '', text)
                        
                    # Post the tweet containing the important info
                    await self.post_tweet(text, user, profile_pic, url, images, tickers)

            
    async def post_tweet(self, text, user, profile_pic, url, images, tickers):
                
        # Use 'media' 'url' as url
        # Use 'profile_image_url'' for thumbnail
        e = discord.Embed(
            title=f"{user} tweeted about {', '.join(tickers)}",
            url=url,
            description=text,
            color=0x1DA1F2,
        )
        
        e.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)
        e.set_thumbnail(url=profile_pic)
                
        # In case multiple tickers get send
        crypto = 0
        stocks = 0
        
        for ticker in tickers:
            volume, website, exchanges, price, change = classify_ticker(ticker)
            
            # Do this first           
            if volume is None:
                # Skip this one
                print(f"Skipping {ticker}")
                e.add_field(name=f"${ticker}")
                
                # Assume it is a crypto
                crypto += 1
                continue
            
            title = f"${ticker}"
            
            # Determine if this is a crypto or stock
            if 'coingecko' in website:
                crypto += 1
            if 'yahoo' in website:
                stocks += 1
        
            # Format change
            if change > 0:
                change = f"+{change}%"
            else:
                change = f"{change}%"

            description = f"[${price} ({change})]({website})"
            if 'Binance' in exchanges:
                title = f"{title} {get_emoji(self.bot, 'binance')}"
            if "KuCoin" in exchanges:
                title = f"{title} {get_emoji(self.bot, 'kucoin')}"

            # Add the field with hyperlink
            e.add_field(name=title, value=description, inline=True)

        # If there are any tickers
        if tickers:
            sentiment = classify_sentiment(text)
            prediction = ("🐻 - Bearish", "🐂 - Bullish")[np.argmax(sentiment)]
            e.add_field(name="Sentiment", value=f"{prediction} ({round(max(sentiment*100),2)}%)", inline=True)
        
        # Set image if an image is included in the tweet
        for media_url in images:
            e.set_image(url=media_url)
        
        e.timestamp = datetime.datetime.utcnow()

        if images:
            if crypto > stocks:
                await self.crypto_charts_channel.send(embed=e)
            elif crypto < stocks:
                await self.stocks_charts_channel.send(embed=e)
        else:
            if crypto > stocks:
                await self.crypto_text_channel.send(embed=e)
            elif crypto < stocks:
                await self.stocks_text_channel.send(embed=e)
            else:
                await self.other_channel.send(embed=e)
            
        # Send in the timeline channel
        await self.timeline.send(embed=e)