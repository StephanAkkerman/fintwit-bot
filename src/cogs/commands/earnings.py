##> Imports
# > 3rd Party Dependencies
from discord.ext import commands

# Local dependencies
from util.earnings_scraper import YahooEarningsCalendar


class Earnings(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def earnings(self, ctx: commands.Context, stock: str) -> None:

        if input:
            next_earnings = YahooEarningsCalendar().get_next_earnings_date(stock)
            msg = f"The next earnings date for {stock.upper()} is <t:{next_earnings}:R>."
            await ctx.send(msg)
        else:
            raise commands.UserInputError()

    @earnings.error
    async def earnings_error(
        self, ctx: commands.context.Context, error: Exception
    ) -> None:
        print(error)
        if isinstance(error, commands.UserInputError):
            await ctx.send(
                f"{ctx.author.mention} You must specify a stock to request the next earnings of!"
            )
        else:
            await ctx.send(
                f"{ctx.author.mention} An error has occurred. Please try again later."
            )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Earnings(bot))
