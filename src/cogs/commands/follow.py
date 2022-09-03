##> Imports
# > 3rd Party Dependencies
from discord.ext import commands
from discord.commands import Option, slash_command

# Local dependencies
from util.vars import api


class Follow(commands.Cog):
    """
    This class is used to handle the follow command.
    You can enable / disable this command in the config, under ["COMMANDS"]["FOLLOW"].

    Methods
    -------
    follow(ctx : commands.context.Context, *input : Union[str, tuple])) -> None:
        This method is used to handle the follow command.
    unfollow(ctx : commands.context.Context, *input : Union[str, tuple])) -> None:
        This method is used to handle the unfollow command.
    follow_error(ctx : commands.context.Context, error : Exception) -> None:
        This method is used to handle the errors when using the `!follow` command.
    unfollow_error(ctx : commands.context.Context, error : Exception) -> None:
        This method is used to handle the errors when using the `!unfollow` command.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @slash_command(name="follow", description="Follow a user on Twitter.")
    async def follow(
        self,
        ctx,
        input: Option(str, description="The user you want to follow.", required=True),
    ) -> None:
        """
        Follow Twitter user(s), using their screen name (without @ in front).
        Usage: `!follow [<username>]`.

        Parameters
        ----------
        ctx : commands.context.Context
            The context of the command.
        input : str
            The Twitter username(s) specified after `!follow`.

        Returns
        -------
        None
        """

        if input:
            for user in input.split(" "):
                try:
                    api.create_friendship(screen_name=user)
                    await ctx.respond(
                        f"You are now following: https://twitter.com/{user}"
                    )
                except Exception as e:
                    raise commands.UserNotFound(user)
        else:
            raise commands.UserInputError()

    @slash_command(description="Unfollow a user on Twitter.")
    async def unfollow(
        self,
        ctx: commands.Context,
        input: Option(str, description="The user you want to unfollow.", required=True),
    ) -> None:
        """Unfollow Twitter user(s), using their screen name (without @ in front).
        Usage: `!unfollow [<username>]`.

        Parameters
        ----------
        ctx : commands.context.Context
            The context of the command.
        input : str
            The Twitter username(s) specified after `!unfollow`.

        Returns
        -------
        None
        """

        if input:
            for user in input.split(" "):
                try:
                    api.destroy_friendship(screen_name=user)
                    await ctx.respond(
                        f"You are no longer following: https://twitter.com/{user}"
                    )
                except Exception:
                    raise commands.UserNotFound(user)
        else:
            raise commands.UserInputError()

    @follow.error
    async def follow_error(
        self, ctx: commands.context.Context, error: Exception
    ) -> None:
        if isinstance(error, commands.UserNotFound):
            await ctx.respond(f"{error}")
        elif isinstance(error, commands.UserInputError):
            await ctx.respond(f"You must specify a user to follow!")
        else:
            print(error)
            await ctx.respond(f"An error has occurred. Please try again later.")

    @unfollow.error
    async def unfollow_error(
        self, ctx: commands.context.Context, error: Exception
    ) -> None:
        if isinstance(error, commands.UserNotFound):
            await ctx.respond(f"{error}")
        elif isinstance(error, commands.UserInputError):
            await ctx.respond(f"You must specify a user to follow!")
        else:
            print(error)
            await ctx.respond(f"An error has occurred. Please try again later.")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Follow(bot))
