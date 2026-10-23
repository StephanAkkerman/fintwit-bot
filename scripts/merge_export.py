"""Combine the Discord scrape with fintwit-web's database export.

    python scripts/merge_export.py --export ../fintwit-web/export

Inputs:
    scraped/dataset/tweets.jsonl.gz   from ``merge_scraped.py`` (2021 - May 2026)
    --export DIR                      ``tweets-*.jsonl.gz`` from fintwit-web's
                                      ``python -m app.runtime.export_dataset``

Output ``scraped/combined/tweets.jsonl.gz`` has one record per tweet in a single
schema, ordered by tweet id, ready for ``upload_hf.py``. A tweet in both sources
keeps the export's record (better text, engagement, sentiment scores) and gains
the Discord-only fields (channels, post count, per-ticker prices at post time).

Both inputs must be sorted by tweet id, which both exporters guarantee; they are
merged as streams, so memory use doesn't depend on their size.
"""

import argparse
import glob
import gzip
import heapq
import itertools
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

from merge_scraped import tweet_created_at

CATEGORIES = ("crypto", "stocks", "other")

# Columns of the combined schema. None means "this source doesn't have it",
# which is different from an empty list or zero.
COLUMNS = (
    "tweet_id",
    "created_at",
    "source",
    "categories",
    "url",
    "user_name",
    "user_screen_name",
    "user_img",
    "text",
    "title",
    "tweet_type",
    "media",
    "tickers",
    "hashtags",
    "sentiment_label",
    "sentiment_score",
    "quoted_sentiment_label",
    "quoted_sentiment_score",
    "ticker_sentiment",
    "quoted_tweet",
    "replies",
    "likes",
    "views",
    "retweets",
    "has_chart",
    "chart_extraction",
    "image_text",
    "is_options_tweet",
    "options_context",
    "edited_at",
    "assets",
    # Discord only
    "channels",
    "first_posted_at",
    "n_posts",
    "financial_info",
)
# Copied unchanged from the export row
_EXPORT_PASSTHROUGH = (
    "user_name",
    "user_screen_name",
    "user_img",
    "text",
    "title",
    "url",
    "media",
    "tickers",
    "hashtags",
    "sentiment_label",
    "sentiment_score",
    "quoted_sentiment_label",
    "quoted_sentiment_score",
    "ticker_sentiment",
    "quoted_tweet",
    "replies",
    "likes",
    "views",
    "retweets",
    "has_chart",
    "chart_extraction",
    "image_text",
    "is_options_tweet",
    "options_context",
    "assets",
)
_NOT_STOCKS = {"", "unknown", "none", "crypto"}

# Hugging Face infers one Arrow schema from the first rows of a JSONL file, and
# a struct whose keys differ between rows then fails to load (verified with
# `datasets` 5.1). So `financial_info` gets a fixed set of keys, and the dicts
# whose keys vary per row are stored as JSON strings.
_FINANCIAL_KEYS = (
    "ticker",
    "exchanges",
    "price",
    "percentage_change",
    "after_hours_price",
    "after_hours_change",
    "source_url",
    "4h_ta_result",
    "4h_ta_details",
    "1d_ta_result",
    "1d_ta_details",
)
_JSON_COLUMNS = (
    "assets",
    "quoted_tweet",
    "chart_extraction",
    "options_context",
    "ticker_sentiment",
)


def _utc(value: str | None) -> str | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def _tweet_type(title: str | None) -> str:
    title = title or ""
    if "retweeted" in title:
        return "retweet"
    return "quote tweet" if "quote" in title else "tweet"


def _categories(*, crypto: bool, stocks: bool) -> list[str]:
    found = [c for c, hit in (("crypto", crypto), ("stocks", stocks)) if hit]
    return found or ["other"]


def from_discord(r: dict) -> dict:
    channels = r["channels"]
    kind = {"Video": "video", "GIF": "animated_gif"}.get(r.get("media_kind"), "photo")
    financial = r.get("financial_info") or []
    return {
        **dict.fromkeys(COLUMNS),
        "tweet_id": r["tweet_id"],
        "created_at": r["tweet_created_at"],
        "source": "discord",
        # The old stocks dataset included forex, so the forex channels do too
        "categories": _categories(
            crypto=any(c.startswith("crypto") for c in channels),
            stocks=any(c.startswith(("stocks", "forex")) for c in channels),
        ),
        "url": r.get("url"),
        "user_name": r.get("user_name"),
        "user_img": r.get("thumbnail_url"),
        "text": r.get("description"),
        "title": r.get("embed_title"),
        "tweet_type": r.get("tweet_type"),
        "media": [{"url": r["image_url"], "type": kind}] if r.get("image_url") else [],
        # Tickers the bot recognised, not just the cashtags written in the tweet
        "tickers": [t["ticker"].lstrip("$") for t in financial if t.get("ticker")],
        "sentiment_label": (r.get("sentiment") or "").upper() or None,
        "channels": channels,
        "first_posted_at": r.get("first_posted_at"),
        "n_posts": r.get("n_posts"),
        "financial_info": financial,
    }


def from_export(r: dict) -> dict:
    kinds = {str(a.get("kind") or "").lower() for a in r.get("assets") or []}
    tweet_id = str(r["id"])
    return {
        **dict.fromkeys(COLUMNS),
        **{k: r.get(k) for k in _EXPORT_PASSTHROUGH},
        "tweet_id": tweet_id,
        "created_at": _utc(r.get("created_at")) or tweet_created_at(int(tweet_id)),
        "source": "web",
        "categories": _categories(
            crypto="crypto" in kinds, stocks=bool(kinds - _NOT_STOCKS)
        ),
        "tweet_type": _tweet_type(r.get("title")),
        "edited_at": _utc(r.get("edited_at")),
    }


def combine(web: dict, discord: dict) -> dict:
    """A tweet both sources have: the export's record plus the Discord extras."""
    merged = dict(web)
    merged["source"] = "both"
    for key in ("channels", "first_posted_at", "n_posts", "financial_info"):
        merged[key] = discord[key]
    for key in ("sentiment_label", "user_img", "user_name"):
        merged[key] = web[key] or discord[key]
    merged["media"] = web["media"] or discord["media"]
    union = set(web["categories"]) | set(discord["categories"])
    union -= {"other"} if union - {"other"} else set()
    merged["categories"] = [c for c in CATEGORIES if c in union]
    return merged


def finalise(record: dict) -> dict:
    """The record as written: only schema columns, with loader-safe nesting."""
    out = {k: record[k] for k in COLUMNS}
    for key in _JSON_COLUMNS:
        if out[key] is not None:
            out[key] = json.dumps(out[key], ensure_ascii=False)
    if out["financial_info"] is not None:
        out["financial_info"] = [
            {k: t.get(k) for k in _FINANCIAL_KEYS} for t in out["financial_info"]
        ]
    return out


def _read(paths: list[str], convert):
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                yield convert(json.loads(line))


def _in_order(records, name: str):
    """Pass records through, failing loudly if a source isn't sorted by id."""
    previous = -1
    for record in records:
        current = int(record["tweet_id"])
        if current <= previous:
            raise SystemExit(f"{name} is not sorted by tweet id (at {current})")
        previous = current
        yield record


def merge_streams(discord_path: str, export_paths: list[str]):
    streams = [_in_order(_read([discord_path], from_discord), "Discord data")]
    if export_paths:
        streams.append(_in_order(_read(export_paths, from_export), "export"))
    merged = heapq.merge(*streams, key=lambda r: int(r["tweet_id"]))
    for _, group in itertools.groupby(merged, key=lambda r: r["tweet_id"]):
        records = list(group)
        if len(records) == 1:
            yield records[0]
        else:
            web = next(r for r in records if r["source"] == "web")
            discord = next(r for r in records if r["source"] == "discord")
            yield combine(web, discord)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--discord", default="scraped/dataset/tweets.jsonl.gz")
    parser.add_argument(
        "--export",
        metavar="DIR",
        help="fintwit-web export folder (tweets-*.jsonl.gz); optional",
    )
    parser.add_argument("--out", default="scraped/combined")
    args = parser.parse_args()

    if not os.path.exists(args.discord):
        parser.error(f"{args.discord} not found; run merge_scraped.py first")
    export_paths = []
    if args.export:
        export_paths = sorted(glob.glob(os.path.join(args.export, "tweets-*.jsonl.gz")))
        if not export_paths:
            parser.error(f"no tweets-*.jsonl.gz in {args.export}")

    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, "tweets.jsonl.gz")
    sources, categories = Counter(), Counter()
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for record in merge_streams(args.discord, export_paths):
            fh.write(json.dumps(finalise(record), ensure_ascii=False))
            fh.write("\n")
            sources[record["source"]] += 1
            categories.update(record["categories"])

    print(f"{sum(sources.values()):,} tweets -> {path}")
    for name in ("discord", "web", "both"):
        print(f"  {name:8} {sources[name]:>9,}")
    print("  categories: " + ", ".join(f"{c} {categories[c]:,}" for c in CATEGORIES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
