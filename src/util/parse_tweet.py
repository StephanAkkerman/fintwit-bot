import re
from typing import List, Tuple, Optional

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


def get_legacy_info(tweet: dict, key: str) -> Optional[str]:
    """
    Retrieves legacy information from a tweet.

    Parameters
    ----------
    tweet : dict
        The tweet from which to retrieve information.
    key : str
        The key of the information to retrieve.

    Returns
    -------
    Optional[str]
        The retrieved information, or None if the key does not exist.
    """
    return tweet["core"]["user_results"]["result"]["legacy"].get(key)


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


def parse_tweet(
    tweet: dict, update_tweet_id: bool = False
) -> Tuple[str, str, str, str, str, List[str], List[str], List[str], Optional[str]]:
    """
    Parses a tweet and returns a tuple with all important information.

    Parameters
    ----------
    tweet : dict
        The tweet to parse.
    update_tweet_id : bool, optional
        If this Tweet should update the database, by default False.

    Returns
    -------
    Tuple[str, str, str, str, str, List[str], List[str], List[str], Optional[str]]
        The parsed tweet.
    """
    reply = None

    if "items" in tweet:
        reply = tweet["items"][1]["item"]["itemContent"].get("tweet_results")
        tweet = tweet["items"][0]["item"]["itemContent"].get("tweet_results")
    elif "itemContent" in tweet:
        tweet = tweet["itemContent"].get("tweet_results")

    tweet = tweet.get("result")

    tweet_id = int(tweet.get("legacy", {}).get("id_str", tweet["tweet"]["rest_id"]))

    if update_tweet_id:
        if tweet_id <= util.vars.latest_tweet_id:
            return
        util.vars.latest_tweet_id = tweet_id

    tweet = tweet.get("core", tweet)

    user_name = get_legacy_info(tweet, "name")
    user_screen_name = get_legacy_info(tweet, "screen_name")
    user_img = get_legacy_info(tweet, "profile_image_url_https")

    media = []
    if "extended_entities" in tweet["legacy"]:
        media = [
            image["media_url_https"]
            for image in tweet["legacy"]["extended_entities"].get("media", [])
        ]

    text = tweet["legacy"]["full_text"]
    text = remove_twitter_url_at_end(text)

    tweet_url = f"https://twitter.com/user/status/{tweet_id}"

    tickers = get_entities(tweet, "symbols")
    hashtags = get_entities(tweet, "hashtags")

    quoted_status_result = tweet.get("quoted_status_result")
    retweeted_status_result = tweet["legacy"].get("retweeted_status_result")

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

        text = "\n".join(map(lambda line: "> " + line, text.split("\n")))
        text = f"> [@{r_user_screen_name}](https://twitter.com/{r_user_screen_name}):\n{text}\n\n{r_text}"

        media += r_media
        tickers += r_tickers
        hashtags += r_hashtags

    text = text.replace("&amp;", "&").replace("&gt;", ">").replace("&lt;", "<")

    media = list(set(media))
    tickers = list(set(tickers))
    hashtags = list(set(hashtags))

    tickers = [ticker.upper() for ticker in tickers]
    hashtags = [hashtag.upper() for hashtag in hashtags if hashtag != "CRYPTO"]

    return (
        text,
        user_name,
        user_screen_name,
        user_img,
        tweet_url,
        media,
        tickers,
        hashtags,
        r_user_name if reply else None,
    )
