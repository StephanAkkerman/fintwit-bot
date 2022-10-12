## > Imports
# > Standard Library
import datetime

# > 3rd Party Dependencies
import pandas as pd
from bs4 import BeautifulSoup

# > Discord imports
import discord
from discord.ext import commands
from discord.commands import Option

# > Local dependencies
from util.vars import get_json_data


class Analyze(commands.Cog):
    """ """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.slash_command(
        description="Request the current analysis for a stock ticker."
    )
    async def analyze(
        self,
        ctx: commands.Context,
        stock: Option(str, description="Stock ticker, i.e. AAPL.", required=True),
    ) -> None:

        # await ctx.response.defer(ephemeral=True)

        req = await get_json_data(
            f"https://www.benzinga.com/quote/{stock}/analyst-ratings", text=True
        )

        soup = BeautifulSoup(req, "html.parser")

        table_div = soup.find(
            "div", {"class": "analyst-ratings__AggegrateTableContainer-ckk206-1 hBEyHZ"}
        )
        table = table_div.find("table")

        headers = []
        for row in table.find_all("th"):
            headers.append(row.text)

        data = []
        for row in table.find_all("td"):
            data.append(row.text)

        e = discord.Embed(
            title=f"{stock.upper()} Analysist Rating Summary ",
            url=f"https://www.benzinga.com/quote/{stock}/analyst-ratings",
            description="",
            color=0x1F7FC1,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        e.set_footer(
            text="\u200b",
            icon_url="https://www.benzinga.com/next-assets/images/apple-touch-icon.png",
        )

        for i in range(len(headers)):
            e.add_field(name=headers[i], value=data[i], inline=True)

        await ctx.respond(embed=e)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Analyze(bot))
