## > Imports
# > Standard libaries
from __future__ import annotations
from typing import Optional, List
import json
import datetime
from traceback import format_exc

# Discord imports
import discord
from discord.ext import commands

# Local dependencies
from util.sentiment_analyis import add_sentiment
from util.ticker_classifier import classify_ticker
from util.vars import filter_dict, get_json_data, bearer_token
from util.disc_util import get_emoji


async def format_tweet(
    raw_data: str | bytes,
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

    #print(as_json)

    # Get the user name
    user = as_json["includes"]["users"][0]["username"]

    # Get other info
    profile_pic = as_json["includes"]["users"][0]["profile_image_url"]

    # Could also use ['id_sr'] instead
    url = f"https://twitter.com/{user}/status/{as_json['data']['conversation_id']}"

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


async def add_quote_tweet(
    quote_data, user_image, user_ticker_list, user_hashtags, user_text, retweeted_user
):

    text, ticker_list, image, hashtags = await standard_tweet_info(
        quote_data["includes"]["tweets"][0], "tweet"
    )

    # Combine the information
    images = user_image + image
    ticker_list = user_ticker_list + ticker_list
    hashtags = user_hashtags + hashtags

    # Add > to show it's a quote
    text = "\n".join(map(lambda line: "> " + line, text.split("\n")))

    text = f"{user_text}\n\n> [@{retweeted_user}](https://twitter.com/{retweeted_user}):\n{text}"

    return text, ticker_list, images, hashtags


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

    retweeted_user = None

    # Check for any referenced tweets
    if "referenced_tweets" in as_json["data"].keys():

        tweet_type = as_json["data"]["referenced_tweets"][0]["type"]

        if tweet_type == "retweeted" or tweet_type == "quoted":
            if len(as_json["includes"]["users"]) > 1:
                retweeted_user = as_json["includes"]["users"][1]["username"]
            else:
                # If the user retweeted themselves
                retweeted_user = as_json["includes"]["users"][0]["username"]

        if tweet_type == "replied_to":
            text, ticker_list, images, hashtags = await standard_tweet_info(
                as_json["data"], tweet_type
            )

        # If it is a retweet change format
        elif tweet_type == "retweeted":
            # If the retweet is a quoted tweet
            if "referenced_tweets" in as_json["includes"]["tweets"][0].keys():
                if (
                    "quoted"
                    == as_json["includes"]["tweets"][0]["referenced_tweets"][0]["type"]
                ):

                    quote_data = await get_json_data(
                        url=f"https://api.twitter.com/2/tweets/{as_json['includes']['tweets'][0]['conversation_id']}?tweet.fields=attachments,entities,conversation_id&expansions=attachments.media_keys,referenced_tweets.id&media.fields=url",
                        headers={"Authorization": f"Bearer {bearer_token}"},
                    )

                    (
                        user_text,
                        user_ticker_list,
                        user_image,
                        user_hashtags,
                    ) = await standard_tweet_info(quote_data["data"], "quoted")

                    text, ticker_list, images, hashtags = await add_quote_tweet(
                        quote_data,
                        user_image,
                        user_ticker_list,
                        user_hashtags,
                        user_text,
                        retweeted_user,
                    )

            # Standaard retweet
            else:
                (text, ticker_list, images, hashtags,) = await standard_tweet_info(
                    as_json["includes"]["tweets"][0], tweet_type
                )

        # Add the user text to it
        elif tweet_type == "quoted":
            (
                user_text,
                user_ticker_list,
                user_image,
                user_hashtags,
            ) = await standard_tweet_info(as_json["data"], tweet_type)

            text, ticker_list, images, hashtags = await add_quote_tweet(
                as_json,
                user_image,
                user_ticker_list,
                user_hashtags,
                user_text,
                retweeted_user,
            )

    # If there is no reference then it is a normal tweet
    else:
        text, ticker_list, images, hashtags = await standard_tweet_info(
            as_json["data"], "tweet"
        )

    return text, ticker_list, images, retweeted_user, hashtags


def get_tweet_img(as_json: dict) -> List[str]:
    images = []

    # Check for images
    if "includes" in as_json.keys():
        if "media" in as_json["includes"].keys():
            for media in as_json["includes"]["media"]:
                if media["type"] == "photo":
                    # Could increase resolution by changing url using width and height
                    images.append(media["url"])

    return images


async def standard_tweet_info(
    as_json: dict, tweet_type: str = "tweet"
) -> tuple[str, List[str], List[str], List[str]]:
    """
    Returns the text, tickers, images, and hashtags of a tweet.

    Parameters
    ----------
    as_json : dict
        The json object of the tweet.
    tweet_type: str
        The type of tweet, can be "quoted", "retweet", "replied_to" or "tweet".

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

    text = as_json["text"]

    # Check for images
    images = get_tweet_img(as_json)

    # Remove image urls and extend other urls
    if "urls" in as_json["entities"].keys():
        for url in as_json["entities"]["urls"]:
            if "media_key" in url.keys():
                text = text.replace(url["url"], "")
                # If there are no images yet, get the image based on conversation id
                if not images:
                    image_data = await get_json_data(
                        url=f"https://api.twitter.com/2/tweets/{as_json['conversation_id']}?expansions=attachments.media_keys&media.fields=url",
                        headers={"Authorization": f"Bearer {bearer_token}"},
                    )
                    images = get_tweet_img(image_data)
            else:
                if tweet_type == "quoted" and url["expanded_url"].startswith(
                    "https://twitter.com"
                ):
                    # If it is a quote and the url is a twitter url, remove it
                    text = text.replace(url["url"], "")
                else:
                    text = text.replace(url["url"], url["expanded_url"])

    tickers = []
    hashtags = []
    # Process hashtags and tickers
    if "cashtags" in as_json["entities"].keys():
        for symbol in as_json["entities"]["cashtags"]:
            tickers.append(f"{symbol['tag'].upper()}")

    # Also check the hashtags
    if "hashtags" in as_json["entities"].keys():
        for symbol in as_json["entities"]["hashtags"]:
            hashtags.append(f"{symbol['tag'].upper()}")

    return text, tickers, images, hashtags


def get_clean_symbols(tickers, hashtags):

    # First remove the duplicates
    symbols = list(set(tickers + hashtags))

    clean_symbols = []

    # Check the filter dict
    for symbol in symbols:

        # Filter beforehand
        if symbol in filter_dict.keys():
            # For instance Ethereum -> ETH
            new_sym = filter_dict[symbol]
            # However if ETH is in there we do not want to have it twice
            if new_sym not in clean_symbols:
                clean_symbols.append(new_sym)
        else:
            clean_symbols.append(symbol)

    return clean_symbols


def format_description(AH: bool, change: list, price: list, website: str, i : int) -> str:
    if AH:
        return f"[AH: ${price[i]}\n({change[i]})]({website})\n"
    else:
        return f"[${price[i]}\n({change[i]})]({website})"


def get_description(change, price, website):
    # Change can be a list (if the information is from Yahoo Finance) or a string
    if type(change) == list:
        # If the length is 2 then we know the after-hour prices
        if len(change) == 2:
            for i in range(len(change)):
                if i == 0:
                    description = format_description(True, change, price, website, i)
                else:
                    description += format_description(False, change, price, website, i)
        else:
            return format_description(False, change, price, website, 0)

    else:
        return format_description(False, [change], [price], website, 0)

    return description


async def add_financials(
    e: discord.Embed,
    tickers: List[str],
    hashtags: List[str],
    text: str,
    user: str,
    bot: commands.Bot,
) -> tuple[discord.Embed, str, str, List[str], List[str]]:
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
    tuple[discord.Embed, str, str]
        discord.Embed
            The embed with the data added.
        str
            The category of the tweet.
        str
            The sentiment of the tweet.
        List[str]
            The base symbols of the tickers.
        List[str]
            The category of each ticker.
    """

    # In case multiple tickers get send
    crypto = 0
    stocks = 0

    # Get the unique values
    symbols = get_clean_symbols(tickers, hashtags)

    base_symbols = []
    categories = []

    for ticker in symbols:

        if crypto > stocks:
            majority = "crypto"
        elif crypto < stocks:
            majority = "stocks"
        else:
            majority = "Unknown"

        # Get the information about the ticker
        ticker_info = await classify_ticker(ticker, majority)

        if ticker_info:
            (
                _,
                website,
                exchanges,
                price,
                change,
                four_h_ta,
                one_d_ta,
                base_symbol,
            ) = ticker_info

            # Skip if this ticker has been done before, for instance in tweets containing Solana and SOL
            if base_symbol in base_symbols:
                continue

        else:
            if ticker in tickers:

                e.add_field(name=f"${ticker}", value=majority)
                print(
                    f"No crypto or stock match found for ${ticker} in {user}'s tweet at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )

            # Go to next in symbols
            continue

        title = f"${ticker}"

        # Determine if this is a crypto or stock
        if website:
            if "coingecko" in website:
                crypto += 1
                categories.append("crypto")
                if exchanges:
                    if "Binance" in exchanges:
                        title = f"{title} {get_emoji(bot, 'binance')}"
                    if "KuCoin" in exchanges:
                        title = f"{title} {get_emoji(bot, 'kucoin')}"

            if "yahoo" in website:
                stocks += 1
                categories.append("stocks")
        else:
            # Default category is crypto
            categories.append("crypto")

        # Add the field with hyperlink
        e.add_field(
            name=title, value=get_description(change, price, website), inline=True
        )

        if four_h_ta is not None:
            e.add_field(name="4h TA", value=four_h_ta, inline=True)

        if one_d_ta is not None:
            e.add_field(name="1d TA", value=one_d_ta, inline=True)

        base_symbols.append(base_symbol)

    # Finally add the sentiment to the embed
    if symbols:
        e, prediction = add_sentiment(e, text)
    else:
        prediction = None

    # Decide the category of this tweet
    if crypto == 0 and stocks == 0:
        category = None
    elif crypto >= stocks:
        category = "crypto"
    elif crypto < stocks:
        category = "stocks"

    # Return just the prediction without emoji
    return e, category, prediction, base_symbols, categories


async def count_tweets(ticker: str) -> int:
    """
    Counts the number of tweets for a ticker during the last 24 hours.
    https://developer.twitter.com/en/docs/twitter-api/tweets/counts/api-reference/get-tweets-counts-recent
    Max 300 requests per 15 minutes, so 20 requests per minute.

    Parameters
    ----------
    ticker : str
        The ticker to count the tweets for.

    Returns
    -------
    int
        Returns the number of tweets for the ticker.
    """

    # Count the last 24 hours
    # Can add -is:retweet in query param to exclude retweets
    start_time = (
        datetime.datetime.utcnow() - datetime.timedelta(days=1)
    ).isoformat() + "Z"
    url = f"https://api.twitter.com/2/tweets/counts/recent?query={ticker}&granularity=day&start_time={start_time}"
    counts = await get_json_data(
        url=url, headers={"Authorization": f"Bearer {bearer_token}"}
    )

    return counts["meta"]["total_tweet_count"]
