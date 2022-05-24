## > Imports
# > Standard Library
import datetime

# > 3rd Party Dependencies
import pandas as pd
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# > Discord imports
import discord
from discord.ext import commands

# > Local dependencies
from util.vars import get_json_data
from util.confirm_stock import confirm_stock


class Sentiment(commands.Cog):
    """
    This class is used to handle the earnings command.
    You can enable / disable this command in the config, under ["COMMANDS"]["EARNINGS"].

    Methods
    -------
    earnings(ctx : commands.context.Context, stock : str) -> None:
        This method is used to handle the earnings command.
    earnings_error(ctx : commands.context.Context, error : Exception) -> None:
        This method is used to handle the errors when using the `!earnings` command.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def sentiment(self, ctx: commands.Context, stock: str) -> None:
        if input:

            # Check if this stock exists
            if not await confirm_stock(self.bot, ctx, stock):
                return

            news_df = await self.get_news(stock)

            # Get the total mean
            total_mean = news_df["Sentiment"].mean()

            # The mean of the most recent 50 articles
            fifty_mean = news_df["Sentiment"].head(50).mean()

            # The mean of the most recent 10 articles
            ten_mean = news_df["Sentiment"].head(10).mean()

            e = discord.Embed(
                title=f"Sentiment of Latest {stock} News",
                url=f"https://finviz.com/quote.ashx?t={stock}",
                description="",
                color=0xFFFFFF,
                timestamp=datetime.datetime.utcnow(),
            )
            e.set_footer(
                text="\u200b",
                icon_url="https://pbs.twimg.com/profile_images/554978836488540160/rqhRqbgQ_400x400.png",
            )

            # Start by showing the means
            e.add_field(name="Last 10 Mean", value=f"{ten_mean:.2f}", inline=True)
            e.add_field(name="Last 50 Mean", value=f"{fifty_mean:.2f}", inline=True)
            e.add_field(name="Total Mean", value=f"{total_mean:.2f}", inline=True)

            # Display the last 10 articles
            last_5 = news_df.head(5)

            dates = last_5["Date"].dt.strftime("%d/%m/%y").tolist()
            headlines = last_5["Headline"].astype(str).tolist()
            sentiments = last_5["Sentiment"].astype(str).tolist()

            for i in range(5):
                e.add_field(
                    name="Date" if i == 0 else "\u200b", value=dates[i], inline=True
                )
                e.add_field(
                    name="Headline" if i == 0 else "\u200b",
                    value=headlines[i],
                    inline=True,
                )
                e.add_field(
                    name="Sentiment" if i == 0 else "\u200b",
                    value=sentiments[i],
                    inline=True,
                )

            await ctx.send(embed=e)
        else:
            raise commands.UserInputError()

    @sentiment.error
    async def sentiment_error(self, ctx: commands.Context, error: Exception) -> None:
        print(error)

        if isinstance(error, commands.UserInputError):
            await ctx.send(
                f"{ctx.author.mention} You must specify a stock to request the next sentiment of!"
            )
        else:
            await ctx.send(
                f"{ctx.author.mention} An error has occurred. Please try again later."
            )
            

    async def get_news(self, ticker):

        html = await get_json_data(
            url=f"https://finviz.com/quote.ashx?t={ticker}",
            headers={"user-agent": "my-app/0.0.1"},
            text=True,
        )

        # Get everything part of id='news-table'
        html = html[html.find('id="news-table"') :]
        html = html[: html.find("</table>")]

        # Split headlines by <tr> until </tr>
        headlines = html.split("<tr>")[1:]

        text_only = []
        last_date = ""
        dates = []
        sentiment = []

        for headline in headlines:

            date = headline[
                headline.find('style="white-space:nowrap">')
                + len('style="white-space:nowrap">') : headline.find("&nbsp;")
            ]

            if date.startswith('ht">'):
                date = last_date + " " + date[len('ht">') :]
            else:
                last_date = date.split()[0]

            # Month-date-year hour:minute AM/pm
            # For instance May-23-22 11:31PM
            dates.append(datetime.datetime.strptime(date, "%b-%d-%y %I:%M%p"))

            text = headline[
                headline.find('class="tab-link-news">')
                + len('class="tab-link-news">') : headline.find("</a>")
            ].replace("&amp;", "&")

            url = headline[
                headline.find("href=")
                + len("href=")
                + 1 : headline.find('" target="_blank"')
            ]

            text_only.append(f"[{text}]({url})")

            try:
                analyzer = SentimentIntensityAnalyzer()
                sentiment.append(analyzer.polarity_scores(text)["compound"])
            except LookupError:
                # Download the NLTK packages
                nltk.download("vader_lexicon")

                # Try again
                analyzer = SentimentIntensityAnalyzer()
                sentiment.append(analyzer.polarity_scores(text)["compound"])

        return pd.DataFrame(
            {"Date": dates, "Headline": text_only, "Sentiment": sentiment}
        )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Sentiment(bot))
