import sys

import discord

# Local dependencies
from util.vars import config

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
