##> Imports
# > Discord dependencies
import discord
from discord.ext import commands

# > Standard libraries
from csv import writer

# Import local dependencies
from vars import config

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
            guild = self.bot.get_guild(reaction.guild_id)
            message = discord.utils.get(await channel.history(limit=100).flatten(), id=reaction.message_id)
            if reaction.user_id != self.bot.user.id:
                if guild.name == config["DEBUG"]["GUILD_NAME"]:
                    await self.classify_reaction(reaction, message)

        except commands.CommandError as e:
            print(e)

    async def classify_reaction(self, reaction, message):

        with open("data/sentiment_data.csv", "a", newline="") as file:
            writer_object = writer(file)
            if str(reaction.emoji) == "🐻":
                writer_object.writerow([message.embeds[0].description.replace("\n"," "), -1])
            elif str(reaction.emoji) == "🐂":
                writer_object.writerow([message.embeds[0].description.replace("\n"," "), 1])
            elif str(reaction.emoji) == "🦆":
                writer_object.writerow([message.embeds[0].description.replace("\n"," "), 0])


def setup(bot):
    bot.add_cog(On_raw_reaction_add(bot))
