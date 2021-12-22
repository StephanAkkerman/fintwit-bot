##> Imports
import asyncio

# > 3rd Party Dependencies
import tweepy
from tweepy.asynchronous import AsyncStream 

# > Discord dependencies
import discord
from discord.ext import commands

# Local dependencies
from config import config

class Timeline(commands.Cog):
    def __init__(self, bot):
        self.bot = bot    
        
        # Call start() to start the stream
        asyncio.create_task(self.start())
        
    async def start(self):
        printer = Streamer(config['TWITTER']['CONSUMER_KEY'],
                           config['TWITTER']['CONSUMER_SECRET'],
                           config['TWITTER']['ACCESS_TOKEN_KEY'],
                           config['TWITTER']['ACCESS_TOKEN_SECRET'])
                        
        await printer.filter(track=['Twitter'])

def setup(bot):
    bot.add_cog(Timeline(bot))

class Streamer(AsyncStream):
    
    async def on_status(self, status):
        print(status.id)
        
