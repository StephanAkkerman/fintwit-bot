## > Imports
# > Standard libaries
from __future__ import annotations
from typing import Optional, List
import json
import datetime
from traceback import format_exc

# > Third party depedencies
import numpy as np

# Discord imports
import discord
from discord.ext import commands

# Local dependencies
from util.sentimentanalyis import classify_sentiment
from util.ticker import classify_ticker
from util.vars import filter_dict
from util.disc_util import get_emoji


async def get_tweet(
    as_json: dict,
) -> tuple[str, List[str], List[str], Optional[str], List[str]]:
    """
    Returns the info of the tweet that was quote retweeted

    Parameters
    ----------
    as_json : dict
        The json object of the tweet.

    Returns
    -------
    tuple[str, List[str], List[str], Optional[str], List[str]]
        str
            The text of the tweet.
        List[str]
            The tickers in the tweet.
        List[str]
            The images in the tweet.
        Optional[str]
            The user that was retweeted.
        List[str]
            The hashtags in the tweet.
    """

    # Check for quote tweet (combine this with user's text)
    if "quoted_status" in as_json:

        # If it is a retweet change format
        if "retweeted_status" in as_json:
            (
                user_text,
                user_ticker_list,
                user_image,
                user_hashtags,
            ) = await standard_tweet_info(as_json["retweeted_status"])
        else:
            (
                user_text,
                user_ticker_list,
                user_image,
                user_hashtags,
            ) = await standard_tweet_info(as_json)

        retweeted_user = as_json["quoted_status"]["user"]["screen_name"]

        text, ticker_list, image, hashtags = await standard_tweet_info(
            as_json["quoted_status"]
        )

        # Combine the information
        images = user_image + image
        ticker_list = user_ticker_list + ticker_list
        hashtags = user_hashtags + hashtags

        # Add > to show it's a quote
        text = "\n".join(map(lambda line: "> " + line, text.split("\n")))

        text = f"{user_text}\n\n> [@{retweeted_user}](https://twitter.com/{retweeted_user}):\n{text}"

    # If retweeted check the extended tweet
    elif "retweeted_status" in as_json:

        text, ticker_list, images, hashtags = await standard_tweet_info(
            as_json["retweeted_status"]
        )
        retweeted_user = as_json["retweeted_status"]["user"]["screen_name"]

    else:
        text, ticker_list, images, hashtags = await standard_tweet_info(as_json)
        retweeted_user = None

    return text, ticker_list, images, retweeted_user, hashtags


async def standard_tweet_info(
    as_json: dict,
) -> tuple[str, List[str], List[str], List[str]]:
    """
    Returns the text, tickers, images, and hashtags of a tweet.

    Parameters
    ----------
    as_json : dict
        The json object of the tweet.

    Returns
    -------
    tuple[str, List[str], List[str], List[str]]
        str
            The text of the tweet.
        List[str]
            The tickers in the tweet.
        List[str]
            The images in the tweet.
        List[str]
            The hashtags in the tweet.
    """

    images = []

    # If the full text is available, use that
    if "extended_tweet" in as_json:
        text = as_json["extended_tweet"]["full_text"]
        ticker_list = as_json["extended_tweet"]["entities"]

        if "urls" in as_json["extended_tweet"]["entities"]:
            for url in as_json["extended_tweet"]["entities"]["urls"]:
                text = text.replace(url["url"], url["expanded_url"])

        # Add the media, check extended entities first
        if "extended_entities" in as_json["extended_tweet"]:
            if "media" in as_json["extended_tweet"]["extended_entities"]:
                for media in as_json["extended_tweet"]["extended_entities"]["media"]:
                    images.append(media["media_url"])
                    text = text.replace(media["url"], "")

    # Not an extended tweet
    else:
        text = as_json["text"]
        ticker_list = as_json["entities"]

        if "urls" in as_json["entities"]:
            for url in as_json["entities"]["urls"]:
                text = text.replace(url["url"], url["expanded_url"])

        if "media" in as_json["entities"]:
            for media in as_json["entities"]["media"]:
                images.append(media["media_url"])
                text = text.replace(media["url"], "")

    tickers = []
    hashtags = []
    # Process hashtags and tickers
    if "symbols" in ticker_list:
        for symbol in ticker_list["symbols"]:
            tickers.append(f"{symbol['text'].upper()}")
        # Also check the hashtags
        for symbol in ticker_list["hashtags"]:
            hashtags.append(f"{symbol['text'].upper()}")

    return text, tickers, images, hashtags


async def format_tweet(
    raw_data: str | bytes, following_ids: List[str]
) -> Optional[
    tuple[str, str, str, str, List[str], List[str], List[str], Optional[str]]
]:
    """
    Gets all the useful infromation from the raw_data.
    Checks if the tweet is from someone we follow.

    Parameters
    ----------
    raw_data : str | bytes
        The raw data of the tweet.
    following_ids : List[str]
        The list of the ids of the people we follow.

    Returns
    -------
    Optional[tuple[str, str, str, str, List[str], List[str], List[str], Optional[str]]]
        str
            The text of the tweet.
        str
            The user that tweeted.
        str
            The url to the user's profile pic.
        str
            The url to the tweet.
        List[str]
            The images in the tweet.
        List[str]
            The tickers in the tweet.
        List[str]
            The hashtags in the tweet.
        Optional[str]
            The user that was retweeted.
    """

    # Convert the string json data to json object
    as_json = json.loads(raw_data)

    # Filter based on users we are following
    # Otherwise shows all tweets (including tweets of people who we are not following)
    if "user" in as_json:
        if as_json["user"]["id"] in following_ids:

            # Ignore replies to other pipo
            # Could instead try: ... or as_json['in_reply_to_user_id'] == as_json['user']['id']
            if (
                as_json["in_reply_to_user_id"] is None
                or as_json["in_reply_to_user_id"] in following_ids
            ):
                # print(as_json)

                # Get the user name
                user = as_json["user"]["screen_name"]

                # Get other info
                profile_pic = as_json["user"]["profile_image_url"]

                # Could also use ['id_sr'] instead
                url = f"https://twitter.com/{user}/status/{as_json['id']}"

                (
                    text,
                    tickers,
                    images,
                    retweeted_user,
                    hashtags,
                ) = await get_tweet(as_json)

                # Replace &amp;
                text = text.replace("&amp;", "&")
                text = text.replace("&gt;", ">")

                # Post the tweet containing the important info
                try:
                    return (
                        text,
                        user,
                        profile_pic,
                        url,
                        images,
                        tickers,
                        hashtags,
                        retweeted_user,
                    )

                except Exception:
                    print(
                        f"Error posting tweet of {user} at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    )
                    print(format_exc())
                    return None


async def add_financials(
    e: discord.Embed,
    tickers: List[str],
    hashtags: List[str],
    text: str,
    user: str,
    bot: commands.Bot,
) -> tuple[discord.Embed, str]:
    """
    Adds the financial data to the embed and returns the corresponding category.

    Parameters
    ----------
    e : discord.Embed
        The embed to add the data to.
    tickers : List[str]
        The tickers in the tweet.
    hashtags : List[str]
        The hashtags in the tweet.
    text : str
        The text of the tweet.
    user : str
        The user that tweeted.
    bot : commands.Bot
        The bot object, used for getting the custom emojis.

    Returns
    -------
    tuple[discord.Embed, str]
        discord.Embed
            The embed with the data added.
        str
            The category of the tweet.
    """

    # In case multiple tickers get send
    crypto = 0
    stocks = 0

    # Get the unique values
    symbols = list(set(tickers + hashtags))

    for ticker in symbols:

        # Filter beforehand
        if ticker in filter_dict.keys():
            ticker = filter_dict[ticker]

            # Skip doubles (for instance $BTC and #Bitocin)
            if ticker in symbols:
                continue

        if crypto > stocks:
            majority = "crypto"
        elif crypto < stocks:
            majority = "stocks"
        else:
            majority = "🤷‍♂️"

        # Get the information about the ticker
        ticker_info = classify_ticker(ticker, majority)

        if ticker_info is not None:
            volume, website, exchanges, price, change, ta = ticker_info
        else:
            # Set everything to None
            volume = website = exchanges = price = change = ta = None

        # Check if there is any volume, and if it is a symbol
        if volume is None:
            if ticker in tickers:

                e.add_field(name=f"${ticker}", value=majority)

                # Go to next in symbols
                print(
                    f"No crypto or stock match found for ${ticker} in {user}'s tweet at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
            continue

        title = f"${ticker}"

        # Determine if this is a crypto or stock
        if website:
            if "coingecko" in website:
                crypto += 1
            if "tradingview" in website or "yahoo" in website:
                stocks += 1

        # Format change
        if type(change) == list:
            if len(change) == 2:
                for i in range(len(change)):
                    if i == 0:
                        description = f"[AH: ${price[i]}\n({change[i]})]({website})\n"
                    else:
                        description += f"[${price[i]}\n({change[i]})]({website})"
            else:
                description = f"[${price[0]}\n({change[0]})]({website})"

        else:
            description = f"[${price}\n({change})]({website})"

            # Currently only adds emojis for crypto exchanges
            if website:
                if "coingecko" in website:
                    if exchanges is not None:
                        if "Binance" in exchanges:
                            title = f"{title} {get_emoji(bot, 'binance')}"
                        if "KuCoin" in exchanges:
                            title = f"{title} {get_emoji(bot, 'kucoin')}"

        # Add the field with hyperlink
        e.add_field(name=title, value=description, inline=True)

        if ta is not None:
            e.add_field(name="4h TA", value=ta, inline=True)

    # If there are any tickers
    if symbols:
        sentiment = classify_sentiment(text)
        prediction = ("🐻 - Bearish", "🦆 - Neutral", "🐂 - Bullish")[np.argmax(sentiment)]
        e.add_field(
            name="Sentiment",
            value=f"{prediction} ({round(max(sentiment*100),2)}%)",
            inline=False,
        )

    # Decide the category of this tweet
    if crypto == 0 and stocks == 0:
        category = None
    elif crypto >= stocks:
        category = "crypto"
    elif crypto < stocks:
        category = "stocks"

    return e, category
