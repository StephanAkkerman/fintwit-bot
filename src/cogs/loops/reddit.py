import os
from datetime import datetime

import asyncpraw
from discord import Embed
from discord.ext import commands
from discord.ext.tasks import loop

from api.reddit import reddit_scraper
from constants.config import config
from constants.logger import logger
from constants.sources import data_sources
from util.disc import get_channel, get_webhook, loop_error_catcher


class Reddit(commands.Cog):
    """
    This class contains the cog for posting the top reddit posts.
    It can be enabled / disabled in the config under ["LOOPS"]["REDDIT"].
    """

    def __init__(self, bot: commands.bot.Bot) -> None:
        self.bot = bot
        self.first_time = True

        self.reddit = asyncpraw.Reddit(
            client_id=os.getenv("REDDIT_PERSONAL_USE"),
            client_secret=os.getenv("REDDIT_SECRET"),
            user_agent=os.getenv("REDDIT_APP_NAME"),
            username=os.getenv("REDDIT_USERNAME"),
            password=os.getenv("REDDIT_PASSWORD"),
        )

        # Setup configuration for subreddits
        self.subreddits = {
            "WallStreetBets": {
                "enabled": config["LOOPS"]["REDDIT"]["WALLSTREETBETS"]["ENABLED"],
                "channel_id": config["LOOPS"]["REDDIT"]["WALLSTREETBETS"]["CHANNEL"],
                "first_time": True,
                "channel": None,
                "scraper": self.wsb_scraper,
            },
            "CryptoMoonShots": {
                "enabled": config["LOOPS"]["REDDIT"]["CRYPTOMOONSHOTS"]["ENABLED"],
                "channel_id": config["LOOPS"]["REDDIT"]["CRYPTOMOONSHOTS"]["CHANNEL"],
                "first_time": True,
                "channel": None,
                "scraper": self.cms_scraper,
            },
        }

        # Start the scrapers for enabled subreddits
        for subreddit, settings in self.subreddits.items():
            if settings["enabled"]:
                settings["scraper"].start()

    async def load_channel(self, subreddit_name):
        """
        Helper function to load the channel for a subreddit.
        """
        subreddit_info = self.subreddits[subreddit_name]
        if subreddit_info["channel"] is None:
            subreddit_info["channel"] = await get_channel(
                self.bot, subreddit_info["channel_id"]
            )
            subreddit_info["first_time"] = False

    async def scrape_and_send_posts(self, subreddit_name):
        """
        Helper function to scrape Reddit posts and send them to the appropriate channel.
        """
        subreddit_info = self.subreddits[subreddit_name]

        # Load channel if it's the first time
        if subreddit_info["first_time"]:
            await self.load_channel(subreddit_name)

        # Scrape posts and send them to the channel
        posts = await reddit_scraper(
            subreddit_name=subreddit_name, reddit_client=self.reddit
        )
        await self.send_posts(posts, subreddit_name)

    @loop(hours=12)
    @loop_error_catcher
    async def wsb_scraper(self):
        """
        Scraper for WallStreetBets subreddit.
        """
        await self.scrape_and_send_posts("WallStreetBets")

    @loop(hours=12)
    @loop_error_catcher
    async def cms_scraper(self):
        """
        Scraper for CryptoMoonShots subreddit.
        """
        await self.scrape_and_send_posts("CryptoMoonShots")

    async def send_posts(self, posts: list, subreddit_name: str):
        channel = self.subreddits[subreddit_name]["channel"]
        if channel:
            for counter, post in enumerate(posts):
                submission, title, descr, img_urls = post
                embed = create_embed(submission, title, descr, img_urls)
                await self.send_embed(embed, img_urls, channel)

                if counter > 10:
                    return
        else:
            logger.error(f"Channel not found for {subreddit_name}.")

    async def send_embed(self, embed: Embed, img_urls: list, channel) -> None:
        """
        Send a discord embed, handling multiple images if necessary.

        Parameters
        ----------
        embed : discord.Embed
            The embed to send.
        img_urls : list
            The list of image URLs.
        channel : discord.TextChannel
            The channel to send the embed to.

        Returns
        -------
        None
        """
        if len(img_urls) > 1:
            image_embeds = [embed] + [
                Embed(url=embed.url).set_image(url=img) for img in img_urls[1:10]
            ]
            webhook = await get_webhook(channel)
            await webhook.send(
                embeds=image_embeds,
                username="FinTwit",
                wait=True,
                avatar_url=self.bot.user.avatar.url,
            )
        else:
            await channel.send(embed=embed)


def create_embed(submission, title: str, descr: str, img_urls: list) -> Embed:
    """
    Create a discord embed for a reddit submission.

    Parameters
    ----------
    submission : asyncpraw.models.Submission
        The reddit submission.
    title : str
        The title of the submission.
    descr : str
        The description of the submission.
    img_urls : list
        The list of image URLs.

    Returns
    -------
    discord.Embed
        The created embed.
    """
    embed = Embed(
        title=title,
        url="https://www.reddit.com" + submission.permalink,
        description=descr,
        color=data_sources["reddit"]["color"],
        timestamp=datetime.utcfromtimestamp(submission.created_utc),
    )
    if img_urls:
        embed.set_image(url=img_urls[0])
    embed.set_footer(
        text=f"🔼 {submission.score} | 💬 {submission.num_comments} | {submission.link_flair_text}",
        icon_url=data_sources["reddit"]["icon"],
    )
    return embed


def setup(bot: commands.bot.Bot) -> None:
    bot.add_cog(Reddit(bot))
