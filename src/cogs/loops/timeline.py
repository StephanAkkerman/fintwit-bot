##> Imports
# > Standard libraries
from __future__ import annotations
import asyncio
from typing import List
import datetime
import traceback
import requests
import json

# > 3rd Party Dependencies
from tweepy.asynchronous import AsyncStreamingClient
from tweepy import StreamRule

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, bearer_token, get_json_data
from util.disc_util import get_channel, get_tagged_users
from util.tweet_util import format_tweet, add_financials
from util.db import update_tweet_db
from cogs.loops.overview import Overview


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
        printer = Streamer(self.bot)

        try:
            await printer.add_rules(self.get_rules())
            # https://docs.tweepy.org/en/stable/asyncstreamingclient.html#tweepy.asynchronous.AsyncStreamingClient.filter
            # https://developer.twitter.com/en/docs/twitter-api/fields
            await printer.filter(
                expansions=[
                    "author_id",
                    "referenced_tweets.id",
                    "in_reply_to_user_id",
                    "attachments.media_keys",
                    "entities.mentions.username",
                    "referenced_tweets.id.author_id",
                ],
                tweet_fields=[
                    "id",
                    "text",
                    "attachments",
                    "author_id",
                    "conversation_id",
                    "entities",
                    "in_reply_to_user_id",
                    "referenced_tweets",
                ],
                user_fields=["id", "name", "username", "profile_image_url"],
                media_fields=[
                    "media_key",
                    "type",
                    "url",
                    "height",
                    "preview_image_url",
                    "width",
                    "variants",
                ],
            )

        except Exception as e:
            print("Could not get following ids on startup. Error: ", e)

            # Wait 5 min and try again
            await asyncio.sleep(60 * 5)
            await self.start()

    def get_rules(self) -> List[StreamRule]:
        """
        Creates the rules for the streamer to filter on.
        Only tweets from users that the bot is following are allowed.

        Returns
        -------
        List[StreamRule]
            List of StreamRules to filter on.
        """
        id = requests.get(
            f"https://api.twitter.com/2/users/by/username/{config['TWITTER']['USERNAME']}?user.fields=id",
            headers={"Authorization": f"Bearer {bearer_token}"},
        ).json()["data"]["id"]

        following = requests.get(
            f"https://api.twitter.com/2/users/{id}/following?max_results=1000",
            headers={"Authorization": f"Bearer {bearer_token}"},
        ).json()["data"]

        following = [user["id"] for user in following]

        rules = []
        text_rule = ""
        for user in following:
            if len(text_rule) + len(str(user)) + 2 < 512:
                text_rule += f"from:{user} OR "
            else:
                # https://docs.tweepy.org/en/stable/streamrule.html#tweepy.StreamRule
                rules.append(StreamRule(value=text_rule[:-4], tag="user"))
                text_rule = ""

        return rules


def setup(bot: commands.Bot) -> None:
    """
    This is a necessary method to make the cog loadable.

    Returns
    -------
    None
    """
    bot.add_cog(Timeline(bot))


class Streamer(AsyncStreamingClient):
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
        bot: commands.Bot,
    ) -> None:

        # Init the parent class
        # https://docs.tweepy.org/en/stable/asyncstreamingclient.html
        AsyncStreamingClient.__init__(
            self, bearer_token=bearer_token, wait_on_rate_limit=True, max_retries=10
        )

        # Set the bot for messages
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
                self.bot, config["LOOPS"]["TIMELINE"]["NEWS"]["CHANNEL"]
            )

        # Get all text channels
        self.all_txt_channels.start()

        # Set following ids
        # self.get_following_ids.start()

        self.tweet_overview = Overview(self.bot)

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
        # Could also use this
        # https://developer.twitter.com/en/docs/twitter-api/users/follows/api-reference/get-users-id-following
        try:
            id = await get_json_data(
                f"https://api.twitter.com/2/users/by/username/{config['TWITTER']['USERNAME']}?user.fields=id",
                headers={"Authorization": f"Bearer {bearer_token}"},
            )
            following = await get_json_data(
                f"https://api.twitter.com/2/users/{id['data']['id']}/following?max_results=1000",
                headers={"Authorization": f"Bearer {bearer_token}"},
            )
            self.following_ids = [user["id"] for user in following["data"]]
        except Exception as e:
            print(e)
            print("Failed to get following ids")

    async def on_connection_error(self):
        print("Tweepy Stream Connection error")
        # Consider restarting the stream

    async def on_request_error(self, status_code):
        return await super().on_request_error(status_code)

    async def on_data(self, raw_data: str | bytes) -> None:
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

        # Convert the string json data to json object
        tweet_data = json.loads(raw_data)
        
        if "data" not in tweet_data.keys():
            # For instance if the stream was temporarily disconnected
            print("Stream error")
            return
        else:
            formatted_tweet = await format_tweet(tweet_data)

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

        # Ensure the tickers are unique
        tickers = list(set(tickers))

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
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        e.set_thumbnail(url=profile_pic)

        # Max 25 fields
        if len(tickers + hashtags) < 26:
            e, category, sentiment, base_symbols, categories = await add_financials(
                e, tickers, hashtags, text, user, self.bot
            )
        else:
            # If the tweet contains no tickers or hasthags, then it is not a financial tweet
            category = None
            base_symbols = None

        # Set image if an image is included in the tweet
        if images:
            e.set_image(url=images[0])

        # Set the twitter icon as footer image
        e.set_footer(
            text="\u200b",
            icon_url="https://abs.twimg.com/icons/apple-touch-icon-192x192.png",
        )

        # Upload the tweet to the Discord.
        await self.upload_tweet(
            e, category, images, user, retweeted_user, tickers + hashtags
        )

        if base_symbols:
            # This can be deleted later
            if len(base_symbols) != len(categories):
                print("Error: tickers and categories are not the same length")
                print("Tickers:", base_symbols)
                print("Categories:", categories)
            else:
                tweet_db = update_tweet_db(base_symbols, user, sentiment, categories)
                await self.tweet_overview.overview(
                    tweet_db, category, base_symbols, sentiment
                )

    async def upload_tweet(
        self,
        e: discord.Embed,
        category: str,
        images: List[str],
        user: str,
        retweeted_user: str,
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

        # Default channel
        channel = self.other_channel

        # Check if there is a user specific channel
        # If there is a retweeted user check for both
        if retweeted_user and retweeted_user.lower() in self.text_channel_names:
            channel = self.text_channels[
                self.text_channel_names.index(retweeted_user.lower())
            ]

        # Highlighted users
        elif user.lower() in self.text_channel_names:
            channel = self.text_channels[self.text_channel_names.index(user.lower())]

        # News posters
        elif user in config["LOOPS"]["TIMELINE"]["NEWS"]["FOLLOWING"]:
            channel = self.news_channel

        # Tweets without financial information
        elif category == None and not images:
            channel = self.other_channel
        elif category == None and images:
            channel = self.images_channel

        # If we do not know what category it is, assume it is crypto
        elif (category == "crypto" or category == "🤷‍♂️") and not images:
            channel = self.crypto_text_channel
        elif (category == "crypto" or category == "🤷‍♂️") and images:
            channel = self.crypto_charts_channel

        # Stocks tweet channels
        elif category == "stocks" and not images:
            channel = self.stocks_text_channel
        elif category == "stocks" and images:
            channel = self.stocks_charts_channel

        # Forex tweet channels
        elif category == "forex" and not images:
            channel = self.forex_text_channel
        elif category == "forex" and images:
            channel = self.forex_charts_channel

        try:
            # Create a list of image embeds, max 10 images per post
            image_e = [e] + [
                discord.Embed(url=e.url).set_image(url=img) for img in images[1:10]
            ]

            # If there are multiple images to be sent, use a webhook to send them all at once
            if len(image_e) > 1:
                webhook = await channel.webhooks()

                if not webhook:
                    webhook = await channel.create_webhook(name=channel.name)
                    print(f"Created webhook for {channel.name}")
                else:
                    webhook = webhook[0]

                # Wait so we can use this message as reference
                msg = await webhook.send(
                    content=get_tagged_users(tickers),
                    embeds=image_e,
                    username="FinTwit",
                    wait=True,
                    avatar_url=self.bot.user.avatar.url,
                )

            else:
                # Use the normal send function
                msg = await channel.send(content=get_tagged_users(tickers), embed=e)

            # Do this for every message
            try:
                await msg.add_reaction("💸")
            except discord.DiscordServerError:
                print("Could not add reaction to message")

            if category != None:
                try:
                    await msg.add_reaction("🐂")
                    await msg.add_reaction("🦆")
                    await msg.add_reaction("🐻")
                except discord.DiscordServerError:
                    print("Could not add reaction to message")

            return msg, channel

        except Exception as error:
            print("Error posting tweet on timeline", error)
            print(traceback.format_exc())
            return
