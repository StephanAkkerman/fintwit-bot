##> Imports
# > Discord dependencies
from discord.ext import commands

class On_member_join(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member) -> None:
        """ Sends a private message to the member when they join the server """
        
        await member.send("""Welcome to the server! You can use `/help` to get a list of all commands available to you.
For more information about a specific command, use `/help <command>`.
Be sure to add your portfolio API read-only keys to your profile using `/portfolio`.""")

def setup(bot):
    bot.add_cog(On_member_join(bot))
