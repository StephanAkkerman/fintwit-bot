import os
from datetime import datetime

import asyncpraw
from discord import Embed
from discord.ext import commands
from discord.ext.tasks import loop

from api.reddit import reddit_scraper
from util.disc_util import get_channel, get_webhook, loop_error_catcher
from util.vars import config, data_sources


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

        if config["LOOPS"]["REDDIT"]["WALLSTREETBETS"]["ENABLED"]:
            self.wsb_channel = None
            self.wsb_scraper.start()

        if config["LOOPS"]["REDDIT"]["CRYPTOMOONSHOTS"]["ENABLED"]:
            self.cmc_channel = None
            self.cms_scraper.start()

    @loop(hours=12)
    @loop_error_catcher
    async def wsb_scraper(self):
        if self.wsb_channel is None:
            self.wsb_channel = await get_channel(
                self.bot, config["LOOPS"]["REDDIT"]["WALLSTREETBETS"]["CHANNEL"]
            )
            posts = await reddit_scraper(subreddit_name="WallStreetBets")
            self.send_posts(posts, "WallStreetBets")
            self.first_time = False

        # To prevent it from going to quick
        if not self.first_time:
            posts = await reddit_scraper(subreddit_name="WallStreetBets")
            self.send_posts(posts, "WallStreetBets")

    @loop(hours=12)
    @loop_error_catcher
    async def cms_scraper(self):
        if self.cms_scraper is None:
            self.cmc_channel = await get_channel(
                self.bot, config["LOOPS"]["REDDIT"]["CRYPTOMOONSHOTS"]["CHANNEL"]
            )
            posts = await reddit_scraper(subreddit_name="CryptoMoonShots")
            self.send_posts(posts, "CryptoMoonShots")
            self.first_time = False

        if not self.first_time:
            posts = await reddit_scraper(subreddit_name="CryptoMoonShots")
            self.send_posts(posts, "CryptoMoonShots")

    async def send_posts(self, posts: list, subreddit_name: str):
        for counter, post in enumerate(posts):
            submission, title, descr, img_urls = post
            embed = create_embed(submission, title, descr, img_urls)
            if subreddit_name == "WallStreetBets":
                channel = self.wsb_channel
            else:
                channel = self.cmc_channel
            await self.send_embed(embed, img_urls, channel)

            if counter > 10:
                return

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
