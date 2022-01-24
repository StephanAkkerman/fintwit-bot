import json
import datetime
from traceback import format_exc

# Local dependencies
from sentimentanalyis import classify_sentiment
from ticker import classify_ticker
from vars import (
    get_emoji,
    filter_dict
)

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

async def format_tweet(raw_data, following_ids):
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
                    #print(as_json)

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
                        return text, user, profile_pic, url, images, tickers, hashtags, retweeted_user
                        
                    except Exception:
                        print(
                            f"Error posting tweet of {user} at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
                        )
                        print(format_exc())
                        return None, None, None, None, None, None, None, None
                        
async def add_financials(e, tickers, hashtags, text, user, bot):
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

        volume, website, exchanges, price, change = classify_ticker(ticker)

        # Check if there is any volume
        if volume is None:

            # If it is a symbol, assume it is crypto (if no match could be found)
            if ticker in tickers:
                e.add_field(name=f"${ticker}", value="Crypto?")
                crypto += 1

                # Go to next in symbols
                print(
                    f"No crypto or stock match found for ${ticker} in {user}'s tweet at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
                continue
            else:
                continue

        title = f"${ticker}"

        # Determine if this is a crypto or stock
        if "coingecko" in website:
            crypto += 1
        if "yahoo" in website:
            stocks += 1

        # Format change
        if type(change) == list:
            if len(change) == 2:
                for i in range(len(change)):
                    if i == 0:
                        description = (
                            f"[AH: ${price[i]} ({change[i]})]({website})\n"
                        )
                    else:
                        description += f"[${price[i]} ({change[i]})]({website})"
            else:
                description = f"[${price[0]} ({change[0]})]({website})"

        else:
            description = f"[${price} ({change})]({website})"

            # Currently only adds emojis for crypto exchanges
            if "coingecko" in website:
                if "Binance" in exchanges:
                    title = f"{title} {get_emoji(bot, 'binance')}"
                if "KuCoin" in exchanges:
                    title = f"{title} {get_emoji(bot, 'kucoin')}"

        # Add the field with hyperlink
        e.add_field(name=title, value=description, inline=True)

    # If there are any tickers
    if symbols:
        sentiment = classify_sentiment(text)
        prediction = ("🐻 - Bearish", "🦆 - Neutral", "🐂 - Bullish")[np.argmax(sentiment)]
        e.add_field(
            name="Sentiment",
            value=f"{prediction} ({round(max(sentiment*100),2)}%)",
            inline=True,
        )
        
    # Decide the category
    if crypto == 0 and stocks == 0:
        category = None
    elif crypto >= stocks:
        category = "crypto"
    elif crypto < stocks:
        category = "stocks"
        
    return e, category