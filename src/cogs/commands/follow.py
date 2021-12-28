##> Imports
# > 3rd Party Dependencies
import discord
from discord.ext import commands

from vars import api


class Follow(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def follow(self, ctx, *input):
        """ Follow Twitter user(s), using their screen name (without @ in front).
        
        Usage: `!follow [<username>]`
        """

        if input:
            for user in input:
                try:
                    api.create_friendship(screen_name=user)
                    await ctx.send(f"You are now following: https://twitter.com/{user}")
                except Exception as e:
                    raise commands.UserNotFound(user)
        else:
            raise commands.UserInputError()

    @commands.command()
    async def unfollow(self, ctx, *input):
        """ Unfollow Twitter user(s), using their screen name (without @ in front).
        
        Usage: `!unfollow [<username>]`
        """

        if input:
            for user in input:
                try:
                    api.destroy_friendship(screen_name=user)
                    await ctx.send(
                        f"You are no longer following: https://twitter.com/{user}"
                    )
                except Exception:
                    raise commands.UserNotFound(user)
        else:
            raise commands.UserInputError()

    @follow.error
    async def follow_error(self, ctx, error):
        if isinstance(error, commands.UserNotFound):
            await ctx.send(f"{ctx.author.mention} {error}")
        elif isinstance(error, commands.UserInputError):
            await ctx.send(f"{ctx.author.mention} You must specify a user to follow!")
        else:
            await ctx.send(
                f"{ctx.author.mention} An error has occurred. Please try again later."
            )

    @unfollow.error
    async def unfollow_error(self, ctx, error):
        if isinstance(error, commands.UserNotFound):
            await ctx.send(f"{ctx.author.mention} {error}")
        elif isinstance(error, commands.UserInputError):
            await ctx.send(f"{ctx.author.mention} You must specify a user to follow!")
        else:
            await ctx.send(
                f"{ctx.author.mention} An error has occurred. Please try again later."
            )


def setup(bot):
    bot.add_cog(Follow(bot))
