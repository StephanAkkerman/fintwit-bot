## > Imports
# > Standard libaries
from __future__ import annotations

import datetime
from typing import List

# Discord imports
import discord
import numpy as np

# 3rd party imports
import pandas as pd
from discord.ext import commands

import util.vars
from cogs.loops.overview import Overview

# Local dependencies
from constants.logger import logger
from constants.sources import data_sources
from models.sentiment import add_sentiment
from util.db import merge_and_update, remove_old_rows, update_tweet_db
from util.ticker_classifier import classify_ticker, get_financials

tweet_overview = None

# Replace key by value
filter_dict = {
    "BITCOIN": "BTC",
    "BTCD": "BTC.D",
    "ETHEREUM": "ETH",
    "ES_F": "ES=F",
    "ES": "ES=F",
    "NQ": "NQ=F",
    "NQ_F": "NQ=F",
    "CL_F": "CL=F",
    "APPL": "AAPL",
    "DEFI": "DEFIPERP",
    "NVIDIA": "NVDA",
}


async def make_tweet_embed(
    text: str,
    user_name: str,
    profile_pic: str,
    url: str,
    images: List[str],
    tickers: List[str],
    hashtags: List[str],
    e_title: str,
    media_types: List[str],
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
    tickers = tickers[:24]

    # Check for difference
    if symbols != tickers + hashtags:
        logger.debug(
            f"Removed following symbols: {set(tickers + hashtags) - set(symbols)}"
        )

    e = make_embed(
        symbols=symbols,
        url=url,
        text=text,
        profile_pic=profile_pic,
        images=images,
        e_title=e_title,
        media_types=media_types,
    )

    # Max 25 fields
    if symbols:
        logger.debug(f"Adding financials for symbols: {symbols}")
        e, category, base_symbols = await add_financials(
            e=e, symbols=symbols, tickers=tickers, text=text, user=user_name, bot=bot
        )

    return e, category, base_symbols


def make_embed(
    symbols, url, text, profile_pic, images, e_title, media_types: List[str]
) -> discord.Embed:
    # Set the properties of the embed
    e = discord.Embed(
        title=embed_title(e_title, symbols),
        url=url,
        description=text,
        color=data_sources["twitter"]["color"],
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )

    e.set_thumbnail(url=profile_pic)

    # Set image if an image is included in the tweet
    if images:
        e.set_image(url=images[0])

    footer_text = "\u200b"

    if "video" in media_types:
        footer_text = "Video"
    elif "animated_gif" in media_types:
        footer_text = "GIF"

    # Set the twitter icon as footer image
    e.set_footer(
        text=footer_text,
        icon_url=data_sources["twitter"]["icon"],
    )

    return e


def embed_title(e_title: str, tickers: list) -> str:
    if not tickers:
        return e_title

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
    logger.debug(
        f"Adding financials to the embed. For symbols: {symbols}, tickers: {tickers}"
    )

    # In case multiple tickers get send
    crypto = stocks = 0

    base_symbols = []
    categories = []
    do_last = []
    classified_tickers = []
    changes = []

    if not util.vars.classified_tickers.empty:
        # Drop tickers older than 3 days
        util.vars.classified_tickers = remove_old_rows(util.vars.classified_tickers, 3)
        classified_tickers = util.vars.classified_tickers["ticker"].tolist()

    for symbol in symbols:
        logger.debug(f"Symbol: {symbol}")
        if crypto > stocks:
            majority = "crypto"
        elif stocks > crypto:
            majority = "stocks"
        else:
            majority = "Unknown"

        # Get the information about the ticker
        if symbol not in classified_tickers:
            logger.debug(f"Classifying ticker: {symbol} with majority: {majority}")
            if symbol == "BTC":
                majority = "crypto"
            ticker_info = await classify_ticker(symbol, majority)

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
                logger.debug(
                    f"Classified ticker: {symbol} as {base_symbol}. Website: {website}"
                )

                # Skip if this ticker has been done before, for instance in tweets containing Solana and SOL
                if base_symbol in base_symbols:
                    continue

                if exchanges is None:
                    exchanges = []
                    logger.warn(f"No exchanges found for ticker: {symbol}")

                # Convert info to a dataframe
                df = pd.DataFrame(
                    [
                        {
                            "ticker": symbol,
                            "website": website,
                            # Db cannot handle lists, so we convert them to strings
                            "exchanges": (
                                ";".join(exchanges) if len(exchanges) > 0 else ""
                            ),
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
                if symbol in tickers:
                    e.add_field(name=f"${symbol}", value=majority)
                logger.debug(
                    f"No crypto or stock match found for ${symbol} in {user}'s tweet at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )

                # Go to next in symbols
                continue
        else:
            logger.debug(f"Found ticker {symbol} in previously classified tickers.")
            ticker_info = util.vars.classified_tickers[
                util.vars.classified_tickers["ticker"] == symbol
            ]
            website = ticker_info["website"].values[0]
            exchanges = ticker_info["exchanges"].values[0]
            # Convert string to list
            exchanges = exchanges.split(";")
            base_symbol = ticker_info["base_symbol"].values[0]

            # Still need the price, change, TA info
            price, change, four_h_ta, one_d_ta = await get_financials(symbol, website)

        title = f"${symbol}"

        # Add to base symbol list to prevent duplicates
        base_symbols.append(base_symbol)

        if isinstance(change, list) and len(change) == 1:
            changes.append(change[-1])
        else:
            changes.append(change)

        # Determine if this is a crypto or stock
        if website:
            if "coingecko" in website or "BTC" in base_symbol:
                crypto += 1
                categories.append("crypto")
                for x in exchanges:
                    if x in util.vars.custom_emojis.keys():
                        title = f"{title} {util.vars.custom_emojis[x]}"

            if "yahoo" in website:
                stocks += 1
                categories.append("stocks")
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
    if crypto == 0 and stocks == 0:
        category = None
    else:
        category = ("crypto", "stocks")[np.argmax([crypto, stocks])]

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
    hashtags = [hashtag for hashtag in hashtags if hashtag not in ["NFT", "CRYPTO"]]

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
    if isinstance(change, list) and isinstance(price, list):
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
