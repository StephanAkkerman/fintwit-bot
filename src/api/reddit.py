import html
import re
from datetime import datetime, timedelta

import asyncpraw
import pandas as pd

import util.vars
from constants.logger import logger
from util.db import update_db

URL_REGEX = r"(?P<url>https?://[^\s]+)"
MARKDOWN_LINK_REGEX = r"\[(?P<text>[^\]]+)\]\((?P<url>https?://[^\s]+)\)"


def add_id_to_db(id: str) -> None:
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


def update_reddit_ids():
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


async def reddit_scraper(
    limit: int = 15,
    subreddit_name: str = "WallStreetBets",
    reddit_client: asyncpraw.Reddit = None,
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
    update_reddit_ids()
    subreddit = await reddit_client.subreddit(subreddit_name)

    posts = []
    async for submission in subreddit.hot(limit=limit):
        if submission.stickied or is_submission_processed(submission.id):
            continue

        add_id_to_db(submission.id)

        descr = truncate_text(html.unescape(submission.selftext), 4000)
        descr = process_description(descr)  # Process the description for URLs

        title = truncate_text(html.unescape(submission.title), 250)
        img_urls, title = process_submission_media(submission, title)

        posts.append((submission, title, descr, img_urls))

    update_db(util.vars.reddit_ids, "reddit_ids")
    return posts


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
                logger.warn("No image found for Reddit video post")
    return img_urls, title
