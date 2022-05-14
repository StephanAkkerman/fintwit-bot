# Standard libraries
import sys
import threading

# Third party libraries
import discord
import pandas as pd

# Local dependencies
from util.vars import config
from util.db import get_db

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


async def get_user(bot, user_id):
    return await bot.fetch_user(user_id)


assets_db = pd.DataFrame()
def get_assets_db():
    global assets_db
    assets_db = get_db("assets")
    
    # Do this every hour
    threading.Timer(60*60, get_assets_db).start()
    
get_assets_db()

async def tag_user(msg, channel, tickers):
    # Get the stored db
    matching_users = assets_db[assets_db["asset"].isin(tickers)][
        "id"
    ].tolist()
    unique_users = list(set(matching_users))

    if unique_users:
        # Make it one message for all the users
        tagged_msg = " ".join([f'<@!{user}>' for user in unique_users])
        await channel.send(tagged_msg, reference=msg)