from __future__ import annotations

import datetime
import json
import re

import pandas as pd
from bs4 import BeautifulSoup

from api.http_client import get_json_data
from constants.logger import logger


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
        logger.warn(f"No content found for {type} ideas")
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
