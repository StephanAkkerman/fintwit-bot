##> Imports
import asyncio
import json
import sys
import re

# > 3rd Party Dependencies
from tweepy.asynchronous import AsyncStream 

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from vars import config, consumer_key, consumer_secret, access_token, access_token_secret, api

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
        try:
            if as_json['user']['id'] in self.following_ids:
                
                #print(as_json["user"]["screen_name"])
                #print(as_json)
                #print()
                
                # Ignore replies to other pipo
                # Could instead try: ... or as_json['in_reply_to_user_id'] == as_json['user']['id']
                if as_json['in_reply_to_user_id'] is None or as_json['in_reply_to_user_id'] in self.following_ids:
                    
                    # If the full text is available, use that
                    if "extended_tweet" in as_json:
                        text = as_json["extended_tweet"]["full_text"]
                    else:
                        text = as_json["text"]
                        
                    # Get the user name
                    user = as_json["user"]["screen_name"]
                    
                    # Get other info
                    profile_pic = as_json["user"]["profile_image_url"]
                    
                    # Could also use ['id_sr'] instead
                    url = f"https://twitter.com/{user}/status/{as_json['id']}"
                    
                    # Ticker is saved under 'entities', 'symbols'
                    
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
                    if images != []:
                        # This also removes other links that are not https://t.co/
                        text = re.sub(r'http\S+', '', text)
                        
                    # Post the tweet containing the important info
                    await self.post_tweet(text, user, profile_pic, url, images)
                    
        except Exception as e:
            print(e)
            print(as_json)
            
    async def post_tweet(self, text, user, profile_pic, url, images):
                
        # Use 'media' 'url' as url
        # Use 'profile_image_url'' for thumbnail
        e = discord.Embed(
            url=url,
            description=text,
            color=0x00FFFF,
        )
        
        e.set_thumbnail(url=profile_pic)
        e.set_author(name=user, url=url)
        
        # Set image if an image is included in the tweet
        for media_url in images:
            e.set_image(url=media_url)
        
        await self.channel.send(embed=e)