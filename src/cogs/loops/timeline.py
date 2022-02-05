##> Imports
import asyncio
import datetime

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
    news
)

from tweet_util import format_tweet, add_financials

class Timeline(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Call start() to start the stream
        asyncio.create_task(self.start())

    async def start(self):
        printer = Streamer(
            consumer_key, consumer_secret, access_token, access_token_secret, self.bot
        )

        # https://codeofaninja.com/tools/find-twitter-id/
        # Get Twitter ID of accounts in vars.news
        news_ids = [11385742, 3295423333, 55395551]
        
        following = api.get_friend_ids() + news_ids
        
        await printer.filter(follow=following)    

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
        
        self.news_channel = get_channel(
            self.bot, "📰┃news"
        )
        
        # Get all text channels
        self.all_txt_channels.start()
        
        # Set following ids
        self.get_following_ids.start()
        

    @loop(minutes=60)
    async def all_txt_channels(self):
        text_channel_list = []
        text_channel_names = []
        for server in self.bot.guilds:
            for channel in server.channels:
                if str(channel.type) == 'text':
                    text_channel_list.append(channel)
                    text_channel_names.append(channel.name.split("┃")[1])
        
        self.text_channels = text_channel_list 
        self.text_channel_names = text_channel_names           

    @loop(minutes=15)
    async def get_following_ids(self):
        # Get user ids of people who we are following
        self.following_ids = api.get_friend_ids()

    async def on_data(self, raw_data):
        """
        This method is called whenever data is received from the stream.
        """
        formatted_tweet = await format_tweet(raw_data, self.following_ids)
        
        if formatted_tweet == None:
            return
        else:        
            await self.post_tweet(*formatted_tweet)

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

        if user.lower not in news:
            e, category = await add_financials(e, tickers, hashtags, text, user, self.bot)

        # Set image if an image is included in the tweet
        if images:
            e.set_image(url=images[0])

        e.set_footer(
            text=f"Today at {datetime.datetime.now().strftime('%H:%M')}",
            icon_url="https://abs.twimg.com/icons/apple-touch-icon-192x192.png",
        )           
        
        await self.upload_tweet(e, category, images, user, retweeted_user)
        
    async def upload_tweet(self, e, category, images, user, retweeted_user):
        """ Upload tweet in the dedicated discord channel """
        
        # Check if there is a user specific channel
        if user.lower() in self.text_channel_names or retweeted_user.lower() in self.text_channel_names:
            channel = self.text_channels[self.text_channel_names.index(user.lower())]
            
        if user.lower() in news:
            channel = self.news_channel
                    
        elif category == None and not images:
            channel = self.other_channel
        elif category == None and images:
            channel = self.images_channel
            
        elif category == "crypto" and not images:
            channel = self.crypto_text_channel
        elif category == "crypto" and images:
            channel = self.crypto_charts_channel
            
        elif category == "stocks" and not images:
            channel = self.stocks_text_channel
        else:
            channel = self.stocks_charts_channel
            
        msg = await channel.send(embed=e)
            
        # Send all the other images as a reply
        for i in range(len(images)):
            if i > 0:
                await channel.send(reference=msg, content=images[i])

        # Do this for every message
        await msg.add_reaction("💸")

        if category != None:
            await msg.add_reaction("🐂")
            await msg.add_reaction("🦆")
            await msg.add_reaction("🐻")
            