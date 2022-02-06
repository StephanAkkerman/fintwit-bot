import sys

# > 3rd Party Dependencies
import yaml
import tweepy
import discord

# Read config.yaml content
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.full_load(f)

# Set variables
consumer_key = config["TWITTER"]["CONSUMER_KEY"]
consumer_secret = config["TWITTER"]["CONSUMER_SECRET"]
access_token = config["TWITTER"]["ACCESS_TOKEN_KEY"]
access_token_secret = config["TWITTER"]["ACCESS_TOKEN_SECRET"]

# Init API
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)

# Replace key by value
filter_dict = {"BITCOIN" : "BTC",
               "ETHEREUM" : "ETH",
               "SPX" : "^SPX",
               "ES_F" : "ES=F",
               "ES" : "ES=F",
               "DXY" : "DX-Y.NYB",
               "NQ" : "NQ=F",           
              }

# https://twitter.com/DeItaone
# https://twitter.com/FirstSquawk
# https://twitter.com/EPSGUID
# https://twitter.com/eWhispers
# Make sure to follow these accounts to get the tweets
news = ['DeItaone', 'FirstSquawk', 'EPSGUID', 'eWhispers']

def get_guild(bot):

    return discord.utils.get(
        bot.guilds,
        name=config["DEBUG"]["GUILD_NAME"]
        if len(sys.argv) > 1 and sys.argv[1] == "-test"
        else config["DISCORD"]["GUILD_NAME"],
    )


def get_channel(bot, channel_name):

    return discord.utils.get(
        bot.get_all_channels(),
        guild__name=config["DEBUG"]["GUILD_NAME"]
        if len(sys.argv) > 1 and sys.argv[1] == "-test"
        else config["DISCORD"]["GUILD_NAME"],
        name=channel_name,
    )


def get_emoji(bot, emoji):

    guild = get_guild(bot)
    return discord.utils.get(guild.emojis, name=emoji)
