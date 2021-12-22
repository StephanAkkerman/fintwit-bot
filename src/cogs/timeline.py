##> Imports
import asyncio
import json
import sys

# > 3rd Party Dependencies
import tweepy
from tweepy.asynchronous import AsyncStream 

# > Discord dependencies
import discord
from discord.ext import commands

# Local dependencies
from config import config

# Set variables
consumer_key = config['TWITTER']['CONSUMER_KEY']
consumer_secret = config['TWITTER']['CONSUMER_SECRET']
access_token = config['TWITTER']['ACCESS_TOKEN_KEY']
access_token_secret = config['TWITTER']['ACCESS_TOKEN_SECRET']

# Init API
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)

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
        
        # Set the channel
        self.channel = discord.utils.get(
                        self.bot.get_all_channels(),
                        guild__name=config["DEBUG"]["GUILD_NAME"]
                        if len(sys.argv) > 1 and sys.argv[1] == "-test"
                        else config["DISCORD"]["GUILD_NAME"],
                        name=config["TIMELINE"]["CHANNEL"],
                    )
    
    async def on_data(self, raw_data):
        as_json = json.loads(raw_data)
        
        user_id = as_json['user']['id']
        
        if user_id in api.get_friend_ids():
        
            try:
                text = as_json["extended_tweet"]["full_text"]
            except Exception:
                text = as_json["text"]
                
            user = as_json["user"]["screen_name"]
            
            # Get other info
            profile_pic = as_json["user"]["profile_image_url"]
            
            # Could also use ['id_sr'] instead
            url = f"https://twitter.com/{user}/status/{as_json['id']}"
                
            await self.post_tweet(text, user, profile_pic, url)
        
    async def post_tweet(self, text, user, profile_pic, url):
                
        # Use 'media' 'url' as url
        # Use 'profile_image_url'' for thumbnail
        e = discord.Embed(
            url=url,
            description=text,
            color=0x00FFFF,
        )
        
        e.set_thumbnail(url=profile_pic)
        e.set_author(name=user, url=url)
        
        await self.channel.send(embed=e)