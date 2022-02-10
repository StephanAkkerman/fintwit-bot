# Standard libraries
import datetime
import asyncio

# > 3rd party dependencies
import asyncpraw

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, get_channel

class Reddit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        reddit = asyncpraw.Reddit(client_id=config["REDDIT"]["PERSONAL_USE"], \
                     client_secret=config["REDDIT"]["SECRET"], \
                     user_agent=config["REDDIT"]["APP_NAME"], \
                     username=config["REDDIT"]["USERNAME"], \
                     password=config["REDDIT"]["PASSWORD"])

        self.wsb.start(reddit)

    @loop(hours=12)
    async def wsb(self, reddit):
        channel = get_channel(self.bot, config["SUBREDDIT"]["WALLSTREETBETS"]["CHANNEL"])

        em = discord.Embed(
                title="Hottest r/wallstreetbets posts of the last 24 hours",
                url="https://www.reddit.com/r/wallstreetbets/",
                description="The 10 hottest posts of the last 12 hours on r/wallstreetbets are posted below!",
                color=0xFF3F18,
                timestamp=datetime.datetime.utcnow()
            )
        em.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)
        em.set_thumbnail(url="https://styles.redditmedia.com/t5_2th52/styles/communityIcon_wzrl8s0hx8a81.png?width=256&s=dcbf830170c1e8237335a3f046b36f723c5d55e7")

        await channel.send(embed=em)

        subreddit = await reddit.subreddit('WallStreetBets')
        async for submission in subreddit.hot(limit=10):
            

            descr = submission.selftext
            if len(descr) > 280:
                descr = descr[:280] + "..."

            e = discord.Embed(
                title=submission.title,
                url=submission.url,
                description=descr,
                color=0xFF3F18,
                timestamp=datetime.datetime.utcfromtimestamp(submission.created_utc)
            )
            e.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)
            e.set_thumbnail(url="https://styles.redditmedia.com/t5_2th52/styles/communityIcon_wzrl8s0hx8a81.png?width=256&s=dcbf830170c1e8237335a3f046b36f723c5d55e7")

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

            await channel.send(embed=e)

def setup(bot):
    bot.add_cog(Reddit(bot))

