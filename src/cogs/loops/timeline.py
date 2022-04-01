##> Imports
import asyncio
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

from util.disc_util import get_channel
from util.db import get_db
from util.tweet_util import format_tweet, add_financials


class Timeline(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Call start() to start the stream
        asyncio.create_task(self.start())

    async def start(self):
        printer = Streamer(
            consumer_key, consumer_secret, access_token, access_token_secret, self.bot
        )

        following = api.get_friend_ids()

        await printer.filter(follow=following)


def setup(bot):
    bot.add_cog(Timeline(bot))


class Streamer(AsyncStream):
    def __init__(
        self, consumer_key, consumer_secret, access_token, access_token_secret, bot
    ):

        # Init the parent class
        AsyncStream.__init__(
            self, consumer_key, consumer_secret, access_token, access_token_secret
        )

        # Set the bot for messages
        self.bot = bot

        # Set the channels
        self.timeline = get_channel(self.bot, config["TIMELINE"]["CHANNEL"])

        self.stocks_charts_channel = get_channel(
            self.bot, config["STOCKS"]["CHARTS_CHANNEL"]
        )
        self.stocks_text_channel = get_channel(
            self.bot, config["STOCKS"]["TEXT_CHANNEL"]
        )

        self.crypto_charts_channel = get_channel(
            self.bot, config["CRYPTO"]["CHARTS_CHANNEL"]
        )
        self.crypto_text_channel = get_channel(
            self.bot, config["CRYPTO"]["TEXT_CHANNEL"]
        )

        self.images_channel = get_channel(self.bot, config["IMAGES"]["CHANNEL"])
        self.other_channel = get_channel(self.bot, config["OTHER"]["CHANNEL"])

        self.news_channel = get_channel(self.bot, "📰┃news")

        # Get all text channels
        self.all_txt_channels.start()

        # Set following ids
        self.get_following_ids.start()

        self.assets_db = None
        self.get_assets_db.start()

    @loop(minutes=60)
    async def get_assets_db(self):
        self.assets_db = get_db("assets")

    @loop(minutes=60)
    async def all_txt_channels(self):
        text_channel_list = []
        text_channel_names = []
        for server in self.bot.guilds:
            for channel in server.channels:
                if str(channel.type) == "text":
                    text_channel_list.append(channel)
                    text_channel_names.append(channel.name.split("┃")[1])

        self.text_channels = text_channel_list
        self.text_channel_names = text_channel_names

    @loop(minutes=15)
    async def get_following_ids(self):
        # Get user ids of people who we are following
        self.following_ids = api.get_friend_ids()

    async def on_data(self, raw_data):
        """
        This method is called whenever data is received from the stream.
        """
        formatted_tweet = await format_tweet(raw_data, self.following_ids)

        if formatted_tweet == None:
            return
        else:
            await self.post_tweet(*formatted_tweet)

    async def post_tweet(
        self, text, user, profile_pic, url, images, tickers, hashtags, retweeted_user
    ):

        # Use 'media' 'url' as url
        # Use 'profile_image_url'' for thumbnail

        title = (
            f"{user} tweeted about {', '.join(tickers)}"
            if retweeted_user == None
            else f"{user} 🔁 {retweeted_user} about {', '.join(tickers)}"
        )

        if len(title) > 256:
            title = title[:253] + "..."

        e = discord.Embed(title=title, url=url, description=text, color=0x1DA1F2,)

        e.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)
        e.set_thumbnail(url=profile_pic)

        # Max 25 fields
        if len(tickers + hashtags) < 26:
            e, category = await add_financials(
                e, tickers, hashtags, text, user, self.bot
            )
        else:
            category = None

        # Set image if an image is included in the tweet
        if images:
            e.set_image(url=images[0])

        e.set_footer(
            text=f"Today at {datetime.datetime.now().strftime('%H:%M')}",
            icon_url="https://abs.twimg.com/icons/apple-touch-icon-192x192.png",
        )

        msg, channel = await self.upload_tweet(
            e, category, images, user, retweeted_user
        )

        if len(tickers + hashtags) > 0:
            await self.tag_user(msg, channel, tickers + hashtags)

    async def tag_user(self, msg, channel, tickers):
        # Get the stored db
        matching_users = self.assets_db[self.assets_db["asset"].isin(tickers)][
            "id"
        ].tolist()
        unique_users = list(set(matching_users))

        for user in unique_users:
            await channel.send(f"<@{user}>", reference=msg)

    async def upload_tweet(self, e, category, images, user, retweeted_user):
        """ Upload tweet in the dedicated discord channel """

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

        elif user in config["NEWS"]:
            channel = self.news_channel

        elif category == None and not images:
            channel = self.other_channel
        elif category == None and images:
            channel = self.images_channel

        elif category == "crypto" and not images:
            channel = self.crypto_text_channel
        elif category == "crypto" and images:
            channel = self.crypto_charts_channel

        elif category == "stocks" and not images:
            channel = self.stocks_text_channel
        else:
            channel = self.stocks_charts_channel

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
