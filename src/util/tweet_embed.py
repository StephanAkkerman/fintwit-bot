## > Imports
# > Standard libaries
from __future__ import annotations
from typing import List
import datetime

# Discord imports
import discord
from discord.ext import commands

# 3rd party imports
import pandas as pd
import numpy as np

# Local dependencies
import util.vars
from util.ticker_classifier import classify_ticker, get_financials
from util.sentiment_analyis import add_sentiment
from util.vars import filter_dict
from util.db import merge_and_update, remove_old_rows, update_tweet_db
from cogs.loops.overview import Overview

tweet_overview = None


async def make_tweet_embed(
    text: str,
    user_name: str,
    profile_pic: str,
    url: str,
    images: List[str],
    tickers: List[str],
    hashtags: List[str],
    e_title: str,
    bot: commands.Bot,
) -> tuple[discord.Embed, str, str, list, list]:
    """
    Pre-processing the tweet data before uploading it to the Discord channels.
    This function creates the embed object and tags the user after it is correctly uploaded.

    Parameters
    ----------
        text : str
            The text of the tweet.
        user : str
            The user that posted this tweet.
        profile_pic : str
            The url to the profile pic of the user.
        url : str
            The url to the tweet.
        images : list
            The images contained in this tweet.
        tickers : list
            The tickers contained in this tweet (i.e. $BTC).
        hashtags : list
            The hashtags contained in this tweet.
        retweeted_user : str
            The user that was retweeted by this tweet.
        bot : commands.Bot
            Discord bot object.

    Returns
    -------
    None
    """

    category = None
    base_symbols = []

    # Ensure the tickers are unique
    symbols = get_clean_symbols(tickers, hashtags)[:24]

    e = make_embed(symbols, url, text, profile_pic, images, e_title)

    # Max 25 fields
    if symbols:
        e, category, base_symbols = await add_financials(
            e, symbols, tickers, text, user_name, bot
        )

    return e, category, base_symbols


def make_embed(symbols, url, text, profile_pic, images, e_title) -> discord.Embed:
    # Set the properties of the embed
    e = discord.Embed(
        title=embed_title(e_title, symbols),
        url=url,
        description=text,
        color=0x1DA1F2,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )

    e.set_thumbnail(url=profile_pic)

    # Set image if an image is included in the tweet
    if images:
        e.set_image(url=images[0])

    # Set the twitter icon as footer image
    e.set_footer(
        text="\u200b",
        icon_url="https://abs.twimg.com/icons/apple-touch-icon-192x192.png",
    )

    return e


def embed_title(e_title, tickers) -> str:
    title = f"{e_title} about {', '.join(tickers)}"

    # The max length of the title is 256 characters
    if len(title) > 256:
        title = title[:253] + "..."

    return title


async def add_financials(
    e: discord.Embed,
    symbols: List[str],
    tickers: List[str],
    text: str,
    user: str,
    bot: commands.Bot,
) -> tuple[discord.Embed, str, List[str]]:
    """
    Adds the financial data to the embed and returns the corresponding category.

    Parameters
    ----------
    e : discord.Embed
        The embed to add the data to.
    symbols : List[str]
        The symbols (tickers + hashtags) in the tweet.
    tickers : List[str]
        The tickers in the tweet.
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
        List[str]
            The base symbols of the tickers.
    """
    global tweet_overview

    # In case multiple tickers get send
    crypto = stocks = forex = 0

    base_symbols = []
    categories = []
    do_last = []
    classified_tickers = []
    changes = []

    if not util.vars.classified_tickers.empty:
        # Drop tickers older than 3 days
        util.vars.classified_tickers = remove_old_rows(util.vars.classified_tickers, 3)
        classified_tickers = util.vars.classified_tickers["ticker"].tolist()

    for ticker in symbols:
        if crypto > stocks and crypto > forex:
            majority = "crypto"
        elif stocks > crypto and stocks > forex:
            majority = "stocks"
        elif forex > crypto and forex > stocks:
            majority = "forex"
        else:
            majority = "Unknown"

        # Get the information about the ticker
        if ticker not in classified_tickers:
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

                # Db cannot save lists
                if exchanges == []:
                    exchanges = None

                # Convert info to a dataframe
                df = pd.DataFrame(
                    [
                        {
                            "ticker": ticker,
                            "website": website,
                            "exchanges": ";".join(exchanges),
                            "base_symbol": base_symbol,
                            "timestamp": datetime.datetime.now(),
                        }
                    ]
                )

                # Save the ticker info in a database
                util.vars.classified_tickers = merge_and_update(
                    util.vars.classified_tickers, df, "classified_tickers"
                )

            else:
                if ticker in tickers:
                    e.add_field(name=f"${ticker}", value=majority)
                    print(
                        f"No crypto or stock match found for ${ticker} in {user}'s tweet at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    )

                # Go to next in symbols
                continue
        else:
            ticker_info = util.vars.classified_tickers[
                util.vars.classified_tickers["ticker"] == ticker
            ]
            website = ticker_info["website"].values[0]
            exchanges = ticker_info["exchanges"].values[0]
            exchanges = exchanges.split(";")
            base_symbol = ticker_info["base_symbol"].values[0]

            # Still need the price, change, TA info
            price, change, four_h_ta, one_d_ta = await get_financials(ticker, website)

        title = f"${ticker}"

        # Add to base symbol list to prevent duplicates
        base_symbols.append(base_symbol)

        if type(change) == list:
            changes.append(change[-1])
        else:
            changes.append(change)

        # Determine if this is a crypto or stock
        if website:
            if "coingecko" in website:
                crypto += 1
                categories.append("crypto")
                for x in exchanges:
                    if x in util.vars.custom_emojis.keys():
                        title = f"{title} {util.vars.custom_emojis[x]}"

            if "yahoo" in website:
                stocks += 1
                categories.append("stocks")
            if "forex" in website:
                forex += 1
                categories.append("forex")
        else:
            # Default category is crypto
            categories.append("crypto")

        # If there is no TA for a symbol, add it at the end of the embed
        if four_h_ta is None:
            do_last.append((title, change, price, website))
            continue

        # Add the field with hyperlink
        e.add_field(
            name=title, value=get_description(change, price, website), inline=True
        )

        e.add_field(name="4h TA", value=four_h_ta, inline=True)

        if one_d_ta:
            e.add_field(name="1d TA", value=one_d_ta, inline=True)

    for title, change, price, website in do_last:
        e.add_field(
            name=title, value=get_description(change, price, website), inline=True
        )

    # Finally add the sentiment to the embed
    if base_symbols:  # or if categories:
        e, prediction = add_sentiment(e, text)
    else:
        prediction = None

    # Decide the category of this tweet
    if crypto == 0 and stocks == 0 and forex == 0:
        category = None
    else:
        category = ("crypto", "stocks", "forex")[np.argmax([crypto, stocks, forex])]

    # If there are base symbols, add them to the database
    # Also post the overview of mentioned tickers
    if base_symbols:
        update_tweet_db(base_symbols, user, prediction, categories, changes)

        if not tweet_overview:
            tweet_overview = Overview(bot)

        await tweet_overview.overview(category, base_symbols, prediction)

    # Return just the prediction without emoji
    return e, category, base_symbols


def get_clean_symbols(tickers, hashtags):
    # Remove #NFT from the list
    hashtags = [hashtag for hashtag in hashtags if hashtag != "NFT"]

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


def format_description(
    AH: bool, change: list, price: list, website: str, i: int
) -> str:
    if AH:
        return f"[AH: ${price[i]}\n({change[i]})]({website})\n"
    else:
        return f"[${price[i]}\n({change[i]})]({website})"


def get_description(change, price, website):
    if not change and not price:
        return "\u200b"

    # Change can be a list (if the information is from Yahoo Finance) or a string
    if type(change) == list and type(price) == list:
        # If the length is 2 then we know the after-hour prices
        if len(change) == 2 and len(price) == 2:
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
