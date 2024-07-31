## > Imports
# > Standard Library
import datetime
import traceback
from io import StringIO

# > Discord imports
import discord
import nltk

# > 3rd Party Dependencies
import pandas as pd
from discord.commands import Option
from discord.commands.context import ApplicationContext
from discord.ext import commands
from nltk.sentiment.vader import SentimentIntensityAnalyzer

from util.confirm_stock import confirm_stock

# > Local dependencies
from util.vars import data_sources, get_json_data, logger

# Initialize variables
today_date = datetime.datetime.now().date()
current_date = today_date


def convert_to_datetime(date_str):
    global current_date

    if "Today" in date_str:
        time_str = date_str.replace("Today ", "")
        datetime_str = f"{today_date} {time_str}"
    elif any(
        month in date_str
        for month in [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]
    ):
        datetime_obj = datetime.datetime.strptime(date_str, "%b-%d-%y %I:%M%p")
        current_date = datetime_obj.date()
        return datetime_obj
    else:
        time_str = date_str
        datetime_str = f"{current_date} {time_str}"

    return datetime.datetime.strptime(datetime_str, "%Y-%m-%d %I:%M%p")


class Sentiment(commands.Cog):
    """
    This class is used to handle the sentiment command.
    You can enable / disable this command in the config, under ["COMMANDS"]["SENTIMENT"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.slash_command(
        description="Request the current sentiment for a stock ticker."
    )
    async def sentiment(
        self,
        ctx: ApplicationContext,
        stock: Option(str, description="Stock ticker, i.e. AAPL.", required=True),
    ) -> None:
        """
        This method is used to handle the sentiment command.
        Usage: `!sentiment <stock ticker>` for instance `!sentiment AAPL`.

        Parameters
        ----------
        ctx : commands.context.Context
            The context of the command.
        stock : str
            The stock ticker, i.e. AAPL. Specified at the end of the command.

        Returns
        -------
        None
        """

        await ctx.response.defer(ephemeral=True)

        # Check if this stock exists
        if not await confirm_stock(self.bot, ctx, stock):
            return

        news_df = await self.get_sentiment(stock)

        # Get the total mean
        total_mean = news_df["Sentiment"].mean()

        # The mean of the most recent 50 articles
        fifty_mean = news_df["Sentiment"].head(50).mean()

        # The mean of the most recent 10 articles
        ten_mean = news_df["Sentiment"].head(10).mean()

        e = discord.Embed(
            title=f"Sentiment of Latest {stock.upper()} News",
            url=f"https://finviz.com/quote.ashx?t={stock}",
            description="",
            color=data_sources["finviz"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        e.set_footer(
            text="\u200b",
            icon_url=data_sources["finviz"]["icon"],
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

        await ctx.followup.send(embed=e)

    @sentiment.error
    async def sentiment_error(self, ctx: ApplicationContext, error: Exception) -> None:
        """
        Catches the errors when using the `!sentiment` command.

        Parameters
        ----------
        ctx : commands.Context
            The context of the command.
        error : Exception
            The exception that was raised when using the `!sentiment` command.
        """
        logger.error(error)
        logger.debug(traceback.format_exc())
        await ctx.respond("An error has occurred. Please try again later.")

    async def get_finviz_data(self, ticker: str) -> pd.DataFrame:
        """
        Get the latest news for a given stock ticker.

        Parameters
        ----------
        ticker : str
            The stock ticker to get the news for.

        Returns
        -------
        pd.DataFrame
            The latest news for a given stock ticker.
        """

        html = await get_json_data(
            url=f"https://finviz.com/quote.ashx?t={ticker}",
            headers={
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36"
            },
            text=True,
        )

        df = pd.read_html(StringIO(html))[-3]

        # Set column names
        df.columns = ["Date", "Headline"]

        # Convert the date column
        df["Date"] = df["Date"].apply(convert_to_datetime)

        return df

    async def get_sentiment(self, ticker: str) -> pd.DataFrame:
        """
        Calculate the sentiment for a given stock ticker.

        Parameters
        ----------
        ticker : str
            The stock ticker to get the news for.

        Returns
        -------
        pd.DataFrame
            The latest news for a given stock ticker.
        """

        df = await self.get_finviz_data(ticker)
        text = df["Headline"].tolist()
        sentiment = []

        # Calculate the sentiment for each headline
        for text in text:
            # Check if the NLTK packages are installed
            try:
                analyzer = SentimentIntensityAnalyzer()
                sentiment.append(analyzer.polarity_scores(text)["compound"])
            except LookupError:
                # Download the NLTK packages
                nltk.download("vader_lexicon")

                # Try again
                analyzer = SentimentIntensityAnalyzer()
                sentiment.append(analyzer.polarity_scores(text)["compound"])

        # Add the sentiment to the dataframe
        df["Sentiment"] = sentiment

        return df


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Sentiment(bot))
