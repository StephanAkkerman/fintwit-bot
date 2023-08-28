##> Imports
# > Discord dependencies
import discord
from discord.ext import commands
from discord.commands import Option

from util.disc_util import get_guild


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cmd_dict = {}
        self.guild = None

    @commands.slash_command(description="Receive information about a command.")
    async def help(
        self,
        ctx: commands.Context,
        command: Option(str, description="Command to get help for.", required=False),
    ):
        """
        Receive information about a command or channel
        Usage: `/help <command>`
        List all commands available to you. If you want more information about a specific command, simply type that command after `/help`.


        Parameters
        ----------
        ctx : commands.Context
            The context of the command.
        command : Option, optional
            A specific command, by default it will show all commands, required=False)
        """
        await ctx.response.defer(ephemeral=True)

        if self.cmd_dict == {}:
            self.get_cmd_dict()

        if not self.guild:
            self.guild = get_guild(self.bot)

        # List all commands
        if not command:
            e = discord.Embed(
                title="Available commands",
                color=self.guild.self_role.color,
                description="Use `/help <command>` to get more information about a command!",
            )

            cmd_mentions = []
            cmd_descs = []

            for v in list(self.cmd_dict.values()):
                cmd_mentions.append(v[0])
                cmd_descs.append(v[1])

            e.add_field(name="Commands", value="\n".join(cmd_mentions), inline=True)
            e.add_field(name="Description", value="\n".join(cmd_descs), inline=True)

            await ctx.respond(embed=e)
        else:
            command = command.lower()

            if command in self.cmd_dict.keys():
                e = discord.Embed(
                    title=f"The {command} command",
                    color=self.guild.self_role.color,
                    description="",
                )

                options = []
                for option in self.cmd_dict[command][2]:
                    options.append(f"**{option.name}**: {option.description}")

                e.add_field(name="Command", value=self.cmd_dict[command][0])
                e.add_field(name="Description", value=self.cmd_dict[command][1])
                e.add_field(name="Parameters", value="\n".join(options))
                await ctx.respond(embed=e)
            else:
                await ctx.respond(f"The {command} command was not found.")

    def get_cmd_dict(self):
        self.cmd_dict = {}

        # Iterate through all commands
        for _, cog in self.bot.cogs.items():
            commands = cog.get_commands()
            # https://docs.pycord.dev/en/stable/api.html?highlight=slashcommand#discord.SlashCommand
            for command in commands:
                # https://docs.pycord.dev/en/stable/api.html?highlight=slashcommand#slashcommandgroup
                if type(command) == discord.SlashCommandGroup:
                    for subcommand in command.walk_commands():
                        self.cmd_dict[f"{command.name} {subcommand.name}"] = [
                            subcommand.mention,
                            subcommand.description,
                            subcommand.options,
                        ]

                elif type(command) == discord.SlashCommand:
                    self.cmd_dict[command.name] = [
                        command.mention,
                        command.description,
                        command.options,
                    ]

    # @help.error
    # async def help_error(self, ctx, error):
    #    if isinstance(error, commands.UserInputError):
    #        await ctx.send(
    #            f"Too many arguments given. Correct usage of this command: `!help [command]`."
    #        )
    #    elif isinstance(error, commands.CommandNotFound):
    #        e = discord.Embed(
    #            title="Help",
    #            color=0x00FFFF,
    #            description="This command could not be found... Try `!help` to list all available commands.",
    #        )
    #        await ctx.send(embed=e)
    #    else:


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Help(bot))
