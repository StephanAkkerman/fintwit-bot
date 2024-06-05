import html
import os
import re
from datetime import datetime, timedelta

import asyncpraw
import pandas as pd
import util.vars
from discord import Embed
from discord.ext import commands
from discord.ext.tasks import loop
from util.db import update_db
from util.disc_util import get_channel, get_webhook
from util.vars import config, data_sources


class Reddit(commands.Cog):
    """
    This class contains the cog for posting the top reddit posts.
    It can be enabled / disabled in the config under ["LOOPS"]["REDDIT"].
    """

    def __init__(self, bot: commands.bot.Bot) -> None:
        self.bot = bot

        self.reddit = asyncpraw.Reddit(
            client_id=os.getenv("REDDIT_PERSONAL_USE"),
            client_secret=os.getenv("REDDIT_SECRET"),
            user_agent=os.getenv("REDDIT_APP_NAME"),
            username=os.getenv("REDDIT_USERNAME"),
            password=os.getenv("REDDIT_PASSWORD"),
        )

        if config["LOOPS"]["REDDIT"]["WALLSTREETBETS"]["ENABLED"]:
            self.wsb_channel = get_channel(
                self.bot, config["LOOPS"]["REDDIT"]["WALLSTREETBETS"]["CHANNEL"]
            )

            self.wsb_scraper.start()

        if config["LOOPS"]["REDDIT"]["CRYPTOMOONSHOTS"]["ENABLED"]:
            self.cmc_channel = get_channel(
                self.bot, config["LOOPS"]["REDDIT"]["CRYPTOMOONSHOTS"]["CHANNEL"]
            )

            self.cms_scraper.start()

    def add_id_to_db(self, id: str) -> None:
        """
        Adds the given id to the database.
        """

        util.vars.reddit_ids = pd.concat(
            [
                util.vars.reddit_ids,
                pd.DataFrame(
                    [
                        {
                            "id": id,
                            "timestamp": datetime.now(),
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    @loop(hours=12)
    async def wsb_scraper(self):
        await self.reddit_scraper(
            subreddit_name="WallStreetBets", channel=self.wsb_channel
        )

    @loop(hours=12)
    async def cms_scraper(self):
        await self.reddit_scraper(
            subreddit_name="CryptoMoonShots", channel=self.cmc_channel
        )

    async def reddit_scraper(
        self,
        limit: int = 15,
        subreddit_name: str = "WallStreetBets",
        channel=None,
    ) -> None:
        """
        Scrapes the top reddit posts from the wallstreetbets subreddit and posts them in the wallstreetbets channel.

        Parameters
        ----------
        reddit : asyncpraw.Reddit
            The reddit instance using the bot's credentials.
        limit : int
            The number of posts to scrape.
        subreddit_name : str
            The name of the subreddit to scrape.

        Returns
        -------
        None
        """
        try:
            await update_reddit_ids()
            subreddit = await self.reddit.subreddit(subreddit_name)

            counter = 1
            async for submission in subreddit.hot(limit=limit):
                if submission.stickied or is_submission_processed(submission.id):
                    continue

                self.add_id_to_db(submission.id)

                descr = truncate_text(html.unescape(submission.selftext), 4000)
                descr = process_description(descr)  # Process the description for URLs

                title = truncate_text(html.unescape(submission.title), 250)
                img_urls, title = process_submission_media(submission, title)

                embed = create_embed(submission, title, descr, img_urls)
                await self.send_embed(embed, img_urls, channel)

                counter += 1
                if counter > 10:
                    break

            update_db(util.vars.reddit_ids, "reddit_ids")

        except Exception as e:
            print("Error getting reddit posts, error:", e)

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


async def update_reddit_ids():
    """
    Update the list of reddit IDs, removing those older than 72 hours.
    """
    if not util.vars.reddit_ids.empty:
        util.vars.reddit_ids = util.vars.reddit_ids.astype(
            {"id": str, "timestamp": "datetime64[ns]"}
        )
        util.vars.reddit_ids = util.vars.reddit_ids[
            util.vars.reddit_ids["timestamp"] > datetime.now() - timedelta(hours=72)
        ]


def is_submission_processed(submission_id: str) -> bool:
    """
    Check if a submission has already been processed.

    Parameters
    ----------
    submission_id : str
        The ID of the submission.

    Returns
    -------
    bool
        True if the submission has been processed, False otherwise.
    """
    if (
        not util.vars.reddit_ids.empty
        and submission_id in util.vars.reddit_ids["id"].tolist()
    ):
        return True
    return False


def truncate_text(text: str, max_length: int) -> str:
    """
    Truncate text to a maximum length, adding ellipsis if truncated.

    Parameters
    ----------
    text : str
        The text to truncate.
    max_length : int
        The maximum length of the text.

    Returns
    -------
    str
        The truncated text.
    """
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def process_submission_media(submission, title: str) -> tuple:
    """
    Process the media in a submission, updating the title and extracting image URLs.

    Parameters
    ----------
    submission : asyncpraw.models.Submission
        The reddit submission.
    title : str
        The title of the submission.

    Returns
    -------
    tuple
        A tuple containing the list of image URLs and the updated title.
    """
    img_urls = []
    if not submission.is_self:
        url = submission.url
        if url.endswith((".jpg", ".png", ".gif")):
            img_urls.append(url)
            title = "🖼️ " + title
        elif "gallery" in url:
            for image_item in submission.media_metadata.values():
                img_urls.append(image_item["s"]["u"])
            title = "📸🖼️ " + title
        elif "v.redd.it" in url:
            title = "🎥 " + title
            if "images" in submission.preview:
                img_urls.append(submission.preview["images"][0]["source"]["url"])
            else:
                print("No image found for video post")
    return img_urls, title


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


URL_REGEX = r"(?P<url>https?://[^\s]+)"
MARKDOWN_LINK_REGEX = r"\[(?P<text>[^\]]+)\]\((?P<url>https?://[^\s]+)\)"


def process_description(description):
    """
    Process the description to convert URLs to plain text links unless they are part of a hyperlink with custom text.

    Parameters
    ----------
    description : str
        The original description text.

    Returns
    -------
    str
        The processed description.
    """

    # Replace Markdown links with just the URL if the text matches the URL
    def replace_markdown_link(match):
        text = match.group("text")
        url = match.group("url")
        if text == url:
            return url
        return match.group(0)

    description = re.sub(MARKDOWN_LINK_REGEX, replace_markdown_link, description)

    # Replace remaining URLs with just the URL
    def replace_url(match):
        return match.group("url")

    processed_description = re.sub(URL_REGEX, replace_url, description)

    return processed_description


def setup(bot: commands.bot.Bot) -> None:
    bot.add_cog(Reddit(bot))
