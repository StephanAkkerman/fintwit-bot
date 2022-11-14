#!/usr/bin/env python3
# Python 3.8.11

##> Imports
# > Standard library
import os
import asyncio
import sys
import datetime

# Discord libraries
import discord
from discord.ext import commands

# Import local dependencies
from util.vars import config
from util.disc_util import get_guild, set_emoji

bot = commands.Bot(intents=discord.Intents.all())


@bot.event
async def on_ready() -> None:
    """This gets printed on boot up"""

    # Load the loops and listeners
    load_folder("loops")
    load_folder("listeners")

    guild = get_guild(bot)
    print(f"{bot.user} is connected to {guild.name} at {datetime.datetime.now()} \n")
    
    await set_emoji(guild)
    
    
def load_folder(foldername: str) -> None:
    """
    Loads all the cogs in the given folder.
    Only loads the cogs if the config allows it.

    Parameters
    ----------
    foldername: str
        The name of the folder to load the cogs from.

    Returns
    -------
    None
    """

    # Get enabled cogs
    enabled_cogs = []

    # Check each file in the folder
    for file in config[foldername.upper()]:
        # Check the contents of the file in the folder
        if config[foldername.upper()][file]:
            # If the file type is not a boolean, check if it is enabled
            if not type(config[foldername.upper()][file]) == bool:
                # Check if the ENABLED key exists
                if "ENABLED" in config[foldername.upper()][file]:
                    # Append if enabled == True
                    if config[foldername.upper()][file]["ENABLED"]:
                        enabled_cogs.append(file.lower() + ".py")
            else:
                # Append the file to enabled cogs, if its value is True
                if config[foldername.upper()][file]:
                    enabled_cogs.append(file.lower() + ".py")

    # Load all cogs
    print(f"Loading {foldername} ...")
    for filename in os.listdir(f"./src/cogs/{foldername}"):
        if filename.endswith(".py") and filename in enabled_cogs:
            try:
                # Do not start timeline if the -no_timeline argument is given
                if (
                    filename == "timeline.py"
                    and len(sys.argv) > 2
                    and sys.argv[2] == "-no_timeline"
                ):
                    continue

                # Overview.py has no setup function, but should be considered as a loop / cog
                if filename == "overview.py":
                    continue

                print("Loading:", filename)
                bot.load_extension(f"cogs.{foldername}.{filename[:-3]}")
            except discord.ExtensionAlreadyLoaded:
                pass
            except discord.ExtensionNotFound:
                print("Cog not found:", filename)
    print()


if __name__ == "__main__":

    # Start by loading the database
    bot.load_extension("util.db")

    # Load commands
    load_folder("commands")

    # Read the token from the config
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
