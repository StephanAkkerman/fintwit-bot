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
from util.disc_util import get_channel, tag_user


async def scraper(type: str) -> pd.DataFrame:
    """
    Extract the front page of trading ideas on TradingView.

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
            datetime.datetime.fromtimestamp(float(time_upd["data-timestamp"]))
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

        try:
            sym = info_row.find("div", class_="tv-widget-idea__symbol-info").a.text
        except Exception:
            sym = None

        symbolList.append(sym)
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
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["TV_IDEAS"]["CRYPTO"]["ENABLED"]:
            self.crypto_channel = get_channel(
                self.bot, config["LOOPS"]["TV_IDEAS"]["CRYPTO"]["CHANNEL"]
            )

            self.crypto_ideas.start()

        if config["LOOPS"]["TV_IDEAS"]["STOCKS"]["ENABLED"]:
            self.stocks_channel = get_channel(
                self.bot, config["LOOPS"]["TV_IDEAS"]["STOCKS"]["CHANNEL"]
            )

            self.stock_ideas.start()

    async def send_embed(self, df, type):
        for _, row in df.iterrows():

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

            e.add_field(name="Symbol", value=row["Symbol"], inline=True)
            e.add_field(name="Timeframe", value=row["Timeframe"], inline=True)
            e.add_field(name="Prediction", value=row["Label"], inline=True)

            e.set_footer(
                text=f"👍 {row['Likes']} | 💬 {row['Comments']}",
                icon_url="https://s3.tradingview.com/userpics/6171439-Hlns_big.png",
            )

            if type == "stocks":
                channel = self.stocks_channel
            else:
                channel = self.crypto_channel

            msg = await channel.send(embed=e)

            await tag_user(msg, channel, [row["Symbol"]])

    @loop(hours=24)
    async def crypto_ideas(self) -> None:
        df = await scraper("crypto")
        await self.send_embed(df, "crypto")

    @loop(hours=24)
    async def stock_ideas(self) -> None:
        df = await scraper("stocks")
        await self.send_embed(df, "stocks")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(TradingView_Ideas(bot))
