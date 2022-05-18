##> Imports
# > 3rd Party Dependencies
from discord.ext import commands

# Local dependencies
from util.vars import api


class Follow(commands.Cog):
    """
    This class is used to handle the follow command.
    You can enable / disable this command in the config, under ["COMMANDS"]["FOLLOW"].
    
    Methods
    -------
    follow(ctx : commands.context.Context, *input : tuple) -> None:
        This method is used to handle the follow command.
    unfollow(ctx : commands.context.Context, *input : tuple) -> None:
        This method is used to handle the unfollow command.
    follow_error(ctx : commands.context.Context, error : Exception) -> None:
        This method is used to handle the errors when using the `!follow` command.
    unfollow_error(ctx : commands.context.Context, error : Exception) -> None:
        This method is used to handle the errors when using the `!unfollow` command.
    """
    
    def __init__(self, bot : commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def follow(self, ctx : commands.Context, *input : tuple) -> None:
        """
        Follow Twitter user(s), using their screen name (without @ in front).
        Usage: `!follow [<username>]`.
        
        Parameters
        ----------
        ctx : commands.context.Context
            The context of the command.
        input : tuple
            The names specified after `!follow`.
        
        Returns
        -------
        None
        """
        
        print(type(input))

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
    async def unfollow(self, ctx : commands.Context, *input : tuple) -> None:
        """Unfollow Twitter user(s), using their screen name (without @ in front).
        Usage: `!unfollow [<username>]`.
        
        Parameters
        ----------
        ctx : commands.context.Context
            The context of the command.
        input : tuple
            The names specified after `!unfollow`.
        
        Returns
        -------
        None
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
    async def follow_error(self, ctx : commands.context.Context, error : Exception) -> None:
        if isinstance(error, commands.UserNotFound):
            await ctx.send(f"{ctx.author.mention} {error}")
        elif isinstance(error, commands.UserInputError):
            await ctx.send(f"{ctx.author.mention} You must specify a user to follow!")
        else:
            await ctx.send(
                f"{ctx.author.mention} An error has occurred. Please try again later."
            )

    @unfollow.error
    async def unfollow_error(self, ctx : commands.context.Context, error : Exception) -> None:
        if isinstance(error, commands.UserNotFound):
            await ctx.send(f"{ctx.author.mention} {error}")
        elif isinstance(error, commands.UserInputError):
            await ctx.send(f"{ctx.author.mention} You must specify a user to follow!")
        else:
            await ctx.send(
                f"{ctx.author.mention} An error has occurred. Please try again later."
            )


def setup(bot : commands.Bot) -> None:
    bot.add_cog(Follow(bot))
