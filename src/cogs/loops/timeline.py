##> Imports
# > Standard libraries
from __future__ import annotations
from typing import List
import traceback

# > 3rd Party Dependencies
import aiohttp

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config
from util.disc_util import get_channel, get_tagged_users, get_webhook
from util.tweet_embed import make_tweet_embed
from util.parse_tweet import parse_tweet
from util.get_tweet import get_tweet


class Timeline(commands.Cog):
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

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        charts_channel = config["LOOPS"]["TIMELINE"]["CHARTS_CHANNEL"]
        text_channel = config["LOOPS"]["TIMELINE"]["TEXT_CHANNEL"]

        # Set the channels
        if config["LOOPS"]["TIMELINE"]["STOCKS"]["ENABLED"]:
            self.stocks_charts_channel = get_channel(
                self.bot, charts_channel, config["CATEGORIES"]["STOCKS"]
            )
            self.stocks_text_channel = get_channel(
                self.bot, text_channel, config["CATEGORIES"]["STOCKS"]
            )

        if config["LOOPS"]["TIMELINE"]["CRYPTO"]["ENABLED"]:
            self.crypto_charts_channel = get_channel(
                self.bot, charts_channel, config["CATEGORIES"]["CRYPTO"]
            )
            self.crypto_text_channel = get_channel(
                self.bot, text_channel, config["CATEGORIES"]["CRYPTO"]
            )

        if config["LOOPS"]["TIMELINE"]["FOREX"]["ENABLED"]:
            self.forex_charts_channel = get_channel(
                self.bot, charts_channel, config["CATEGORIES"]["FOREX"]
            )
            self.forex_text_channel = get_channel(
                self.bot, text_channel, config["CATEGORIES"]["FOREX"]
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
                self.bot,
                config["LOOPS"]["TIMELINE"]["NEWS"]["CHANNEL"],
                config["CATEGORIES"]["TWITTER"],
            )

            if config["LOOPS"]["TIMELINE"]["NEWS"]["CRYPTO"]["ENABLED"]:
                self.crypto_news_channel = get_channel(
                    self.bot,
                    config["LOOPS"]["TIMELINE"]["NEWS"]["CHANNEL"],
                    config["CATEGORIES"]["CRYPTO"],
                )

        # Get all text channels
        self.all_txt_channels.start()

        self.get_latest_tweet.start()

    @loop(hours=1)
    async def all_txt_channels(self) -> None:
        """
        Gets all the text channels as Discord object and the names of the channels.

        Returns
        -------
        None
        """
        self.following_ids = []

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

    @loop(minutes=5)
    async def get_latest_tweet(self):
        print("Getting latest tweets")
        tweets = await get_tweet()
        last_tweet = len(tweets) - 1
        print(f"Got {last_tweet} tweets")

        # Loop from oldest to newest tweet
        for tweet in reversed(tweets):
            tweet = tweet["content"]

            # Skip if the tweet is not a timeline item
            if tweet["entryType"] != "TimelineTimelineItem":
                continue

            await self.on_data(tweet, update_tweet_id=True)

    async def on_data(self, tweet: dict, update_tweet_id: bool = False) -> None:
        """
        Parameters
        ----------
        raw_data : str
            The raw data received from the stream in json text format.

        Returns
        -------
        None
        """

        formatted_tweet = parse_tweet(tweet, update_tweet_id=update_tweet_id)

        if formatted_tweet == None:
            return
        else:
            (
                text,
                user_name,
                user_screen_name,
                user_img,
                tweet_url,
                media,
                tickers,
                hashtags,
                retweeted_user,
            ) = formatted_tweet

            e, category, base_symbols = await make_tweet_embed(
                text,
                user_name,
                user_screen_name,
                user_img,
                tweet_url,
                media,
                tickers,
                hashtags,
                retweeted_user,
                self.bot,
            )

            # Upload the tweet to the Discord.
            await self.upload_tweet(e, category, media, user_screen_name, base_symbols)

    async def upload_tweet(
        self,
        e: discord.Embed,
        category: str,
        media: List[str],
        user_screen_name: str,
        tickers: List[str],
    ) -> None:
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
            tickers : List[str]
                The list of tickers contained in this tweet.

        Returns
        -------
        None
        """

        user_channel = None

        # Default channel
        channel = self.other_channel

        # Check if there is a user specific channel
        if user_screen_name.lower() in self.text_channel_names:
            user_channel = self.text_channels[
                self.text_channel_names.index(user_screen_name.lower())
            ]

        # News posters (Do not post news in other channels)
        if user_screen_name in config["LOOPS"]["TIMELINE"]["NEWS"]["FOLLOWING"]:
            channel = self.news_channel
            await self.post_tweet(channel, e, media, tickers, user_channel, category)
            return

        if (
            user_screen_name
            in config["LOOPS"]["TIMELINE"]["NEWS"]["CRYPTO"]["FOLLOWING"]
        ):
            channel = self.crypto_news_channel
            await self.post_tweet(channel, e, media, tickers, user_channel, category)
            return

        # Tweets without financial information
        if category == None and not media:
            channel = self.other_channel
        if category == None and media:
            channel = self.images_channel

        # If we do not know what category it is, assume it is crypto
        if (category == "crypto" or category == "🤷‍♂️") and not media:
            channel = self.crypto_text_channel
        if (category == "crypto" or category == "🤷‍♂️") and media:
            channel = self.crypto_charts_channel

        # Stocks tweet channels
        if category == "stocks" and not media:
            channel = self.stocks_text_channel
        if category == "stocks" and media:
            channel = self.stocks_charts_channel

        # Forex tweet channels
        if category == "forex" and not media:
            channel = self.forex_text_channel
        if category == "forex" and media:
            channel = self.forex_charts_channel

        await self.post_tweet(channel, e, media, tickers, user_channel, category)

    async def make_and_send_webhook(self, channel, tickers, image_e):
        webhook = await get_webhook(channel)

        # Wait so we can use this message as reference
        msg = await webhook.send(
            content=get_tagged_users(tickers),
            embeds=image_e,
            username="FinTwit",
            wait=True,
            avatar_url=self.bot.user.avatar.url,
        )

        return msg

    async def post_tweet(self, channel, e, media, tickers, user_channel, category):
        msgs = []

        try:
            # Create a list of image embeds, max 10 images per post
            image_e = [e] + [
                discord.Embed(url=e.url).set_image(url=img) for img in media[1:10]
            ]

            # If there are multiple images to be sent, use a webhook to send them all at once
            if len(image_e) > 1:
                msg = await self.make_and_send_webhook(channel, tickers, image_e)
                msgs.append(msg)

                if user_channel:
                    msg = await self.make_and_send_webhook(
                        user_channel, tickers, image_e
                    )
                    msgs.append(msg)

            else:
                # Use the normal send function
                msg = await channel.send(content=get_tagged_users(tickers), embed=e)
                msgs.append(msg)

                if user_channel:
                    msg = await user_channel.send(
                        content=get_tagged_users(tickers), embed=e
                    )
                    msgs.append(msg)

            # Do this for every message
            try:
                for msg in msgs:
                    await msg.add_reaction("💸")

                    if category != None:
                        await msg.add_reaction("🐂")
                        await msg.add_reaction("🦆")
                        await msg.add_reaction("🐻")

            except discord.DiscordServerError:
                print("Could not add reaction to message")

        except aiohttp.ClientConnectionError:
            print("Connection Error posting tweet on timeline")

        except Exception as error:
            print("Error posting tweet on timeline", error)
            print(traceback.format_exc())


def setup(bot: commands.Bot) -> None:
    """
    This is a necessary method to make the cog loadable.

    Returns
    -------
    None
    """
    bot.add_cog(Timeline(bot))
