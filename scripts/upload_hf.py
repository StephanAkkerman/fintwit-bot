"""Split the merged tweets by category and upload them to Hugging Face.

Build locally first (nothing is sent), inspect ``scraped/hf_upload/``, then push:

    python scripts/upload_hf.py --exclude-ids subscriber_ids.txt
    python scripts/upload_hf.py --exclude-ids subscriber_ids.txt --push

Reads ``scraped/dataset/tweets.jsonl.gz`` (from ``merge_scraped.py``). A tweet
goes into every subset it was posted in: ``crypto``, ``stocks``, or ``other``
(everything else); ``all`` holds every tweet.

Uploading needs write access to the repos: set ``HF_TOKEN`` or run
``hf auth login``. Existing files in the repos (the old CSVs) are kept unless
``--delete-old-csv`` is given; the dataset card is pointed at the new data so
``load_dataset`` ignores them either way.
"""

import argparse
import gzip
import json
import os
import re
import sys
from dataclasses import dataclass

OWNER = "StephanAkkerman"
REPOS = {
    "crypto": f"{OWNER}/financial-tweets-crypto",
    "stocks": f"{OWNER}/financial-tweets-stocks",
    "other": f"{OWNER}/financial-tweets-other",
    "all": f"{OWNER}/financial-tweets",
}
DATA_FILE = "data/train.jsonl.gz"
# Discord message ids and the production-DB flag mean nothing outside this setup
PUBLIC_COLUMNS = (
    "tweet_id",
    "tweet_created_at",
    "first_posted_at",
    "n_posts",
    "channels",
    "url",
    "user_name",
    "description",
    "embed_title",
    "tweet_type",
    "media_kind",
    "image_url",
    "thumbnail_url",
    "sentiment",
    "financial_info",
)
MARKER_START, MARKER_END = "<!-- generated:start -->", "<!-- generated:end -->"
# The single CSV each repo has held since 2024-09-05
LEGACY_CSV = {
    "crypto": "crypto.csv",
    "stocks": "stock.csv",
    "other": "other.csv",
    "all": "financial_tweets.csv",
}
# The old cards describe the CSV columns under these headings, up to the next
# level-2 heading (or the end)
_OLD_FIELDS = re.compile(
    r"^##+ (?:Data Fields|Data Description|Dataset Fields)\b.*?(?=^## |\Z)",
    re.DOTALL | re.MULTILINE,
)


@dataclass
class SubsetStats:
    rows: int = 0
    first: str | None = None
    last: str | None = None

    def add(self, created_at: str) -> None:
        self.rows += 1
        self.first = min(self.first or created_at, created_at)
        self.last = max(self.last or created_at, created_at)


def subsets_for(channels: list[str]) -> list[str]:
    crypto = any(c.startswith("crypto") for c in channels)
    stocks = any(c.startswith("stocks") for c in channels)
    names = ["all"]
    if crypto:
        names.append("crypto")
    if stocks:
        names.append("stocks")
    if not (crypto or stocks):
        names.append("other")
    return names


def load_ids(path: str) -> set[str]:
    with open(path, encoding="utf-8") as fh:
        return {line.strip() for line in fh if line.strip()}


def build_subsets(
    src: str, out_dir: str, names: list[str], excluded: set[str]
) -> tuple[dict[str, SubsetStats], int]:
    """Stream ``src`` once, writing one data file per wanted subset."""
    stats = {n: SubsetStats() for n in names}
    writers = {}
    for name in names:
        path = os.path.join(out_dir, name, DATA_FILE)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        writers[name] = gzip.open(path, "wt", encoding="utf-8")

    dropped = 0
    try:
        with gzip.open(src, "rt", encoding="utf-8") as fh:
            for line in fh:
                record = json.loads(line)
                if record["tweet_id"] in excluded:
                    dropped += 1
                    continue
                out = json.dumps(
                    {k: record.get(k) for k in PUBLIC_COLUMNS}, ensure_ascii=False
                )
                for name in subsets_for(record["channels"]):
                    if name in writers:
                        writers[name].write(out + "\n")
                        stats[name].add(record["tweet_created_at"])
    finally:
        for w in writers.values():
            w.close()
    return stats, dropped


def _size_category(n: int) -> str:
    for limit, label in (
        (1_000, "n<1K"),
        (10_000, "1K<n<10K"),
        (100_000, "10K<n<100K"),
        (1_000_000, "100K<n<1M"),
        (10_000_000, "1M<n<10M"),
    ):
        if n < limit:
            return label
    return "10M<n<100M"


def _body(
    name: str, stats: SubsetStats, excluded: int | None, keep_legacy: bool
) -> str:
    scope = {
        "all": "every tweet",
        "crypto": "tweets posted to the crypto channels",
        "stocks": "tweets posted to the stocks channels",
        "other": "tweets that were in neither the crypto nor stocks channels "
        "(news, images, other, forex)",
    }[name]
    lines = [
        MARKER_START,
        "## Contents",
        "",
        f"{stats.rows:,} tweets ({scope}), sent between {stats.first[:10]} and "
        f"{stats.last[:10]}, collected by "
        "[fintwit-bot](https://github.com/StephanAkkerman/fintwit-bot). One row "
        "per tweet; the same tweet is often posted several times by the bot (once "
        "per ticker), so `financial_info` combines all of them.",
        "",
        "| Column | Meaning |",
        "|---|---|",
        "| `tweet_id` | Tweet id (string) |",
        "| `tweet_created_at` | When the tweet was sent, decoded from its id |",
        "| `first_posted_at` | When the bot first posted it; the bot can lag by "
        "minutes, and this is null for older rows |",
        "| `n_posts` | How many times the bot posted this tweet |",
        "| `channels` | Source channels, e.g. `crypto_charts`, `twitter_news` |",
        "| `user_name` | Poster's display name |",
        "| `description` | Tweet text |",
        "| `tweet_type` | `tweet`, `quote tweet` or `retweet` |",
        "| `media_kind` | `Video` / `GIF` when the tweet had one |",
        "| `image_url`, `thumbnail_url` | Tweet image / poster's profile picture |",
        "| `sentiment` | Sentiment label the bot assigned |",
        "| `financial_info` | Per ticker: price and change when the bot posted, "
        "exchanges, and 4h / 1d technical-analysis summaries |",
        "",
        "Retweets and quotes point at the original tweet, so `tweet_created_at` "
        "can be older than the rest of the data. Discord-hosted image links "
        "expire.",
        "",
        "The previous version of this dataset (columns `tweet_text`, "
        "`price_of_ticker`, `tickers_mentioned`, …, up to 2024-09-05) is "
        + (
            f'available as `load_dataset("{REPOS[name]}", "legacy")`.'
            if keep_legacy
            else "in the repository history."
        ),
    ]
    if excluded is not None:
        lines += [
            "",
            "Tweets flagged as subscriber-only in the source database were removed.",
        ]
    lines.append(MARKER_END)
    return "\n".join(lines)


def write_card(
    name: str,
    repo_id: str,
    stats: SubsetStats,
    out_dir: str,
    excluded: int | None,
    keep_legacy: bool,
):
    """Update the existing card in place (keeping license/tags) and save it.

    The old description of the CSV columns is dropped, since it would
    contradict the new schema; the legacy CSV stays loadable as its own config.
    """
    from huggingface_hub import DatasetCard

    try:
        card = DatasetCard.load(repo_id)
    except Exception as e:  # offline, or a brand new repo
        print(
            f"[{name}] couldn't load existing card ({type(e).__name__}); using a new one"
        )
        card = DatasetCard("---\nlicense: mit\nlanguage:\n- en\n---\n")

    configs = [
        {
            "config_name": "default",
            "default": True,
            "data_files": [{"split": "train", "path": DATA_FILE}],
        }
    ]
    if keep_legacy:
        configs.append(
            {
                "config_name": "legacy",
                "data_files": [{"split": "train", "path": LEGACY_CSV[name]}],
            }
        )
    card.data.configs = configs
    card.data.size_categories = [_size_category(stats.rows)]

    section = _body(name, stats, excluded, keep_legacy)
    text = card.text or ""
    if MARKER_START not in text:
        text = _OLD_FIELDS.sub("", text)
    if MARKER_START in text and MARKER_END in text:
        head, rest = text.split(MARKER_START, 1)
        tail = rest.split(MARKER_END, 1)[1]
        card.text = head + section + tail
    else:
        card.text = (text.rstrip() + "\n\n" if text.strip() else "") + section + "\n"
    card.save(os.path.join(out_dir, name, "README.md"))


def push(name: str, repo_id: str, out_dir: str, delete_csv: bool) -> None:
    from huggingface_hub import HfApi

    api = HfApi()
    remote = api.list_repo_files(repo_id, repo_type="dataset")
    print(f"[{name}] {repo_id} currently has: {', '.join(remote)}")
    api.upload_folder(
        folder_path=os.path.join(out_dir, name),
        repo_id=repo_id,
        repo_type="dataset",
        commit_message="Replace with merged Discord + Twitter scrape (JSONL)",
        delete_patterns=["*.csv"] if delete_csv else None,
    )
    print(f"[{name}] pushed -> https://huggingface.co/datasets/{repo_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--input", default="scraped/dataset/tweets.jsonl.gz")
    parser.add_argument("--out", default="scraped/hf_upload")
    parser.add_argument(
        "--repos",
        default=",".join(REPOS),
        help=f"Comma separated subset of: {', '.join(REPOS)}",
    )
    parser.add_argument(
        "--exclude-ids",
        metavar="FILE",
        help="Tweet ids (one per line) to leave out, e.g. subscriber-only tweets",
    )
    parser.add_argument(
        "--allow-unfiltered",
        action="store_true",
        help="Publish without --exclude-ids (subscriber tweets can't be told apart "
        "in the Discord data)",
    )
    parser.add_argument(
        "--push", action="store_true", help="Upload (default: build only)"
    )
    parser.add_argument(
        "--delete-old-csv",
        action="store_true",
        help="With --push, remove the old *.csv files from each repo",
    )
    args = parser.parse_args()

    names = [n.strip() for n in args.repos.split(",") if n.strip()]
    unknown = [n for n in names if n not in REPOS]
    if unknown:
        parser.error(f"unknown repos {unknown}; choose from {list(REPOS)}")
    if not args.exclude_ids and not args.allow_unfiltered:
        parser.error(
            "pass --exclude-ids FILE to drop subscriber tweets, or --allow-unfiltered "
            "to publish everything"
        )
    if not os.path.exists(args.input):
        parser.error(f"{args.input} not found; run merge_scraped.py first")

    excluded = load_ids(args.exclude_ids) if args.exclude_ids else set()
    stats, dropped = build_subsets(args.input, args.out, names, excluded)

    for name in names:
        if stats[name].rows == 0:
            print(f"[{name}] no rows, skipping", file=sys.stderr)
            continue
        write_card(
            name,
            REPOS[name],
            stats[name],
            args.out,
            len(excluded) if args.exclude_ids else None,
            keep_legacy=not args.delete_old_csv,
        )
        s = stats[name]
        print(f"[{name}] {s.rows:>8,} rows  {s.first[:10]} .. {s.last[:10]}")
    if args.exclude_ids:
        print(f"excluded {dropped:,} tweets listed in {args.exclude_ids}")

    if not args.push:
        print(f"\nBuilt in {args.out}. Review it, then re-run with --push.")
        return 0

    from huggingface_hub import HfApi

    print(f"\nlogged in to Hugging Face as {HfApi().whoami()['name']}")
    for name in names:
        if stats[name].rows:
            push(name, REPOS[name], args.out, args.delete_old_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
