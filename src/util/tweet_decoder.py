## > Imports
# > Standard libaries
from __future__ import annotations
from typing import Optional, List
import datetime
from traceback import format_exc

# Local dependencies
from util.vars import  get_json_data, bearer_token

async def decode_tweet(
    as_json: dict,
    following_ids: List[str],
) -> Optional[
    tuple[str, str, str, str, List[str], List[str], List[str], Optional[str]]
]:
    """
    Gets all the useful infromation from the raw_data.
    Checks if the tweet is from someone we follow.

    Parameters
    ----------
    as_json : dict
        The data from the tweet.
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

    #print(as_json)
    (
        text,
        tickers,
        images,
        retweeted_user,
        hashtags,
    ) = await get_tweet(as_json, following_ids)

    # Post tweets that contain images
    if text == "" and images == []:
        return

    # Replace &amp;
    text = text.replace("&amp;", "&")
    text = text.replace("&gt;", ">")
    text = text.replace("&lt;", "<")

    # Post the tweet containing the important info
    try:
        # Get the user info
        user, profile_pic = get_user_info(as_json)
        
        return (
            text,
            user,
            profile_pic,
            f"https://twitter.com/{user}/status/{as_json['data']['id']}",
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
        return

def get_user_info(as_json: dict) -> tuple[str, str]:
    # Get the user name
    if "includes" in as_json.keys():
        user = as_json["includes"]["users"][0]["username"]

        # Get other info
        profile_pic = as_json["includes"]["users"][0]["profile_image_url"]
    else:
        print(as_json)

    return user, profile_pic

async def add_quote_tweet(quote_data : dict, retweeted_user : str):
    (
        user_text,
        user_ticker_list,
        user_image,
        user_hashtags,
    ) = await standard_tweet_info(quote_data, "quoted")

    # Get the information from the tweet that was quoted
    text, ticker_list, image, hashtags = await standard_tweet_info(
        quote_data, "quoted tweet"
    )

    # Combine the information
    images = user_image + image
    ticker_list = user_ticker_list + ticker_list
    hashtags = user_hashtags + hashtags

    # Add > to show it's a quote
    if text != "":
        text = "\n".join(map(lambda line: "> " + line, text.split("\n")))

    text = f"{user_text}\n\n> [@{retweeted_user}](https://twitter.com/{retweeted_user}):\n{text}"

    return text, ticker_list, images, hashtags

def get_basic_tweet_info(as_json : dict) -> tuple[str, Optional[str]]:
    retweeted_user = None
    
    # Tweet type can be "retweeted", "quoted" or "replied_to"
    tweet_type = as_json["data"]["referenced_tweets"][0]["type"]

    # Set the retweeted / quoted user
    if tweet_type == "retweeted" or tweet_type == "quoted":
        if len(as_json["includes"]["users"]) > 1:
            retweeted_user = as_json["includes"]["users"][1]["username"]
        else:
            # If the user retweeted themselves
            retweeted_user = as_json["includes"]["users"][0]["username"]
            
    return tweet_type, retweeted_user

async def add_replied_tweet(reply_data : dict):
    """
    Basically the same as add_quote_tweet but then turned around.

    Parameters
    ----------
    reply_data : dict
        The data from the tweet that was replied to and the reply itself.

    Returns
    -------
    _type_
        _description_
    """
    (
        user_text,
        user_ticker_list,
        user_image,
        user_hashtags,
    ) = await standard_tweet_info(reply_data, "reply")

    # Get the information from the tweet that was replied to
    text, ticker_list, image, hashtags = await standard_tweet_info(
        reply_data, "replied tweet"
    )

    # Combine the information
    images = image + user_image
    ticker_list = ticker_list + user_ticker_list 
    hashtags = hashtags + user_hashtags
    
    # Add > to show it's a quote
    if text != "":
        text = "\n".join(map(lambda line: "> " + line, text.split("\n")))
        
    replied_to = reply_data["includes"]["users"][0]["username"]

    text = f"> [@{replied_to}](https://twitter.com/{replied_to}):\n{text}\n\n{user_text}"

    return text, ticker_list, images, hashtags

async def get_tweet(
    as_json: dict,
    following_ids: List[str]
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
        tweet_type, retweeted_user = get_basic_tweet_info(as_json)
        
        # Could also add the tweet that it was replied to
        if tweet_type == "replied_to":
            author = as_json["data"]["author_id"]
            replied_to = as_json["data"]["in_reply_to_user_id"]
            
            # Only post tweets that are replies to people we follow
            if author in following_ids and replied_to in following_ids:
                text, ticker_list, images, hashtags = await add_replied_tweet(as_json)
            else:
                return "", [], [], retweeted_user, []

        # If it is a retweet change format
        if tweet_type == "retweeted":
            # Only do this if a quote tweet was retweeted
            if (
                "referenced_tweets" in as_json["includes"]["tweets"][-1].keys()
                and as_json["includes"]["tweets"][-1]["referenced_tweets"][0]["type"]
                == "quoted"
            ):
                quote_data = await get_json_data(
                    url=f"https://api.twitter.com/2/tweets/{as_json['includes']['tweets'][-1]['conversation_id']}?tweet.fields=attachments,entities,conversation_id&expansions=attachments.media_keys,referenced_tweets.id&media.fields=url",
                    headers={"Authorization": f"Bearer {bearer_token}"},
                )

                text, ticker_list, images, hashtags = await add_quote_tweet(
                    quote_data,
                    retweeted_user,
                )

            # Standard retweet
            else:
                (text, ticker_list, images, hashtags,) = await standard_tweet_info(
                    as_json, "retweeted"
                )

        # Add the user text to it
        elif tweet_type == "quoted":
            text, ticker_list, images, hashtags = await add_quote_tweet(
                as_json,
                retweeted_user,
            )

    # If there is no reference then it is a normal tweet
    else:        
        text, ticker_list, images, hashtags = await standard_tweet_info(
            as_json, "tweet"
        )

    try:
        return text, ticker_list, images, retweeted_user, hashtags
    except Exception as e:
        print("Error processing tweet, error:", e)
        print(as_json)


def get_tweet_img(as_json: dict) -> List[str]:
    images = []

    # Check for images
    if "includes" in as_json.keys():
        if "media" in as_json["includes"].keys():
            for media in as_json["includes"]["media"]:
                if media["type"] == "photo":
                    images.append(media["url"])
                    
    return images

def get_tags(as_json: dict, keyword : str) -> List[str]:
    """
    Gets the hashtags or cashtags from the tweet.

    Parameters
    ----------
    as_json : dict
        The json object of the tweet.
    keyword : str
        Can be "hashtags" or "cashtags".

    Returns
    -------
    List[str]
        The tags in the tweet text.
    """

    tags = []
    if "entities" in as_json.keys():
        if keyword in as_json["entities"].keys():
            for tag in as_json["entities"][keyword]:
                tag = tag["tag"].upper()
                
                # Ignore #crypto
                if tag != "CRYPTO":
                    tags.append(tag)

    return tags

async def get_missing_img(conversation_id : str) -> List[str]:
    image_data = await get_json_data(
        url=f"https://api.twitter.com/2/tweets/{conversation_id}?expansions=attachments.media_keys&media.fields=url",
        headers={"Authorization": f"Bearer {bearer_token}"},
    )
    return get_tweet_img(image_data)

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
    # Check for images, do not do this for quoted tweet, otherwise images will get added twice
    images = []
    if tweet_type != "quoted tweet" and tweet_type != "replied tweet":
        images = get_tweet_img(as_json)
                
    tweet_data = as_json["data"]

    # Unpack json data
    if tweet_type == "retweeted" or tweet_type == "quoted tweet":
        if "includes" in as_json.keys():
            if "tweets" in as_json["includes"].keys():
                tweet_data = as_json["includes"]["tweets"][-1]
            else:
                print(f"Could not find tweet data in json at {datetime.datetime.now()}:\n", as_json)
    elif tweet_type == "reply" or tweet_type == "replied tweet":
        if "includes" in as_json.keys():
            if "tweets" in as_json["includes"].keys():
                tweet_data = as_json["includes"]["tweets"][0]
            else:
                print(f"Could not find tweet data in json at {datetime.datetime.now()}:\n", as_json)
        
    text = tweet_data["text"]

    # Remove image urls and extend other urls
    if "entities" in tweet_data.keys():
        if "urls" in tweet_data["entities"].keys():
            for url in tweet_data["entities"]["urls"]:
                if "media_key" in url.keys():
                    text = text.replace(url["url"], "")
                    # If there are no images yet, get the image based on conversation id
                    if images == []:
                        if tweet_type == "replied tweet":
                            if "referenced_tweets" in tweet_data.keys():
                                images = await get_missing_img(tweet_data["referenced_tweets"][0]["id"])
                            else:
                                images = await get_missing_img(tweet_data["conversation_id"])
                                print(f"No referenced tweet found for replied tweet at:", datetime.datetime.now(), as_json)
                        else:
                            images = await get_missing_img(tweet_data["conversation_id"])
                else:
                    if tweet_type == "quoted" and url["expanded_url"].startswith(
                        "https://twitter.com"
                    ):
                        # If it is a quote and the url is a twitter url, remove it
                        text = text.replace(url["url"], "")
                    else:
                        text = text.replace(url["url"], url["expanded_url"])
                        
    tickers = get_tags(tweet_data, "cashtags")
    hashtags = get_tags(tweet_data, "hashtags")

    return text, tickers, images, hashtags