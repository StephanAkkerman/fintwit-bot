"""Merge every scrape (old CSVs and new JSONL) into one deduplicated dataset.

Run with ``python scripts/merge_scraped.py [--input scraped] [--out scraped/dataset]``.

Sources are read most-trustworthy first: JSONL from ``scraper.py``, then the raw
CSV scrapes, then anything in a ``merged`` folder (those are derived from the
raw files). For every file the report shows how many tweets and posts it added
that earlier files didn't have; a file adding nothing is redundant and can be
skipped (or deleted).

The same tweet is often posted several times, once per ticker it mentions, so
duplicates are merged rather than dropped: their ``financial_info`` is combined.

Writes to ``--out``:
    tweets.jsonl.gz      one record per tweet, ordered by tweet id
    known_tweet_ids.txt  every tweet id covered, to skip when scraping more
    report.json          the per-file table below, machine readable
"""

import argparse
import ast
import csv
import glob
import gzip
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

csv.field_size_limit(2**31 - 1)  # sys.maxsize overflows the C long on Windows

_TWEET_ID = re.compile(r"/status/(\d+)")
_TWITTER_EPOCH_MS = 1288834974657
_SCALAR_FIELDS = (
    "description",
    "embed_title",
    "tweet_type",
    "user_name",
    "media_kind",
    "image_url",
    "thumbnail_url",
    "sentiment",
)


@dataclass
class SourceStats:
    file: str
    rows: int = 0
    blank: int = 0
    no_tweet_id: int = 0
    tweets: int = 0
    new_tweets: int = 0
    new_posts: int = 0

    @property
    def redundant(self) -> bool:
        return self.rows > 0 and self.new_posts == 0


def tweet_created_at(tweet_id: int) -> str:
    """When the tweet was sent, from its Snowflake id (the embed time is the
    bot's posting time, which can lag by hours)."""
    ms = (tweet_id >> 22) + _TWITTER_EPOCH_MS
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def _parse_time(value) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _literal_list(value) -> list:
    if not value or value == "[]":
        return []
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return []
    return parsed if isinstance(parsed, list) else []


def _channel_from_discord(category: str | None, channel: str | None) -> str:
    """'▬▬▬ 🎰 Crypto ▬▬▬' + '📈┃charts' -> 'crypto_charts', the CSV naming.

    The channel name alone isn't enough: both Crypto and Stocks have 'charts'.
    """
    parts = (
        re.sub(r"[^\w\s]", "", p or "").strip().lower() for p in (category, channel)
    )
    return "_".join(p for p in parts if p) or "jsonl"


def _channel_from_path(path: str) -> str:
    name = os.path.splitext(os.path.basename(path))[0].lower()
    for prefix in ("new_", "merged_"):
        name = name.removeprefix(prefix)
    return name


def _record(
    *, tweet_id, posted_at, channel, message_id=None, financial_info=(), **fields
) -> dict:
    return {
        "tweet_id": tweet_id,
        "posted_at": posted_at,
        "channels": {channel},
        "message_ids": {message_id} if message_id else set(),
        "financial_info": list(financial_info),
        **{k: fields.get(k) or None for k in _SCALAR_FIELDS},
        "url": fields.get("url") or None,
    }


# Titles read "[<:emoji:id>] <user> tweeted|replied to X|quote tweeted X|retweeted X
# [about TICKERS]"; older ones use "<user> 🔁 <retweeted user>".
_TITLE_USER = re.compile(
    r"^(?:<a?:\w+:\d+>\s*)?(.+?)\s+(?:tweeted|replied to|quote tweeted|retweeted|🔁)(?:\s|$)"
)


def _user_from_title(title: str | None) -> str | None:
    """Best-effort poster display name; the JSONL scrapes have the real field."""
    match = _TITLE_USER.match(title or "")
    return match.group(1) if match else None


def _from_csv_row(row: dict, channel: str) -> dict | None:
    match = _TWEET_ID.search(row.get("url") or "")
    if not match:
        return None
    fields = {k: row.get(k) for k in (*_SCALAR_FIELDS, "url")}
    # The CSV schema has no author field; the name is only inside embed_title
    fields["user_name"] = _user_from_title(row.get("embed_title"))
    return _record(
        tweet_id=match.group(1),
        posted_at=_parse_time(row.get("timestamp")),
        channel=channel,
        financial_info=_literal_list(row.get("financial_info")),
        **fields,
    )


def _from_json_record(rec: dict) -> dict | None:
    if not rec.get("tweet_id"):
        return None
    return _record(
        posted_at=_parse_time(rec.get("timestamp")),
        channel=_channel_from_discord(rec.get("category"), rec.get("channel")),
        message_id=rec.get("message_id"),
        **{
            k: rec.get(k)
            for k in (*_SCALAR_FIELDS, "url", "tweet_id", "financial_info")
        },
    )


def _read_source(path: str):
    """Yield (record_or_None, is_blank) for each row of a CSV or JSONL file."""
    if path.endswith(".jsonl"):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    yield _from_json_record(json.loads(line)), False
        return
    channel = _channel_from_path(path)
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            blank = not any(v for v in row.values())
            yield (None if blank else _from_csv_row(row, channel)), blank


def _merge(base: dict, new: dict) -> None:
    base["channels"] |= new["channels"]
    base["message_ids"] |= new["message_ids"]
    if new["posted_at"] and (
        not base["posted_at"] or new["posted_at"] < base["posted_at"]
    ):
        base["posted_at"] = new["posted_at"]
    seen = {t.get("ticker") for t in base["financial_info"]}
    for ticker in new["financial_info"]:
        if ticker.get("ticker") not in seen:
            base["financial_info"].append(ticker)
            seen.add(ticker.get("ticker"))
    for key in (*_SCALAR_FIELDS, "url"):
        base[key] = base[key] or new[key]


def find_sources(root: str, skip_dirs: set[str]) -> list[str]:
    paths = []
    for folder, dirs, files in os.walk(root):
        # `images` holds hundreds of thousands of files and no data
        dirs[:] = [
            d
            for d in dirs
            if d != "images"
            and os.path.abspath(os.path.join(folder, d)) not in skip_dirs
        ]
        paths += [
            os.path.join(folder, f) for f in files if f.endswith((".csv", ".jsonl"))
        ]

    def priority(path: str):
        derived = "merged" in os.path.normpath(path).split(os.sep)
        return (not path.endswith(".jsonl"), derived, path)

    return sorted(paths, key=priority)


def load_production_ids(directory: str) -> set[str]:
    ids = set()
    for path in sorted(glob.glob(os.path.join(directory, "tweets-*.jsonl.gz"))):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            ids.update(str(json.loads(line)["id"]) for line in fh)
    return ids


def merge_sources(paths: list[str]) -> tuple[dict[str, dict], list[SourceStats]]:
    tweets: dict[str, dict] = {}
    posts: dict[str, set] = {}  # tweet id -> posting times already counted
    report = []

    for path in paths:
        stats = SourceStats(file=path)
        seen_here = set()
        for record, blank in _read_source(path):
            stats.rows += 1
            if blank:
                stats.blank += 1
                continue
            if record is None:
                stats.no_tweet_id += 1
                continue
            tid = record["tweet_id"]
            seen_here.add(tid)

            # An identical post re-appearing in a derived file adds nothing, so
            # it is skipped entirely (it would only pollute `channels`)
            post_key = (
                record["posted_at"].isoformat() if record["posted_at"] else None,
                tuple(sorted(str(t.get("ticker")) for t in record["financial_info"])),
            )
            if tid not in tweets:
                tweets[tid] = record
                posts[tid] = {post_key}
                stats.new_tweets += 1
                stats.new_posts += 1
            elif post_key not in posts[tid]:
                posts[tid].add(post_key)
                _merge(tweets[tid], record)
                stats.new_posts += 1
        stats.tweets = len(seen_here)
        report.append(stats)

    for tid, record in tweets.items():
        record["n_posts"] = len(posts[tid])
    return tweets, report


def _serialise(record: dict, production_ids: set[str] | None) -> str:
    out = {
        "tweet_id": record["tweet_id"],
        "tweet_created_at": tweet_created_at(int(record["tweet_id"])),
        "first_posted_at": record["posted_at"].isoformat()
        if record["posted_at"]
        else None,
        "n_posts": record["n_posts"],
        "channels": sorted(record["channels"]),
        "message_ids": sorted(record["message_ids"]),
        **{k: record[k] for k in ("url", *_SCALAR_FIELDS)},
        "financial_info": record["financial_info"],
    }
    if production_ids is not None:
        out["in_fintwit_web"] = record["tweet_id"] in production_ids
    return json.dumps(out, ensure_ascii=False)


def print_report(report: list[SourceStats], total: int, overlap: str | None) -> None:
    width = max(len(s.file) for s in report)
    print(
        f"{'file':<{width}} {'rows':>8} {'blank':>7} {'no id':>6} {'new tweets':>11} {'new posts':>10}"
    )
    for s in report:
        verdict = "  <- redundant, can skip" if s.redundant else ""
        print(
            f"{s.file:<{width}} {s.rows:>8,} {s.blank:>7,} {s.no_tweet_id:>6,} {s.new_tweets:>11,} {s.new_posts:>10,}{verdict}"
        )
    print(f"\nunique tweets: {total:,}")
    if overlap:
        print(overlap)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--input", default="scraped", help="Folder searched for CSV/JSONL"
    )
    parser.add_argument("--out", default="scraped/dataset", help="Output folder")
    parser.add_argument(
        "--against",
        metavar="DIR",
        help="fintwit-web export folder (tweets-*.jsonl.gz); adds an "
        "`in_fintwit_web` flag and reports how many tweets it already has",
    )
    args = parser.parse_args()

    out_dir = os.path.abspath(args.out)
    paths = find_sources(args.input, {out_dir})
    if not paths:
        print(f"No CSV or JSONL files under {args.input}", file=sys.stderr)
        return 1

    tweets, report = merge_sources(paths)
    production_ids = load_production_ids(args.against) if args.against else None

    os.makedirs(out_dir, exist_ok=True)
    ordered = sorted(tweets, key=int)
    with gzip.open(
        os.path.join(out_dir, "tweets.jsonl.gz"), "wt", encoding="utf-8"
    ) as fh:
        for tid in ordered:
            fh.write(_serialise(tweets[tid], production_ids) + "\n")
    with open(os.path.join(out_dir, "known_tweet_ids.txt"), "w") as fh:
        fh.write("\n".join(ordered) + "\n")

    overlap = None
    if production_ids is not None:
        shared = sum(1 for tid in ordered if tid in production_ids)
        overlap = (
            f"already in fintwit-web export: {shared:,}\n"
            f"only in the Discord scrapes: {len(ordered) - shared:,}"
        )
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {
                "unique_tweets": len(ordered),
                "sources": [{**asdict(s), "redundant": s.redundant} for s in report],
            },
            fh,
            indent=2,
        )

    print_report(report, len(ordered), overlap)
    print(f"\nwritten to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
