from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, List, Optional

import aiohttp

from constants.logger import logger

XQUIK_API_KEY_ENV = "XQUIK_API_KEY"
XQUIK_SEARCH_QUERY_ENV = "XQUIK_SEARCH_QUERY"
XQUIK_SEARCH_LIMIT_ENV = "XQUIK_SEARCH_LIMIT"
XQUIK_SEARCH_MAX_PAGES_ENV = "XQUIK_SEARCH_MAX_PAGES"
DEFAULT_XQUIK_BASE_URL = "https://xquik.com/api/v1"
DEFAULT_SEARCH_LIMIT = 50
MAX_SEARCH_LIMIT = 200
DEFAULT_MAX_SEARCH_PAGES = 10
MAX_SEARCH_PAGES = 100
MAX_SEEN_IDS = MAX_SEARCH_LIMIT * MAX_SEARCH_PAGES
SEEN_IDS_PATH = "state/xquik_seen_ids.json"

CASHTAG_RE = re.compile(r"(?<![A-Za-z0-9_])\$([A-Za-z][A-Za-z0-9_]{0,14})")
HASHTAG_RE = re.compile(r"(?<![A-Za-z0-9_])#([A-Za-z][A-Za-z0-9_]{0,49})")


@dataclass(frozen=True)
class XquikMedia:
    url: str


@dataclass(frozen=True)
class XquikTweet:
    id: str
    text: str
    user_name: str
    user_screen_name: str
    user_img: str
    url: str
    media: List[XquikMedia]
    tickers: List[str]
    hashtags: List[str]
    title: str
    media_types: List[str]


def is_xquik_enabled() -> bool:
    return bool(os.getenv(XQUIK_API_KEY_ENV, "").strip())


def build_xquik_search_query() -> str:
    return os.getenv(XQUIK_SEARCH_QUERY_ENV, "").strip()


async def fetch_xquik_tweets(query: str) -> Optional[List[XquikTweet]]:
    api_key = os.getenv(XQUIK_API_KEY_ENV, "").strip()
    if not api_key or not query.strip():
        return []

    tweets: List[XquikTweet] = []
    cursor = ""
    seen_cursors = set()
    headers = {"Accept": "application/json", "x-api-key": api_key}

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for _ in range(_xquik_search_max_pages()):
                payload = await _fetch_xquik_tweet_page(
                    session,
                    headers,
                    query,
                    cursor,
                )
                if payload is None:
                    return None

                tweets.extend(
                    tweet
                    for tweet in (
                        _tweet_from_record(record)
                        for record in _tweet_records_from_payload(payload)
                    )
                    if tweet is not None
                )
                if not _has_next_page(payload):
                    return _filter_new_tweets(tweets)

                cursor = _string_value(payload.get("next_cursor"))
                if not cursor:
                    logger.error("Xquik tweet search returned no next cursor")
                    return None
                if cursor in seen_cursors:
                    logger.error("Xquik tweet search repeated a pagination cursor")
                    return None
                seen_cursors.add(cursor)

            logger.error("Xquik tweet search returned too many pages")
            return None
    except Exception as error:
        logger.error(f"Xquik tweet search failed: {type(error).__name__}")
        return None


async def _fetch_xquik_tweet_page(
    session: aiohttp.ClientSession,
    headers: dict,
    query: str,
    cursor: str,
) -> Optional[dict]:
    url = f"{DEFAULT_XQUIK_BASE_URL}/x/tweets/search"
    params = {
        "q": query,
        "queryType": "Latest",
        "limit": str(_xquik_search_limit()),
    }
    if cursor:
        params["cursor"] = cursor

    async with session.get(url, headers=headers, params=params) as response:
        if response.status != 200:
            logger.error(f"Xquik tweet search failed with status {response.status}")
            return None
        payload = await response.json()

    return payload if isinstance(payload, dict) else None


def _xquik_search_limit() -> int:
    raw_limit = os.getenv(XQUIK_SEARCH_LIMIT_ENV, "")
    try:
        limit = int(raw_limit)
    except ValueError:
        limit = DEFAULT_SEARCH_LIMIT

    return min(max(limit, 1), MAX_SEARCH_LIMIT)


def _xquik_search_max_pages() -> int:
    raw_pages = os.getenv(XQUIK_SEARCH_MAX_PAGES_ENV, "")
    try:
        pages = int(raw_pages)
    except ValueError:
        pages = DEFAULT_MAX_SEARCH_PAGES

    return min(max(pages, 1), MAX_SEARCH_PAGES)


def _tweet_records_from_payload(payload: Any) -> List[dict]:
    if not isinstance(payload, dict):
        return []

    tweets = payload.get("tweets")
    if not isinstance(tweets, list):
        return []

    return [tweet for tweet in tweets if isinstance(tweet, dict)]


def _has_next_page(payload: dict) -> bool:
    raw_value = payload.get("has_next_page")
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        return raw_value.strip().lower() in {"1", "true", "yes"}
    return bool(raw_value)


def _tweet_from_record(record: dict) -> Optional[XquikTweet]:
    text = _string_value(record.get("text"))
    tweet_id = _string_value(record.get("id"))
    if not text or not tweet_id:
        return None

    author = record.get("author")
    author_record = author if isinstance(author, dict) else {}
    user_name = _string_value(author_record.get("name")) or "X user"
    user_screen_name = (
        _string_value(author_record.get("username"))
        or _string_value(author_record.get("userName"))
        or "unknown"
    )
    user_img = (
        _string_value(author_record.get("profilePicture"))
        or _string_value(author_record.get("profile_image_url_https"))
        or ""
    )
    tweet_url = _string_value(record.get("url")) or (
        f"https://twitter.com/{user_screen_name}/status/{tweet_id}"
    )
    media_items, media_types = _media_from_record(record)

    return XquikTweet(
        id=tweet_id,
        text=text,
        user_name=user_name,
        user_screen_name=user_screen_name,
        user_img=user_img,
        url=tweet_url,
        media=media_items,
        tickers=_tickers_from_record(record),
        hashtags=_hashtags_from_record(record),
        title=f"{user_name} tweeted",
        media_types=media_types,
    )


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _media_from_record(record: dict) -> tuple[List[XquikMedia], List[str]]:
    media = record.get("media")
    if not isinstance(media, list):
        return [], []

    media_items: List[XquikMedia] = []
    media_types: List[str] = []
    for item in media:
        if not isinstance(item, dict):
            continue
        media_url = (
            _string_value(item.get("mediaUrl"))
            or _string_value(item.get("media_url_https"))
            or _string_value(item.get("url"))
        )
        if media_url:
            media_items.append(XquikMedia(url=media_url))
        media_type = _string_value(item.get("type"))
        if media_type:
            media_types.append(media_type)

    return media_items, media_types


def _tickers_from_record(record: dict) -> List[str]:
    symbols = _entity_values(record, "symbols", "text")
    if symbols:
        return sorted({symbol.upper().lstrip("$") for symbol in symbols})

    text = _string_value(record.get("text"))
    return sorted({match.upper() for match in CASHTAG_RE.findall(text)})


def _hashtags_from_record(record: dict) -> List[str]:
    hashtags = _entity_values(record, "hashtags", "text")
    if hashtags:
        return sorted({hashtag.upper().lstrip("#") for hashtag in hashtags})

    text = _string_value(record.get("text"))
    return sorted({match.upper() for match in HASHTAG_RE.findall(text)})


def _entity_values(record: dict, key: str, value_key: str) -> List[str]:
    entities = record.get("entities")
    if not isinstance(entities, dict):
        return []

    values = entities.get(key)
    if not isinstance(values, list):
        return []

    parsed: List[str] = []
    for value in values:
        if isinstance(value, dict):
            raw = _string_value(value.get(value_key))
            if raw:
                parsed.append(raw)
    return parsed


def _filter_new_tweets(tweets: List[XquikTweet]) -> List[XquikTweet]:
    current_ids = _unique_strings([tweet.id for tweet in tweets if tweet.id])
    if not current_ids:
        return []

    seen_ids = _read_seen_ids()
    if seen_ids is None:
        _write_seen_ids(current_ids)
        return []

    seen_id_set = set(seen_ids)
    new_tweets: List[XquikTweet] = []
    new_ids = set()
    for tweet in tweets:
        if tweet.id in seen_id_set or tweet.id in new_ids:
            continue
        new_tweets.append(tweet)
        new_ids.add(tweet.id)

    updated_ids = _unique_strings([*current_ids, *seen_ids])[:MAX_SEEN_IDS]
    if not _write_seen_ids(updated_ids):
        return []

    return new_tweets


def _unique_strings(values: List[str]) -> List[str]:
    seen = set()
    unique_values = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _read_seen_ids() -> Optional[List[str]]:
    try:
        with open(SEEN_IDS_PATH, "r", encoding="utf-8") as file:
            values = json.load(file)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError) as error:
        logger.error(f"Could not read Xquik timeline state: {type(error).__name__}")
        return None

    if not isinstance(values, list) or not all(
        isinstance(value, str) and value for value in values
    ):
        logger.error("Could not read Xquik timeline state: invalid data")
        return None

    return _unique_strings(values)[:MAX_SEEN_IDS]


def _write_seen_ids(tweet_ids: List[str]) -> bool:
    temp_path = f"{SEEN_IDS_PATH}.tmp"
    try:
        os.makedirs(os.path.dirname(SEEN_IDS_PATH), exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(tweet_ids, file)
        os.replace(temp_path, SEEN_IDS_PATH)
    except OSError as error:
        logger.error(f"Could not write Xquik timeline state: {type(error).__name__}")
        return False
    return True
