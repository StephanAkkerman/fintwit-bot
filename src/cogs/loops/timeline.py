##> Imports
# > Standard libraries
from __future__ import annotations
import asyncio
from typing import List
import datetime

# > 3rd Party Dependencies
from tweepy.asynchronous import AsyncStream

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import (
    config,
    consumer_key,
    consumer_secret,
    access_token,
    access_token_secret,
    api,
)
from util.disc_util import get_channel, tag_user
from util.tweet_util import format_tweet, add_financials


class Timeline(commands.Cog):
    """
    A class to stream tweets from the Twitter API.
    Necessary to inherit commands.Cog to use this class as a Discord cog.
    It can be enabled / disabled in the config under ["LOOPS"]["TIMELINE"].

    Methods
    -------
    start()
        Readies the custom Tweepy async stream and starts it.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        # Call start() to start the stream
        asyncio.create_task(self.start())

    async def start(self):
        """
        Builds the Streamer object, gets the users that we are following, and then starts the stream.
        """

        # These values are all imported from config.yaml
        printer = Streamer(
            consumer_key, consumer_secret, access_token, access_token_secret, self.bot
        )

        try:
            following = api.get_friend_ids()
            await printer.filter(follow=following)

        except Exception as e:
            print("Could not get following ids on startup. Error: ", e)

            # Wait 5 min and try again
            await asyncio.sleep(60 * 5)
            await self.start()


def setup(bot: commands.Bot) -> None:
    """
    This is a necessary method to make the cog loadable.

    Returns
    -------
    None
    """
    bot.add_cog(Timeline(bot))


class Streamer(AsyncStream):
    """
    The main Class of this project. This class is responsible for streaming tweets from the Twitter API.

    Methods
    -------
    all_txt_channels()
        Gets all the text channels as Discord object and the names of the channels.
    get_following_ids()
        Gets the Twitters IDs of the accounts that the bot is following.
    on_data(raw_data : str)
        This method is called whenever data is received from the stream.
    post_tweet(text, user, profile_pic, url, images, tickers, hashtags, retweeted_user)
        Formats the tweet and passes it to upload_tweet().
    upload_tweet(e, category, images, user, retweeted_user)
        Uploads the tweet to the correct channel.
    """

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        access_token: str,
        access_token_secret: str,
        bot: commands.Bot,
    ) -> None:

        # Init the parent class
        AsyncStream.__init__(
            self, consumer_key, consumer_secret, access_token, access_token_secret
        )

        # Set the bot for messages
        self.bot = bot

        # Set the channels
        if config["LOOPS"]["TIMELINE"]["STOCKS"]["ENABLED"]:
            self.stocks_charts_channel = get_channel(
                self.bot, config["LOOPS"]["TIMELINE"]["STOCKS"]["CHARTS_CHANNEL"]
            )
            self.stocks_text_channel = get_channel(
                self.bot, config["LOOPS"]["TIMELINE"]["STOCKS"]["TEXT_CHANNEL"]
            )

        if config["LOOPS"]["TIMELINE"]["CRYPTO"]["ENABLED"]:
            self.crypto_charts_channel = get_channel(
                self.bot, config["LOOPS"]["TIMELINE"]["CRYPTO"]["CHARTS_CHANNEL"]
            )
            self.crypto_text_channel = get_channel(
                self.bot, config["LOOPS"]["TIMELINE"]["CRYPTO"]["TEXT_CHANNEL"]
            )

        if config["LOOPS"]["TIMELINE"]["IMAGES"]["ENABLED"]:
            self.images_channel = get_channel(
                self.bot, config["LOOPS"]["TIMELINE"]["IMAGES"]["CHANNEL"]
            )
        if config["LOOPS"]["TIMELINE"]["OTHER"]["ENABLED"]:
            self.other_channel = get_channel(
                self.bot, config["LOOPS"]["TIMELINE"]["OTHER"]["CHANNEL"]
            )
        if config["LOOPS"]["TIMELINE"]["NEWS"]["ENABLED"]:
            self.news_channel = get_channel(
                self.bot, config["LOOPS"]["TIMELINE"]["NEWS"]["CHANNEL"]
            )

        # Get all text channels
        self.all_txt_channels.start()

        # Set following ids
        self.get_following_ids.start()

    @loop(minutes=60)
    async def all_txt_channels(self) -> None:
        """
        Gets all the text channels as Discord object and the names of the channels.

        Returns
        -------
        None
        """

        text_channel_list = []
        text_channel_names = []

        # Loop over all the text channels
        for server in self.bot.guilds:
            for channel in server.channels:
                if str(channel.type) == "text":
                    text_channel_list.append(channel)
                    text_channel_names.append(channel.name.split("┃")[1])

        # Set the class variables
        self.text_channels = text_channel_list
        self.text_channel_names = text_channel_names

    @loop(minutes=15)
    async def get_following_ids(self) -> None:
        """
        Gets and sets the Twitters IDs of the accounts that the bot is following.

        Returns
        -------
        None
        """
        try:
            self.following_ids = api.get_friend_ids()
        except Exception as e:
            print(e)
            print("Failed to get following ids")

    async def on_data(self, raw_data: str) -> None:
        """
        This method is called whenever data is received from the stream.
        The name of this method cannot be changed, since it is called by the Tweepy stream automatically.

        Parameters
        ----------
        raw_data : str
            The raw data received from the stream in json text format.

        Returns
        -------
        None
        """

        formatted_tweet = await format_tweet(raw_data, self.following_ids)

        if formatted_tweet == None:
            return
        else:
            await self.post_tweet(*formatted_tweet)

    async def post_tweet(
        self,
        text: str,
        user: str,
        profile_pic: str,
        url: str,
        images: List[str],
        tickers: List[str],
        hashtags: List[str],
        retweeted_user: str,
    ) -> None:
        """
        Pre-processing the tweet data before uploading it to the Discord channels.
        This function creates the embed object and tags the user after it is correctly uploaded.

        Parameters
        ----------
            text : str
                The text of the tweet.
            user : str
                The user that posted this tweet.
            profile_pic : str
                The url to the profile pic of the user.
            url : str
                The url to the tweet.
            images : list
                The images contained in this tweet.
            tickers : list
                The tickers contained in this tweet (i.e. $BTC).
            hashtags : list
                The hashtags contained in this tweet.
            retweeted_user : str
                The user that was retweeted by this tweet.

        Returns
        -------
        None
        """

        title = (
            f"{user} tweeted about {', '.join(tickers)}"
            if retweeted_user == None
            else f"{user} 🔁 {retweeted_user} about {', '.join(tickers)}"
        )

        # The max length of the title is 256 characters
        if len(title) > 256:
            title = title[:253] + "..."

        # Set the properties of the embed
        e = discord.Embed(
            title=title,
            url=url,
            description=text,
            color=0x1DA1F2,
            timestamp=datetime.datetime.utcnow(),
        )
        e.set_thumbnail(url=profile_pic)

        # Max 25 fields
        if len(tickers + hashtags) < 26:
            e, category = await add_financials(
                e, tickers, hashtags, text, user, self.bot
            )
        else:
            # If the tweet contains no tickers or hasthags, then it is not a financial tweet
            category = None

        # Set image if an image is included in the tweet
        if images:
            e.set_image(url=images[0])

        # Set the twitter icon as footer image
        e.set_footer(
            icon_url="https://abs.twimg.com/icons/apple-touch-icon-192x192.png",
        )

        # Upload the tweet to the Discord.
        succes = await self.upload_tweet(e, category, images, user, retweeted_user)

        # Tag the users that have this ticker in their portfolio
        if len(tickers + hashtags) > 0 and succes is not None:
            msg, channel = succes
            await tag_user(msg, channel, tickers + hashtags)

    async def upload_tweet(
        self,
        e: discord.Embed,
        category: str,
        images: List[str],
        user: str,
        retweeted_user: str,
    ) -> tuple[discord.Message, discord.TextChannel] | None:
        """
        Uploads tweet in the dedicated Discord channel.

        Parameters
        ----------
            e : discord.Embed
                The Tweet as a Discord embed object.
            category : str
                The category of the tweet, used to decide which Discord channel it should be uploaded to.
            images : list
                The images contained in this tweet.
            user : str
                The user that posted this tweet.
            retweeted_user : str
                The user that was retweeted by this tweet.

        Returns
        -------
        discord.Message
            The message that was uploaded to the Discord channel.
        discord.TextChannel
            The channel that the message was uploaded to.
        """

        # Default channel
        channel = self.other_channel

        # Check if there is a user specific channel
        # If there is a retweeted user check for both
        if retweeted_user and retweeted_user.lower() in self.text_channel_names:
            channel = self.text_channels[
                self.text_channel_names.index(retweeted_user.lower())
            ]
        elif user.lower() in self.text_channel_names:
            channel = self.text_channels[self.text_channel_names.index(user.lower())]

        elif user in config["LOOPS"]["TIMELINE"]["NEWS"]["FOLLOWING"]:
            channel = self.news_channel

        elif category == None and not images:
            channel = self.other_channel
        elif category == None and images:
            channel = self.images_channel

        # If we do not know what category it is, assume it is crypto
        elif category == "crypto" or category == "🤷‍♂️" and not images:
            channel = self.crypto_text_channel
        elif category == "crypto" or category == "🤷‍♂️" and images:
            channel = self.crypto_charts_channel

        elif category == "stocks" and not images:
            channel = self.stocks_text_channel
        else:
            channel = self.stocks_charts_channel

        try:
            msg = await channel.send(embed=e)

            # Send all the other images as a reply
            for i in range(len(images)):
                if i > 0:
                    await channel.send(reference=msg, content=images[i])

            # Do this for every message
            await msg.add_reaction("💸")

            if category != None:
                await msg.add_reaction("🐂")
                await msg.add_reaction("🦆")
                await msg.add_reaction("🐻")

            return msg, channel

        except Exception as error:
            print("Error posting tweet on timeline", error)
            return
