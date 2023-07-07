import re

import util.vars


def remove_twitter_url_at_end(text):
    pattern = r"(https?://t\.co/\S+)$"  # Regular expression pattern to match t.co URLs at the end
    return re.sub(pattern, "", text)


def parse_tweet(tweet: dict, update_tweet_id: bool = False):
    reply = None

    if "items" in tweet.keys():
        reply = tweet["items"][1]["item"]["itemContent"]["tweet_results"]
        tweet = tweet["items"][0]["item"]["itemContent"]["tweet_results"]

    elif "itemContent" in tweet.keys():
        if "tweet_results" in tweet["itemContent"]:
            tweet = tweet["itemContent"]["tweet_results"]
        else:
            print(tweet)

    # Ignore Tweets that are
    tweet_id = int(tweet["result"]["legacy"]["id_str"])

    # So we can use this function recursively
    if update_tweet_id:
        # Skip this tweet
        if tweet_id <= util.vars.latest_tweet_id:
            return
        util.vars.latest_tweet_id = tweet_id

    # Default is no retweet
    retweeted_user = None

    # Get user info
    user_name = tweet["result"]["core"]["user_results"]["result"]["legacy"]["name"]
    user_screen_name = tweet["result"]["core"]["user_results"]["result"]["legacy"][
        "screen_name"
    ]  # The @username
    user_img = tweet["result"]["core"]["user_results"]["result"]["legacy"][
        "profile_image_url_https"
    ]

    # Media
    media = []
    if "extended_entities" in tweet["result"]["legacy"].keys():
        if "media" in tweet["result"]["legacy"]["extended_entities"].keys():
            media = [
                image["media_url_https"]
                for image in tweet["result"]["legacy"]["extended_entities"]["media"]
            ]

    # Text
    text = tweet["result"]["legacy"]["full_text"]

    # Tweet url
    tweet_url = f"https://twitter.com/user/status/{tweet['result']['legacy']['id_str']}"

    # Tickers
    tickers = tweet["result"]["legacy"]["entities"]["symbols"]
    if tickers:
        tickers = [ticker["text"] for ticker in tickers]

    # Hashtags
    hashtags = tweet["result"]["legacy"]["entities"]["hashtags"]
    if hashtags:
        hashtags = [hashtag["text"] for hashtag in hashtags]

    # Quote tweet
    if "quoted_status_result" in tweet["result"].keys():
        (
            q_text,
            q_user_name,
            q_user_screen_name,
            _,
            _,
            q_media,
            q_tickers,
            q_hashtags,
            _,
        ) = parse_tweet(tweet["result"]["quoted_status_result"])

        # Format the text to add the quoted tweet text
        q_text = "\n".join(map(lambda line: "> " + line, q_text.split("\n")))
        text = f"{text}\n\n> [@{q_user_screen_name}](https://twitter.com/{q_user_name}):\n{q_text}"

        # Add media, tickers, and hashtags together
        media += q_media
        tickers += q_tickers
        hashtags += q_hashtags

        retweeted_user = q_user_name

    if "retweeted_status_result" in tweet["result"]["legacy"].keys():
        # Get retweeted_info
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
        ) = parse_tweet(tweet["result"]["legacy"]["retweeted_status_result"])

        # Overwrite text
        text = r_text
        retweeted_user = r_user_name

    if reply:
        # Get reply info
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
        ) = parse_tweet(reply)

        text = "\n".join(map(lambda line: "> " + line, text.split("\n")))
        text = f"> [@{r_user_screen_name}](https://twitter.com/{user_name}):\n{text}\n\n{r_text}"

        # Add media, tickers, and hashtags together
        media += r_media
        tickers += r_tickers
        hashtags += r_hashtags

        # Disable retweeted_user if reply
        retweeted_user = None

    # Remove t.co url from text
    text = remove_twitter_url_at_end(text)

    # Replace &amp; etc.
    text = text.replace("&amp;", "&")
    text = text.replace("&gt;", ">")
    text = text.replace("&lt;", "<")

    # Convert media, tickers, hasthtags to sets to remove duplicates
    media = list(set(media))
    tickers = list(set(tickers))
    hashtags = list(set(hashtags))

    # tickers and hashtags all uppercase
    tickers = [ticker.upper() for ticker in tickers]
    hashtags = [hashtag.upper() for hashtag in hashtags]

    # Remove #crypto
    hashtags = [hashtag for hashtag in hashtags if hashtag != "CRYPTO"]

    # Maybe create the Discord title here as well
    # title = ...

    return (
        text,
        user_name,
        user_screen_name,
        user_img,
        tweet_url,
        media,
        tickers,
        hashtags,
        retweeted_user,
    )
