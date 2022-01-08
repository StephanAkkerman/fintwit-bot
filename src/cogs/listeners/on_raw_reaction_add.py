##> Imports
# > Discord dependencies
import discord
from discord.ext import commands

# > Standard libraries
from csv import writer

from vars import get_channel

class On_raw_reaction_add(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, reaction):

        # Ignore private messages
        if reaction.guild_id is None:
            return

        try:
            # Load necessary variables
            channel = self.bot.get_channel(reaction.channel_id)
            message = discord.utils.get(
                await channel.history(limit=100).flatten(), id=reaction.message_id
            )
            if reaction.user_id != self.bot.user.id:
                if str(reaction.emoji) == "🐻" or str(reaction.emoji) == "🐂" or str(reaction.emoji) == "🦆":
                    await self.classify_reaction(reaction, message)
                if str(reaction.emoji) == "💸":
                    await self.highlight(message, reaction.member)

        except commands.CommandError as e:
            print(e)

    async def classify_reaction(self, reaction, message):

        with open("data/sentiment_data.csv", "a", newline="") as file:
            writer_object = writer(file)
            if str(reaction.emoji) == "🐻":
                writer_object.writerow(
                    [message.embeds[0].description.replace("\n", " "), -1]
                )
            elif str(reaction.emoji) == "🐂":
                writer_object.writerow(
                    [message.embeds[0].description.replace("\n", " "), 1]
                )
            elif str(reaction.emoji) == "🦆":
                writer_object.writerow(
                    [message.embeds[0].description.replace("\n", " "), 0]
                )

    async def highlight(self, message, user):
        channel = get_channel(self.bot, "💸┃highlights")
        
        # Get the old embed
        e = message.embeds[0]
        
        user = str(user).split("#")[0]
        e.set_footer(text= f"{e.footer.text} | Highlighted by {user}", icon_url=e.footer.icon_url)
        
        await channel.send(embed=e) 
                
def setup(bot):
    bot.add_cog(On_raw_reaction_add(bot))
