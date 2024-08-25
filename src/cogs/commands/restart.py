import os
import sys

from discord.commands.context import ApplicationContext
from discord.ext import commands

from constants.config import config
from util.disc import conditional_role_decorator, log_command_usage


class Restart(commands.Cog):
    """
    This class is used to handle the /restart command.
    You can enable / disable this command in the config, under ["COMMANDS"]["RESTART"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def restart_bot(self):
        os.execv(sys.executable, ["python"] + sys.argv)

    @commands.slash_command(description="Restarts the FinTwit bot.")
    @conditional_role_decorator(config["COMMANDS"]["RESTART"]["ROLE"])
    @log_command_usage
    async def restart(
        self,
        ctx: ApplicationContext,
    ) -> None:
        await ctx.respond("Restarting bot...")
        self.restart_bot()


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Restart(bot))
