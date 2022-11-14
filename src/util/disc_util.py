# Standard libraries
from typing import Optional

# Discord dependencies
import discord
from discord.ext import commands

# Local dependencies
import util.vars
from util.vars import guild_name


def get_guild(bot: commands.Bot) -> discord.Guild:
    """
    Returns the guild / server the bot is currently connected to.

    Parameters
    ----------
    commands.Bot
        The bot object.

    Returns
    -------
    discord.Guild
        The guild / server the bot is currently connected to.
    """

    return discord.utils.get(
        bot.guilds,
        # Return the debug server if -test is used as an argument
        name=guild_name,
    )


def get_channel(
    bot: commands.Bot, channel_name: str, category_name: str = None
) -> discord.TextChannel:
    """
    Returns the discord.TextChannel object of the channel with the given name.

    Parameters
    ----------
    bot : commands.Bot
        The bot object.
    channel_name : str
        The name of the channel.

    Returns
    -------
    discord.TextChannel
        The discord.TextChannel object of the channel with the given name.
    """

    for guild in bot.guilds:
        if guild.name == guild_name:
            for channel in guild.channels:
                if channel.name == channel_name:
                    if category_name is None:
                        return channel
                    else:
                        if channel.category.name == category_name:
                            return channel


async def set_emoji(guild) -> dict:
    """
    Returns the custom emoji with the given name.

    Parameters
    ----------
    bot : commands.Bot
        The bot object.
    emoji : str
        The name of the emoji.

    Returns
    -------
    discord.Emoji
        The custom emoji with the given name.
    """
    # https://docs.pycord.dev/en/stable/api.html?highlight=emojis#discord.on_guild_emojis_update
    # Could use this event to update the emojis if they change

    emojis = await guild.fetch_emojis()
    
    for emoji in emojis:
        util.vars.custom_emojis[emoji.name] = emoji	

async def get_user(bot: commands.Bot, user_id: int) -> discord.User:
    """
    Gets the discord.User object of the user with the given id.

    Parameters
    ----------
    bot : commands.Bot
        The bot object.
    user_id : int
        The id of the user.

    Returns
    -------
    discord.User
        The discord.User object of the user with the given id.
    """

    return await bot.fetch_user(user_id)


def get_tagged_users(tickers: list) -> Optional[str]:
    """
    Tags the users with the tickers in their portfolio that are mentioned in the message.

    Parameters
    ----------
    tickers : list
        The list of tickers mentioned in the message.

    Returns
    -------
    Optional[str]
        The message of the users that need to be tagged.
    """

    # Get the stored db
    if not util.vars.assets_db.empty:
        matching_users = util.vars.assets_db[util.vars.assets_db["asset"].isin(tickers)]["id"].dropna().tolist()
        unique_users = list(set(matching_users))

        if unique_users:
            # Make it one message for all the users
            return " ".join([f"<@!{user}>" for user in unique_users])


async def get_webhook(channel: discord.TextChannel) -> discord.Webhook:
    """
    Checks if there is a webhook in the given channel and returns it.
    If there is not a webhook for a channel, then it creates one.

    Parameters
    ----------
    channel : discord.TextChannel
        The channel to check for a webhook.

    Returns
    -------
    discord.Webhook
        The webhook for the given channel.
    """

    webhook = await channel.webhooks()

    if not webhook:
        webhook = await channel.create_webhook(name=channel.name)
        print(f"Created webhook for {channel.name}")
    else:
        webhook = webhook[0]

    return webhook
