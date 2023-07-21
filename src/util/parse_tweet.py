import re
from typing import List

# > Local imports
import util.vars


def remove_twitter_url_at_end(text: str) -> str:
    """
    Removes a t.co URL at the end of a text string.

    Parameters
    ----------
    text : str
        The text from which to remove the URL.

    Returns
    -------
    str
        The text with the URL removed.
    """
    pattern = r"(https?://t\.co/\S+)$"
    return re.sub(pattern, "", text)


def get_user_info(tweet: dict, key: str) -> str:
    return tweet["core"]["user_results"]["result"]["legacy"][key]


def get_entities(tweet: dict, key: str) -> List[str]:
    """
    Retrieves entities from a tweet.

    Parameters
    ----------
    tweet : dict
        The tweet from which to retrieve entities.
    key : str
        The key of the entities to retrieve.

    Returns
    -------
    List[str]
        The retrieved entities, or an empty list if the key does not exist.
    """
    entities = tweet["legacy"]["entities"].get(key)
    return [entity["text"] for entity in entities] if entities else []


def parse_tweet(tweet: dict, update_tweet_id: bool = False):
    reply = None

    if "items" in tweet.keys():
        reply = tweet["items"][1]["item"]["itemContent"]["tweet_results"]
        tweet = tweet["items"][0]["item"]["itemContent"]["tweet_results"]

    elif "itemContent" in tweet.keys():
        if "tweet_results" in tweet["itemContent"]:
            tweet = tweet["itemContent"]["tweet_results"]
        else:
            print("Tweet contains no tweet_results key")
            return

    try:
        tweet = tweet["result"]
    except KeyError:
        print("Tweet contains no result key")
        return

    # Ignore Tweets that are older than the latest tweet
    if "legacy" not in tweet:
        tweet_id = int(tweet["tweet"]["rest_id"])
    else:
        tweet_id = int(tweet["legacy"]["id_str"])

    if "core" not in tweet:
        tweet = tweet["tweet"]

    # So we can use this function recursively
    if update_tweet_id:
        # Skip this tweet
        if tweet_id <= util.vars.latest_tweet_id:
            return
        util.vars.latest_tweet_id = tweet_id

    # Get user info
    user_name = get_user_info(tweet, "name")  # The name of the account (not @username)
    user_screen_name = get_user_info(tweet, "screen_name")  # The @username
    user_img = get_user_info(tweet, "profile_image_url_https")

    # Media
    media = []
    if "extended_entities" in tweet["legacy"].keys():
        if "media" in tweet["legacy"]["extended_entities"].keys():
            media = [
                image["media_url_https"]
                for image in tweet["legacy"]["extended_entities"]["media"]
            ]

    # Remove t.co url from text
    text = remove_twitter_url_at_end(tweet["legacy"]["full_text"])

    # Tweet url
    tweet_url = f"https://twitter.com/user/status/{tweet_id}"

    # Tickers
    tickers = get_entities(tweet, "symbols")

    # Hashtags
    hashtags = get_entities(tweet, "hashtags")

    quoted_status_result = tweet.get("quoted_status_result")
    retweeted_status_result = tweet["legacy"].get("retweeted_status_result")

    e_title = f"{user_name} tweeted"

    if quoted_status_result or retweeted_status_result or reply:
        result = quoted_status_result or retweeted_status_result or reply
        (
            r_text,
            r_user_name,
            r_user_screen_name,
            _,
            _,
            r_media,
            r_tickers,
            r_hashtags,
            _,
        ) = parse_tweet(result)

        if reply:
            e_title = f"{util.vars.custom_emojis['reply']} {user_name} replied to {r_user_name}"
            text = "\n".join(map(lambda line: "> " + line, text.split("\n")))
            text = f"> [@{r_user_screen_name}](https://twitter.com/{r_user_screen_name}):\n{text}\n\n{r_text}"

        # Add text on top
        if quoted_status_result:
            e_title = (
                f"{util.vars.custom_emojis['quote_tweet']} {user_name} quote tweeted"
            )
            q_text = "\n".join(map(lambda line: "> " + line, r_text.split("\n")))
            text = f"{text}\n\n> [@{r_user_screen_name}](https://twitter.com/{r_user_screen_name}):\n{q_text}"

        if retweeted_status_result:
            e_title = f"{util.vars.custom_emojis['retweet']} {user_name} retweeted"

        media += r_media
        tickers += r_tickers
        hashtags += r_hashtags

    # Replace &amp; etc.
    text = text.replace("&amp;", "&").replace("&gt;", ">").replace("&lt;", "<")

    # Convert media, tickers, hasthtags to sets to remove duplicates
    media = list(set(media))
    tickers = list(set(tickers))
    hashtags = list(set(hashtags))

    # tickers and hashtags all uppercase
    tickers = [ticker.upper() for ticker in tickers]
    hashtags = [hashtag.upper() for hashtag in hashtags if hashtag != "CRYPTO"]

    # Create the embed title

    return (
        text,
        user_name,
        user_screen_name,
        user_img,
        tweet_url,
        media,
        tickers,
        hashtags,
        e_title,
    )
