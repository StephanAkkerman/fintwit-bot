##> Imports
# > 3rd Party Dependencies
from discord.ext import commands
from discord.commands import Option

# Local dependencies
from util.vars import get_json_data, bearer_token, post_json_data, api


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

    async def get_user_id(self, username):
        id = await get_json_data(
            f"https://api.twitter.com/2/users/by/username/{username}?user.fields=id",
            headers={"Authorization": f"Bearer {bearer_token}"},
        )

        return id["data"]["id"]

    @commands.slash_command(name="follow", description="Follow a user on Twitter.")
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
                    #id = await self.get_user_id(user)
                    #response = await post_json_data(f"https://api.twitter.com/2/users/{id}/following",
                    #                                headers={"Authorization": f"Bearer {bearer_token}"}
                    #                                )
                    api.create_friendship(screen_name=user)
                    await ctx.respond(
                        f"You are now following: https://twitter.com/{user}"
                    )
                except Exception:
                    raise commands.UserNotFound(user)
        else:
            raise commands.UserInputError()

    @commands.slash_command(description="Unfollow a user on Twitter.")
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
