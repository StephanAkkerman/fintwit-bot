import os
import sys

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load the .env file before importing the rest of the bot
load_dotenv()

from constants.config import config
from constants.logger import logger
from util.disc import get_guild, set_emoji

bot = commands.Bot(intents=discord.Intents.all())


@bot.event
async def on_ready() -> None:
    """This gets logger.infoed on boot up"""

    # Load the loops and listeners
    load_folder("loops")
    load_folder("listeners")

    guild = get_guild(bot)
    logger.info(f"{bot.user} is connected to {guild.name}")

    await set_emoji(guild)


def is_cog_enabled(config_section, file):
    """
    Checks if a cog is enabled in the configuration.

    Parameters
    ----------
    config_section: dict
        The section of the config corresponding to the folder.
    file: str
        The name of the file to check.

    Returns
    -------
    bool
        True if the cog is enabled, False otherwise.
    """
    cog_config = config_section.get(file)
    if cog_config is None:
        return False
    if isinstance(cog_config, bool):
        return cog_config
    return cog_config.get("ENABLED", False)


def load_cog(filename, foldername):
    """
    Loads a single cog by filename.

    Parameters
    ----------
    filename: str
        The name of the file to load.
    foldername: str
        The name of the folder containing the cog.

    Returns
    -------
    None
    """
    try:
        logger.info(f"Loading: {filename}")
        bot.load_extension(f"cogs.{foldername}.{filename[:-3]}")
    except discord.ExtensionAlreadyLoaded:
        logger.debug(f"Extension already loaded: {filename}")
    except discord.ExtensionNotFound:
        logger.warning(f"Cog was not found: {filename}")
    except Exception as e:
        logger.error(f"Failed to load cog {filename}: {e}", exc_info=True)


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
    logger.info(f"Loading cogs from folder: {foldername}")
    folder_config = config.get(foldername.upper(), {})

    debug_mode = False
    if "-debug" in sys.argv:
        debug_mode = True
        debug_mode_type = config.get("DEBUG_MODE_TYPE", "include_only")
        debug_cogs = config.get("DEBUG_COGS", [])

    enabled_cogs = []

    if debug_mode:
        if debug_mode_type == "include_only":
            if isinstance(debug_cogs, list):
                enabled_cogs = [cog + ".py" for cog in debug_cogs]
            if isinstance(debug_cogs, str):
                enabled_cogs = [debug_cogs + ".py"]
        elif debug_mode_type == "exclude":
            if debug_cogs is None:
                enabled_cogs = [
                    file.lower() + ".py"
                    for file in folder_config
                    if is_cog_enabled(folder_config, file)
                ]
            else:
                enabled_cogs = [
                    file.lower() + ".py"
                    for file in folder_config
                    if is_cog_enabled(folder_config, file)
                    and file.lower() not in debug_cogs
                ]
    else:
        enabled_cogs = [
            file.lower() + ".py"
            for file in folder_config
            if is_cog_enabled(folder_config, file)
        ]

    # Load all enabled cogs
    for filename in os.listdir(f"./src/cogs/{foldername}"):
        if filename.endswith(".py") and filename in enabled_cogs:
            load_cog(filename, foldername)


def get_token():
    debug_mode = False
    if "-debug" in sys.argv:
        debug_mode = True

    if debug_mode:
        logger.info("DEBUG_MODE is enabled")
        logger.info(
            f"DEBUG_MODE_TYPE is set to: {config.get('DEBUG_MODE_TYPE', 'include_only')}"
        )

    # Read the token from the config
    token = os.getenv("DEBUG_TOKEN") if debug_mode else os.getenv("DISCORD_TOKEN")

    if not token:
        logger.critical("No Discord token found. Exiting...")
        sys.exit(1)

    return token


if __name__ == "__main__":
    # Start by loading the database
    bot.load_extension("util.db")

    # Ensure the all directories exist
    os.makedirs("logs", exist_ok=True)
    os.makedirs("temp", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    token = get_token()

    # Load commands first
    load_folder("commands")

    # Main event loop
    try:
        bot.run(token)
    except Exception as e:
        logger.critical(f"Bot crashed: {e}")
