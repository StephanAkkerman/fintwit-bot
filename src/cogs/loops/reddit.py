# Standard libraries
import datetime

# > 3rd party dependencies
import asyncpraw

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config
from util.disc_util import get_channel


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

            # Get the subreddit database

            self.wsb.start(reddit)

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

        subreddit = await reddit.subreddit("WallStreetBets")
        try:
            counter = 1
            async for submission in subreddit.hot(limit=10):
                if submission.stickied:
                    continue

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
                        descr = "See video below."

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
                    text=f"#{counter} | 🔼 {submission.score} | 💬 {submission.num_comments}",
                    icon_url="https://external-preview.redd.it/iDdntscPf-nfWKqzHRGFmhVxZm4hZgaKe5oyFws-yzA.png?width=640&crop=smart&auto=webp&s=bfd318557bf2a5b3602367c9c4d9cd84d917ccd5",
                )

                msg = await self.channel.send(embed=e)

                for i in range(len(img_url)):
                    if i > 0:
                        await self.channel.send(reference=msg, content=img_url[i])

                if video:
                    await self.channel.send(
                        reference=msg, content=url + "/DASH_360.mp4"
                    )

                counter += 1

        except Exception as e:
            print("Error getting reddit posts", e)


def setup(bot: commands.bot.Bot) -> None:
    bot.add_cog(Reddit(bot))
