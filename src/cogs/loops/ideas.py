## > Imports

# > Standard library
import datetime

# > 3rd party dependencies
import json
import pandas as pd
from bs4 import BeautifulSoup

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# > Local dependencies
from util.vars import get_json_data, config
from util.disc_util import get_channel, get_tagged_users


async def scraper(type: str) -> pd.DataFrame:
    """
    Extract the front page of trading ideas on TradingView.
    Written by: https://github.com/mnwato/tradingview-scraper.

    Parameters
    ----------
    type : string
        Specify the type of trading ideas to scrape, either "stocks" or "crypto".

    Returns
    -------
    pd.DataFrame
        A dataframe with the ideas of the specified symbol.
    """

    # The information will be saved in these lists
    titleList = []
    descriptionList = []
    labelList = []
    timeFrameList = []
    symbolList = []
    timestampList = []
    commentsList = []
    imageUrlList = []
    likesList = []
    urlList = []

    # Fetch the page as text
    response = await get_json_data(
        f"https://www.tradingview.com/ideas/{type}/", text=True
    )

    # The response is a HTML page
    soup = BeautifulSoup(response, "html.parser")

    # Find all divs with the following class
    content = soup.find(
        "div",
        class_="tv-card-container__ideas tv-card-container__ideas--with-padding js-balance-content",
    )

    # Save the Timestamps
    for time_upd in content.find_all("span", class_="tv-card-stats__time js-time-upd"):
        timestampList.append(
            datetime.datetime.fromtimestamp(
                float(time_upd["data-timestamp"]), tz=datetime.timezone.utc
            )
        )

    for img_row in content.find_all("div", class_="tv-widget-idea__cover-wrap"):
        # Get the image url
        imageUrlList.append(img_row.find("img")["data-src"])

    # Save their social info in the list
    for social_row in content.find_all(
        "div", class_="tv-social-row tv-widget-idea__social-row"
    ):
        social_info = json.loads(social_row["data-model"])

        commentsList.append(social_info["commentsCount"])
        likesList.append(social_info["agreesCount"])
        urlList.append(f"https://www.tradingview.com{social_info['publishedUrl']}")

    # Save the titles in the list
    for title_row in content.find_all("div", class_="tv-widget-idea__title-row"):
        titleList.append(title_row.a.get_text())

    for description_row in content.find_all(
        "p",
        class_="tv-widget-idea__description-row tv-widget-idea__description-row--clamped js-widget-idea__popup",
    ):
        descriptionList.append(description_row.get_text())

    # Get the Labels, timeFrame and Symbol
    for info_row in content.find_all("div", class_="tv-widget-idea__info-row"):

        if "type-long" in str(info_row):
            label = "Long"
        elif "type-short" in str(info_row):
            label = "Short"
        else:
            label = "Neutral"

        labelList.append(label)

        symbol_info = info_row.find("div", class_="tv-widget-idea__symbol-info")

        if symbol_info:
            symbolList.append(symbol_info.a.text)
        else:
            symbolList.append(None)

        timeFrameList.append(
            info_row.find_all("span", class_="tv-widget-idea__timeframe")[1].text
        )

    data = {
        "Timestamp": timestampList,
        "Title": titleList,
        "Description": descriptionList,
        "Symbol": symbolList,
        "Timeframe": timeFrameList,
        "Label": labelList,
        "Url": urlList,
        "ImageURL": imageUrlList,
        "Likes": likesList,
        "Comments": commentsList,
    }

    return pd.DataFrame(data)


class TradingView_Ideas(commands.Cog):
    """
    This class contains the cog for posting the latest Trading View ideas.
    It can be enabled / disabled in the config under ["LOOPS"]["TV_IDEAS"].

    Methods
    -------
    send_embed(df: pd.DataFrame, type: str) -> None:
        This function creates and sends the embed with the latest ideas.
    crypto_ideas() -> None:
        Manages the loop for the crypto ideas.
    stock_ideas() -> None
        Manages the loop for the stock ideas.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["IDEAS"]["CRYPTO"]["ENABLED"]:
            self.crypto_channel = get_channel(
                self.bot,
                config["LOOPS"]["IDEAS"]["CHANNEL"],
                config["CATEGORIES"]["CRYPTO"],
            )

            self.crypto_ideas.start()

        if config["LOOPS"]["IDEAS"]["STOCKS"]["ENABLED"]:
            self.stocks_channel = get_channel(
                self.bot,
                config["LOOPS"]["IDEAS"]["CHANNEL"],
                config["CATEGORIES"]["STOCKS"],
            )

            self.stock_ideas.start()

        if config["LOOPS"]["IDEAS"]["FOREX"]["ENABLED"]:
            self.forex_channel = get_channel(
                self.bot,
                config["LOOPS"]["IDEAS"]["CHANNEL"],
                config["CATEGORIES"]["FOREX"],
            )

            self.forex_ideas.start()

    async def send_embed(self, df: pd.DataFrame, type: str) -> None:
        """
        Creates an embed based on the given DataFrame and type.
        Then sends this embed in the designated channel.

        Parameters
        ----------
        df : pd.DataFrame
            The dataframe with the ideas.
        type : str
            The type of ideas, either "stocks" or "crypto".

        Returns
        -------
        None
        """

        for i, row in df.iterrows():
            
            # Only show the top 10 ideas
            if i == 9:
                break

            if row["Label"] == "Long":
                color = 0x3CC474
            elif row["Label"] == "Short":
                color = 0xE40414
            else:
                color = 0x808080

            e = discord.Embed(
                title=row["Title"],
                url=row["Url"],
                description=row["Description"],
                color=color,
                timestamp=row["Timestamp"],
            )

            e.set_image(url=row["ImageURL"])

            e.add_field(
                name="Symbol",
                value=row["Symbol"] if row["Symbol"] is not None else "None",
                inline=True,
            )
            e.add_field(name="Timeframe", value=row["Timeframe"], inline=True)
            e.add_field(name="Prediction", value=row["Label"], inline=True)

            e.set_footer(
                text=f"#{i + 1} | 👍 {row['Likes']} | 💬 {row['Comments']}",
                icon_url="https://s3.tradingview.com/userpics/6171439-Hlns_big.png",
            )

            if type == "stocks":
                channel = self.stocks_channel
            elif type == "crypto":
                channel = self.crypto_channel
            elif type == "forex":
                channel = self.forex_channel

            await channel.send(content=get_tagged_users([row["Symbol"]]), embed=e)

    @loop(hours=24)
    async def crypto_ideas(self) -> None:
        """
        This function posts the crypto Trading View ideas.

        Returns
        -------
        None
        """

        df = await scraper("crypto")
        await self.send_embed(df, "crypto")

    @loop(hours=24)
    async def stock_ideas(self) -> None:
        """
        This function posts the stocks Trading View ideas.

        Returns
        -------
        None
        """

        df = await scraper("stocks")
        await self.send_embed(df, "stocks")

    @loop(hours=24)
    async def forex_ideas(self) -> None:
        """
        This function posts the forex Trading View ideas.

        Returns
        -------
        None
        """

        df = await scraper("currencies")
        await self.send_embed(df, "forex")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(TradingView_Ideas(bot))
