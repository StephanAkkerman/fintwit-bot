#!/usr/bin/env python3
# Python 3.8.11

##> Imports
# > Standard library
import os
import asyncio
import sys

# Discord libraries
import discord
from discord.ext import commands

# Import local dependencies
from config import config

bot = commands.Bot(command_prefix=config["PREFIX"], intents=discord.Intents.all())
bot.remove_command("help")


@bot.event
async def on_ready():
    """This gets printed on boot up"""
    
    guild = discord.utils.get(
    bot.guilds,
    name=config["DEBUG"]["GUILD_NAME"]
    if len(sys.argv) > 1 and sys.argv[1] == "-test"
    else config["DISCORD"]["GUILD_NAME"],
    )

    # Load all loops
    load_folder(config, "cogs")

    print(f"{bot.user} is connected to {guild.name} (id: {guild.id}) \n")
    
    
def load_folder(config, foldername):

    # Load all commands
    print(f"Loading {foldername} ...")
    for filename in os.listdir(f"./src/{foldername}"):
        if filename.endswith(".py"):
            print("Loading:", filename)
            bot.load_extension(f"{foldername}.{filename[:-3]}")

    print()
    
if __name__ == "__main__":

    TOKEN = (
        config["DEBUG"]["TOKEN"]
        if len(sys.argv) > 1 and sys.argv[1] == "-test"
        else config["DISCORD"]["TOKEN"]
    )

    # Main event loop
    try:
        bot.loop.run_until_complete(bot.run(TOKEN))
    except KeyboardInterrupt:
        print("Caught interrupt signal.")
        print("exiting...")
        bot.loop.run_until_complete(
            asyncio.wait(
                [bot.change_presence(status=discord.Status.invisible), bot.logout()]
            )
        )
    finally:
        bot.loop.close()
        sys.exit(0)