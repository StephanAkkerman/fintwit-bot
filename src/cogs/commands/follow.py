##> Imports
# > 3rd Party Dependencies
from discord.ext import commands
from discord.commands import Option
from tweepy.asynchronous import AsyncClient

# Local dependencies
import util.vars


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
        self.client = AsyncClient(
            bearer_token=util.vars.bearer_token,
            consumer_key=util.vars.consumer_key,
            consumer_secret=util.vars.consumer_secret,
            access_token=util.vars.access_token,
            access_token_secret=util.vars.access_token_secret,
            wait_on_rate_limit=True,
        )

    @commands.slash_command(name="follow", description="Follow a user on Twitter.")
    async def follow(
        self,
        ctx,
        user: Option(str, description="The user you want to follow.", required=True),
    ) -> None:
        """
        Follow a Twitter user, using their screen name (without @ in front).
        Usage: `!follow <username>`.

        Parameters
        ----------
        ctx : commands.context.Context
            The context of the command.
        user : str
            The Twitter username specified after `!follow`.

        Returns
        -------
        None
        """

        try:
            id = await self.client.get_user(username=user)
            response = await self.client.follow_user(id.data.id)

            if response.data["following"]:
                await ctx.respond(f"You are now following: https://twitter.com/{user}")
            elif response.data["pending_follow"]:
                await ctx.respond(
                    f"Sent a follow request to: https://twitter.com/{user}"
                )
            else:
                await ctx.respond(f"Something went wrong, please try again later.")

        except Exception:
            raise commands.UserNotFound(user)

    @commands.slash_command(description="Unfollow a user on Twitter.")
    async def unfollow(
        self,
        ctx: commands.Context,
        user: Option(str, description="The user you want to unfollow.", required=True),
    ) -> None:
        """Unfollow Twitter user, using their screen name (without @ in front).
        Usage: `!unfollow <username>`.

        Parameters
        ----------
        ctx : commands.context.Context
            The context of the command.
        user : str
            The Twitter username specified after `!unfollow`.

        Returns
        -------
        None
        """

        try:
            id = await self.client.get_user(username=user)
            response = await self.client.unfollow_user(id.data.id)

            if not response.data["following"]:
                await ctx.respond(
                    f"You are no longer following: https://twitter.com/{user}"
                )
            else:
                await ctx.respond(f"Something went wrong, please try again later.")
        except Exception:
            raise commands.UserNotFound(user)

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
