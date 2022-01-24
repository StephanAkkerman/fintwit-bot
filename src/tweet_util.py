async def get_tweet(as_json):
    """Returns the info of the tweet that was quote retweeted"""

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

        retweeted_user = as_json['quoted_status']['user']['screen_name']

        text, ticker_list, image, hashtags = await standard_tweet_info(
            as_json["quoted_status"]
        )

        # Combine the information
        images = user_image + image
        ticker_list = user_ticker_list + ticker_list
        hashtags = user_hashtags + hashtags

        text = f"{user_text}\n\n[@{retweeted_user}](https://twitter.com/{retweeted_user}):\n{text}"

    # If retweeted check the extended tweet
    elif "retweeted_status" in as_json:

        text, ticker_list, images, hashtags = await standard_tweet_info(
            as_json["retweeted_status"]
        )
        retweeted_user = as_json["retweeted_status"]["user"]["screen_name"]

    else:
        text, ticker_list, images, hashtags = await standard_tweet_info(
            as_json
        )
        retweeted_user = None

    return text, ticker_list, images, retweeted_user, hashtags

async def standard_tweet_info(as_json):
    """Returns the info of the tweet"""

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
                for media in as_json["extended_tweet"]["extended_entities"][
                    "media"
                ]:
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
