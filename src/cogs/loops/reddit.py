# Standard libraries
import datetime
import html
import os

# > 3rd party dependencies
import asyncpraw

# > Discord dependencies
import discord
import pandas as pd

# Local dependencies
import util.vars
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

        reddit = asyncpraw.Reddit(
            client_id=os.getenv("REDDIT_PERSONAL_USE"),
            client_secret=os.getenv("REDDIT_SECRET"),
            user_agent=os.getenv("REDDIT_APP_NAME"),
            username=os.getenv("REDDIT_USERNAME"),
            password=os.getenv("REDDIT_PASSWORD"),
        )

        if config["LOOPS"]["REDDIT"]["WALLSTREETBETS"]["ENABLED"]:
            self.channel = get_channel(
                self.bot, config["LOOPS"]["REDDIT"]["WALLSTREETBETS"]["CHANNEL"]
            )

            self.wsb.start(reddit)

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
                            "timestamp": datetime.datetime.now(),
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    @loop(hours=12)
    async def wsb(self, reddit: asyncpraw.Reddit) -> None:
        """
        Scrapes the top reddit posts from the wallstreetbets subreddit and posts them in the wallstreetbets channel.

        Parameters
        ----------
        reddit : asyncpraw.Reddit
            The reddit instance using the bot's credentials.

        Returns
        -------
        None
        """

        if not util.vars.reddit_ids.empty:
            # Set the types
            util.vars.reddit_ids = util.vars.reddit_ids.astype(
                {
                    "id": str,
                    "timestamp": "datetime64[ns]",
                }
            )

            # Only keep ids that are less than 72 hours old
            util.vars.reddit_ids = util.vars.reddit_ids[
                util.vars.reddit_ids["timestamp"]
                > datetime.datetime.now() - datetime.timedelta(hours=72)
            ]

        subreddit = await reddit.subreddit("WallStreetBets")
        try:
            counter = 1

            # https://asyncpraw.readthedocs.io/en/stable/code_overview/models/submission.html?highlight=poll_data#asyncpraw.models.Submission
            async for submission in subreddit.hot(limit=15):
                # Skip stickied posts
                if submission.stickied:
                    continue

                if not util.vars.reddit_ids.empty:
                    if submission.id in util.vars.reddit_ids["id"].tolist():
                        counter += 1
                        continue

                # If it is a new submission add it to the db
                self.add_id_to_db(submission.id)

                descr = html.unescape(submission.selftext)

                # Make sure the description and title are not too long
                if len(descr) > 4000:
                    descr = descr[:4000] + "..."

                title = html.unescape(submission.title)
                if len(title) > 250:
                    title = title[:250] + "..."

                # Add images to the embed
                img_url = []
                video = False
                if not submission.is_self:
                    url = submission.url
                    if (
                        url.endswith(".jpg")
                        or url.endswith(".png")
                        or url.endswith(".gif")
                    ):
                        img_url.append(url)
                        title = "🖼️ " + title
                    # If the post includes multiple images
                    elif "gallery" in url:
                        image_dict = submission.media_metadata
                        for image_item in image_dict.values():
                            largest_image = image_item["s"]
                            img_url.append(largest_image["u"])

                        title = "📸🖼️ " + title
                    elif "v.redd.it" in url:
                        video = True
                        title = "🎥 " + title
                        if "images" in submission.preview:
                            img_url.append(
                                submission.preview["images"][0]["source"]["url"]
                            )
                        else:
                            print("No image found for video post")

                e = discord.Embed(
                    title=title,
                    url="https://www.reddit.com" + submission.permalink,
                    description=descr,
                    color=data_sources["reddit"]["color"],
                    timestamp=datetime.datetime.utcfromtimestamp(
                        submission.created_utc
                    ),
                )
                if img_url:
                    e.set_image(url=img_url[0])

                e.set_footer(
                    text=f"🔼 {submission.score} | 💬 {submission.num_comments}",
                    icon_url=data_sources["reddit"]["icon"],
                )

                if len(img_url) > 1:
                    # Create a list of image embeds, max 10 images per post
                    image_e = [e] + [
                        discord.Embed(url=e.url).set_image(url=img)
                        for img in img_url[1:10]
                    ]

                    webhook = await get_webhook(self.channel)

                    await webhook.send(
                        embeds=image_e,
                        username="FinTwit",
                        wait=True,
                        avatar_url=self.bot.user.avatar.url,
                    )
                else:
                    await self.channel.send(embed=e)

                counter += 1

                if counter == 11:
                    break

            # Write to db
            update_db(util.vars.reddit_ids, "reddit_ids")

        except Exception as e:
            print("Error getting reddit posts, error:", e)


def setup(bot: commands.bot.Bot) -> None:
    bot.add_cog(Reddit(bot))
