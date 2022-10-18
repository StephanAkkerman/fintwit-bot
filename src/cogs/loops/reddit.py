# Standard libraries
import datetime

# > 3rd party dependencies
import asyncpraw
import pandas as pd

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
import util.vars
from util.vars import config
from util.disc_util import get_channel, get_webhook
from util.db import update_db


class Reddit(commands.Cog):
    """
    This class contains the cog for posting the top reddit posts.
    It can be enabled / disabled in the config under ["LOOPS"]["REDDIT"].

    Methods
    -------
    function() -> None:
        _description_
    """

    def __init__(self, bot: commands.bot.Bot) -> None:
        self.bot = bot

        reddit = asyncpraw.Reddit(
            client_id=config["REDDIT"]["PERSONAL_USE"],
            client_secret=config["REDDIT"]["SECRET"],
            user_agent=config["REDDIT"]["APP_NAME"],
            username=config["REDDIT"]["USERNAME"],
            password=config["REDDIT"]["PASSWORD"],
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

                # Skip polls
                if "poll_data" in vars(submission).keys():
                    continue

                if not util.vars.reddit_ids.empty:
                    if submission.id in util.vars.reddit_ids["id"].tolist():
                        counter += 1
                        continue

                # If it is a new submission add it to the db
                self.add_id_to_db(submission.id)

                descr = submission.selftext

                # Make sure the description and title are not too long
                if len(descr) > 4000:
                    descr = descr[:4000] + "..."

                title = submission.title
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
                    elif "gallery" in url:
                        image_dict = submission.media_metadata
                        for image_item in image_dict.values():
                            largest_image = image_item["s"]
                            img_url.append(largest_image["u"])
                    elif "v.redd.it" in url:
                        video = True
                        descr = ""
                        
                e = discord.Embed(
                    title=title,
                    url="https://www.reddit.com" + submission.permalink,
                    description=descr,
                    color=0xFF3F18,
                    timestamp=datetime.datetime.utcfromtimestamp(
                        submission.created_utc
                    ),
                )
                if img_url:
                    e.set_image(url=img_url[0])

                e.set_thumbnail(
                    url="https://styles.redditmedia.com/t5_2th52/styles/communityIcon_wzrl8s0hx8a81.png?width=256&s=dcbf830170c1e8237335a3f046b36f723c5d55e7"
                )

                e.set_footer(
                    text=f"🔼 {submission.score} | 💬 {submission.num_comments}",
                    icon_url="https://external-preview.redd.it/iDdntscPf-nfWKqzHRGFmhVxZm4hZgaKe5oyFws-yzA.png?width=640&crop=smart&auto=webp&s=bfd318557bf2a5b3602367c9c4d9cd84d917ccd5",
                )

                if len(img_url) > 1:
                    # Create a list of image embeds, max 10 images per post
                    image_e = [e] + [
                        discord.Embed(url=e.url).set_image(url=img)
                        for img in img_url[1:10]
                    ]

                    webhook = await get_webhook(self.channel)

                    msg = await webhook.send(
                        embeds=image_e,
                        username="FinTwit",
                        wait=True,
                        avatar_url=self.bot.user.avatar.url,
                    )
                else:
                    if video:
                        await self.channel.send(content = f"https://www.reddit.com{submission.permalink}")
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
