import datetime
import json
import re

import discord
import pandas as pd
from bs4 import BeautifulSoup
from discord.ext import commands
from discord.ext.tasks import loop

import util.vars
from util.db import update_db
from util.disc_util import get_channel, get_tagged_users
from util.vars import config, data_sources, get_json_data


def crypto_parser(soup: BeautifulSoup) -> pd.DataFrame:
    content = soup.find("div", class_=re.compile(r"^listContainer-"))

    # The information will be saved in these lists
    titleList = []
    descriptionList = []
    labelList = []
    timeFrameList = []  # missing
    symbolList = []
    timestampList = []
    commentsList = []
    imageUrlList = []
    likesList = []
    urlList = []

    for article in content.find_all("article"):
        # Get the title and description of the article
        text_block = article.find("div", class_=re.compile(r"^text-block-"))
        title = text_block.find("a", class_=re.compile(r"^title-"))
        url = title.get("href")
        title = title.text
        description = text_block.find("a", class_=re.compile(r"^paragraph-")).text

        # Limit description to 4096 characters
        description = description[:4096]

        # Get the image
        preview = article.find("div", class_=re.compile(r"^preview-grid-"))
        img = preview.find("img", class_=re.compile(r"^image-"))["src"]
        symbol = preview.find("a", class_=re.compile(r"^logo-icon-"))["href"].replace(
            "/symbols/", ""
        )[:-1]
        label = preview.find("span", class_=re.compile(r"^idea-strategy-"))
        if label:
            label = label.text
        else:
            label = "Neutral"

        # Get the other info
        section = article.find("div", class_=re.compile(r"^section-"))
        author = section.find("a")["data-username"]
        publish_date = section.find("time")["datetime"]
        publish_date = datetime.datetime.fromisoformat(
            publish_date.replace("Z", "+00:00")
        )

        likes = section.find("button", class_=re.compile(r"^boostButton-")).text
        comments = section.find("span", class_=re.compile(r"^content-"))
        if comments:
            comments = comments.get("data-overflow-tooltip-text", 0)
        else:
            comments = 0

        # Append the information to the lists
        titleList.append(title)
        descriptionList.append(description)
        labelList.append(label)
        symbolList.append(symbol)
        timestampList.append(publish_date)
        commentsList.append(comments)
        imageUrlList.append(img)
        likesList.append(likes)
        urlList.append(url)
        timeFrameList.append("")

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

    if type == "crypto":
        url = "https://www.tradingview.com/markets/cryptocurrencies/ideas/"
    elif type == "forex":
        url = "https://www.tradingview.com/markets/currencies/ideas/"
    else:
        url = "https://www.tradingview.com/ideas/stocks/"

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
    response = await get_json_data(url, text=True)

    # The response is a HTML page
    soup = BeautifulSoup(response, "html.parser")

    if type == "crypto":
        return crypto_parser(soup)

    # Find all divs with the following class
    content = soup.find(
        "div",
        class_="tv-card-container__ideas tv-card-container__ideas--with-padding js-balance-content",
    )

    if content is None:
        print(f"No content found for {type} ideas")
        return pd.DataFrame()

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
            if symbol_info.a:
                symbolList.append(symbol_info.a.text)
            elif symbol_info.span:
                symbolList.append(symbol_info.span.text)
            else:
                symbolList.append(None)
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

    def add_id_to_db(self, id: str) -> None:
        """
        Adds the given id to the database.
        """

        util.vars.ideas_ids = pd.concat(
            [
                util.vars.ideas_ids,
                pd.DataFrame(
                    [
                        {
                            "id": id,
                            "timestamp": datetime.datetime.now(),
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

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

        # Get the database
        if not util.vars.ideas_ids.empty:
            # Set the types
            util.vars.ideas_ids = util.vars.ideas_ids.astype(
                {
                    "id": str,
                    "timestamp": "datetime64[ns]",
                }
            )

            # Only keep ids that are less than 72 hours old
            util.vars.ideas_ids = util.vars.ideas_ids[
                util.vars.ideas_ids["timestamp"]
                > datetime.datetime.now() - datetime.timedelta(hours=72)
            ]

        counter = 1
        for _, row in df.iterrows():
            if not util.vars.ideas_ids.empty:
                if row["Url"] in util.vars.ideas_ids["id"].tolist():
                    counter += 1
                    continue

            self.add_id_to_db(row["Url"])

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
                text=f"👍 {row['Likes']} | 💬 {row['Comments']}",
                icon_url=data_sources["tradingview"]["icon"],
            )

            if type == "stocks":
                channel = self.stocks_channel
            elif type == "crypto":
                channel = self.crypto_channel
            elif type == "forex":
                channel = self.forex_channel

            await channel.send(content=get_tagged_users([row["Symbol"]]), embed=e)

            counter += 1

            # Only show the top 10 ideas
            if counter == 11:
                break
        # Write to db
        update_db(util.vars.ideas_ids, "ideas_ids")

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
