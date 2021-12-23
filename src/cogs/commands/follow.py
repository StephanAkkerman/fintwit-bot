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
        """ Follow a Twitter user, using their screen name (without @ in front).
        
        Usage: `!follow @<username>`
        """
        
        if len(input) == 1:
            try:
                api.create_friendship(screen_name = input[0])
                await ctx.send(f"{ctx.author.mention} You are now following {input[0]}")
            except Exception as e:
                print(e)
                raise commands.UserNotFound(input[0])
        else:
            raise commands.UserInputError()
        
    @commands.command()
    async def unfollow(self, ctx, *input):
        """ Unfollow a Twitter user, using their screen name (without @ in front).
        
        Usage: `!unfollow <username>`
        """
        
        if len(input) == 1:
            try:
                api.destroy_friendship(screen_name = input[0])
                await ctx.send(f"{ctx.author.mention} You are no longer following {input[0]}")
            except Exception:
                raise commands.UserNotFound(input[0])
        else:
            raise commands.UserInputError()
        
    @follow.error
    async def follow_error(self, ctx, error):
        if isinstance(error, commands.UserNotFound):
            await ctx.send(f"{ctx.author.mention} {error}")
        elif isinstance(error, commands.UserInputError):
            await ctx.send(f"{ctx.author.mention} You must specify a user to follow!")
        else:
            await ctx.send(f"{ctx.author.mention} An error has occurred. Please try again later.")
            
    @unfollow.error
    async def unfollow_error(self, ctx, error):
        if isinstance(error, commands.UserNotFound):
            await ctx.send(f"{ctx.author.mention} {error}")
        elif isinstance(error, commands.UserInputError):
            await ctx.send(f"{ctx.author.mention} You must specify a user to follow!")
        else:
            await ctx.send(f"{ctx.author.mention} An error has occurred. Please try again later.")


def setup(bot):
    bot.add_cog(Follow(bot))
        