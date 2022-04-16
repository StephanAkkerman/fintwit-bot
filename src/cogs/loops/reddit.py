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
    def __init__(self, bot):
        self.bot = bot

        reddit = asyncpraw.Reddit(
            client_id=config["REDDIT"]["PERSONAL_USE"],
            client_secret=config["REDDIT"]["SECRET"],
            user_agent=config["REDDIT"]["APP_NAME"],
            username=config["REDDIT"]["USERNAME"],
            password=config["REDDIT"]["PASSWORD"],
        )

        self.wsb.start(reddit)

    @loop(hours=12)
    async def wsb(self, reddit):
        channel = get_channel(
            self.bot, config["SUBREDDIT"]["WALLSTREETBETS"]["CHANNEL"]
        )

        em = discord.Embed(
            title="Hottest r/wallstreetbets posts of the last 24 hours",
            url="https://www.reddit.com/r/wallstreetbets/",
            description="The 10 hottest posts of the last 12 hours on r/wallstreetbets are posted below!",
            color=0xFF3F18,
            timestamp=datetime.datetime.utcnow(),
        )
        em.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)
        em.set_thumbnail(
            url="https://styles.redditmedia.com/t5_2th52/styles/communityIcon_wzrl8s0hx8a81.png?width=256&s=dcbf830170c1e8237335a3f046b36f723c5d55e7"
        )

        await channel.send(embed=em)

        subreddit = await reddit.subreddit("WallStreetBets")
        async for submission in subreddit.hot(limit=10):
            if submission.stickied:
                continue

            descr = submission.selftext

            # Make sure the description and title are not too long
            if len(descr) > 280:
                descr = descr[:280] + "..."

            title = submission.title
            if len(title) > 250:
                title = title[:250] + "..."

            # Add images to the embed
            img_url = []
            video = False
            if not submission.is_self:
                url = submission.url
                print(url)
                if url.endswith(".jpg") or url.endswith(".png") or url.endswith(".gif"):
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
                timestamp=datetime.datetime.utcfromtimestamp(submission.created_utc),
            )
            if img_url:
                e.set_image(url=img_url[0])

            e.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)
            e.set_thumbnail(
                url="https://styles.redditmedia.com/t5_2th52/styles/communityIcon_wzrl8s0hx8a81.png?width=256&s=dcbf830170c1e8237335a3f046b36f723c5d55e7"
            )

            e.add_field(
                name="Score", value=submission.score, inline=True,
            )

            e.add_field(
                name="Comments", value=submission.num_comments, inline=True,
            )

            e.set_footer(
                text="Hottest posts on r/wallstreetbets",
                icon_url="https://external-preview.redd.it/iDdntscPf-nfWKqzHRGFmhVxZm4hZgaKe5oyFws-yzA.png?width=640&crop=smart&auto=webp&s=bfd318557bf2a5b3602367c9c4d9cd84d917ccd5",
            )

            msg = await channel.send(embed=e)

            for i in range(len(img_url)):
                if i > 0:
                    await channel.send(reference=msg, content=img_url[i])

            if video:
                await channel.send(reference=msg, content=url + "/DASH_360.mp4")


def setup(bot):
    bot.add_cog(Reddit(bot))
