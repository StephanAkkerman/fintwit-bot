"""Scrape the bot's own embeds from the Discord server into JSONL datasets.

Run with ``python scripts/scraper.py [--after DD/MM/YYYY]``. Every channel in
``CATEGORY_CHANNEL_DICT`` is written to ``scraped/<category>_<channel>.jsonl``,
one embed per line. Re-running resumes after the last stored message of each
file, so ``--after`` only matters for a channel's first run.

Each record keeps the untouched embed under ``raw_embed``, so the parsing can
be improved later without scraping Discord again.
"""

import argparse
import asyncio
import datetime
import json
import os
import re
import sys
from pathlib import Path

import aiohttp
import discord
import pandas as pd
from tqdm.asyncio import tqdm

# This lives outside src/, but reuses the bot's logger and token loading
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from constants.logger import logger  # noqa: E402
from main import get_token  # noqa: E402

SCRAPE_DIR = "scraped"
DEFAULT_AFTER = "05/09/2024"  # DD/MM/YYYY

# The channels to scrape from, and the categories they belong to
CATEGORY_CHANNEL_DICT = {
    "▬▬▬ 🎰 Crypto ▬▬▬": [
        "📈┃charts",
        "💬┃text",
    ],
    "▬▬▬ 💵 Stocks ▬▬▬": [
        "📈┃charts",
        "💬┃text",
    ],
    "▬▬▬ 🐦Twitter ▬▬▬": [
        "📈┃unknown-charts",
        "❓┃other",
        "📷┃images",
        "📰┃news",
    ],
}

client = discord.Client()
_after = DEFAULT_AFTER
_finished = False


# Call this to start the on_ready event
def start_scraper(after: str = DEFAULT_AFTER):
    global _after
    _after = after
    try:
        client.run(get_token())
    except RuntimeError as e:
        # client.close() shuts the HTTP session before it marks the client as
        # closed, so the gateway loop can retry once more on the dead session.
        # That's only noise once scraping is done; before then it's a real error.
        if not (_finished and "Session is closed" in str(e)):
            raise


@client.event
async def on_ready():
    global _finished
    logger.info(f"Logged in as {client.user}")
    # Without the finally, an error here leaves client.run() hanging forever
    try:
        await scrape_all(_after)
        _finished = True
    finally:
        await client.close()


async def scrape_all(after: str = DEFAULT_AFTER):
    """Scrape every configured channel; one failing channel doesn't stop the rest."""
    for category, channels in CATEGORY_CHANNEL_DICT.items():
        for channel in channels:
            try:
                count = await fetch_embeds(category, channel, after=after)
                logger.info(f"{category} {channel}: {count} new embeds")
            except Exception:
                logger.exception(f"Scraping {category} {channel} failed")


def extract_text(input_string):
    # Regular expression to remove emojis, special characters, and symbols
    # Keep only alphabetic characters, spaces, and digits if needed
    return re.sub(r"[^\w\s]", "", input_string).strip()


def find_channel(category: str, channel_name: str):
    """Return the text channel with this name inside this category, else None."""
    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.name != channel_name:
                continue
            if not category or (channel.category and channel.category.name == category):
                return channel
    return None


def output_path(category: str, channel_name: str) -> str:
    name = f"{extract_text(category)}_{extract_text(channel_name)}"
    return os.path.join(SCRAPE_DIR, f"{name}.jsonl")


def resume_point(path: str) -> int | None:
    """Message id of the last complete record in ``path``, or None if empty.

    A crash mid-write can leave a half-written last line; it is cut off so the
    next append starts on a clean line.
    """
    last_id = None
    good_end = offset = 0
    with open(path, "rb+") as fh:
        for raw in fh:
            offset += len(raw)
            try:
                last_id = int(json.loads(raw)["message_id"])
            except (ValueError, KeyError):
                break
            good_end = offset
        fh.truncate(good_end)
    return last_id


async def fetch_embeds(
    category: str = "▬▬▬ 🎰 Crypto ▬▬▬",
    channel_name: str = "📈┃charts",
    after: str = DEFAULT_AFTER,
    flush_every: int = 500,
) -> int:
    """Append the bot's embeds from one channel to its JSONL file.

    Returns the number of embeds written during this run.
    """
    channel = find_channel(category, channel_name)
    if channel is None:
        logger.error(f"Channel {channel_name} not found in category {category}")
        return 0

    os.makedirs(SCRAPE_DIR, exist_ok=True)
    path = output_path(category, channel_name)

    resume_id = resume_point(path) if os.path.exists(path) else None
    if resume_id:
        start = discord.Object(id=resume_id)
        logger.info(f"Resuming {path} after message {resume_id}")
    else:
        start = datetime.datetime.strptime(after, "%d/%m/%Y").replace(
            tzinfo=datetime.timezone.utc
        )

    written = unflushed = 0
    with (
        open(path, "a", encoding="utf-8") as out,
        tqdm(desc=os.path.basename(path), unit="embed") as pbar,
    ):
        try:
            async for message in channel.history(
                limit=None, after=start, oldest_first=True
            ):
                # Only the bot's own embeds, not anything users wrote
                if message.author.id != client.user.id or not message.embeds:
                    continue

                # One write per message so a crash can't split its embeds
                lines = [
                    json.dumps(
                        build_record(message, category, channel_name, i, embed),
                        ensure_ascii=False,
                    )
                    + "\n"
                    for i, embed in enumerate(message.embeds)
                ]
                out.write("".join(lines))
                written += len(lines)
                unflushed += len(lines)
                pbar.update(len(lines))

                if unflushed >= flush_every:
                    out.flush()
                    unflushed = 0
        except discord.HTTPException:
            # Everything written so far is kept; the next run resumes from it
            logger.exception(f"Stopped early while scraping {path}")
    return written


def build_record(message, category: str, channel_name: str, index: int, embed) -> dict:
    raw = embed.to_dict()
    return {
        # Ids are strings: they exceed what JSON numbers hold exactly in most tools
        "message_id": str(message.id),
        "embed_index": index,
        "category": category,
        "channel": channel_name,
        "message_created_at": message.created_at.isoformat(),
        **format_embed(raw),
        "raw_embed": raw,
    }


_TWEET_ID = re.compile(r"/status/(\d+)")


def format_embed(data: dict) -> dict:
    fields = data.get("fields", [])

    # The last field is the sentiment, so we extract it separately
    sentiment_field = (
        fields[-1] if fields and "Sentiment" in fields[-1].get("name", "") else None
    )
    sentiment = (
        safe_extract_value(sentiment_field, separator="- ", sub_index=-1)
        if sentiment_field
        else None
    )

    # Extract financial information from the remaining fields
    ticker_data_list = extract_ticker_data(fields[:-1] if sentiment_field else fields)

    image = data.get("image") or {}
    thumbnail = data.get("thumbnail") or {}
    author = data.get("author") or {}
    footer = (data.get("footer") or {}).get("text", "").strip()
    title = data.get("title") or ""
    url = data.get("url") or author.get("url")
    tweet_id = _TWEET_ID.search(url or "")

    return {
        # `timestamp` is when the bot posted the embed, not when the tweet was sent
        "timestamp": data.get("timestamp"),
        "tweet_id": tweet_id.group(1) if tweet_id else None,
        "url": url,
        "user_name": author.get("name"),
        "embed_title": title,
        "description": data.get("description"),
        # Video / GIF are only marked in the footer; the embed shows a still
        "media_kind": footer or None,
        "image_url": image.get("url"),
        "proxy_image_url": image.get("proxy_url"),
        "image_dimensions": [image.get("width"), image.get("height")],
        # The thumbnail is the poster's profile picture
        "thumbnail_url": thumbnail.get("url"),
        "proxy_thumbnail_url": thumbnail.get("proxy_url"),
        "thumbnail_dimensions": [thumbnail.get("width"), thumbnail.get("height")],
        "tweet_type": (
            "retweet"
            if "retweeted" in title
            else ("quote tweet" if "quote" in title else "tweet")
        ),
        "financial_info": ticker_data_list,
        "sentiment": sentiment,
    }


# Matches "$123.4\n(+1.2%)" and the after-hours variant "AH: $123.4\n(+1.2%)".
# The price is any run of non-space characters so integers, thousands separators
# and scientific notation ("1e-05") parse too.
_QUOTE = re.compile(r"(AH:\s*)?\$\s*([^\s(]+)\s*\(([^)]+)\)")


def extract_quotes(input_string):
    """Return (regular, after_hours) as (price, change) pairs; missing ones are None."""
    regular = after_hours = None
    for match in _QUOTE.finditer(input_string or ""):
        quote = (match.group(2), match.group(3).strip().split()[0])
        if match.group(1):
            after_hours = after_hours or quote
        else:
            regular = regular or quote
    return regular, after_hours


# Utility function to extract price and percentage change from a string
def extract_price_and_change(input_string):
    regular, _ = extract_quotes(input_string)
    return regular if regular else (None, None)


# Utility function to split and clean the value from the "fields" dictionary
def safe_extract_value(field, index=0, separator="\n", sub_index=0, replace_dict=None):
    if field and "value" in field:
        try:
            value_parts = field["value"].split(separator)
            result = value_parts[sub_index].strip()
            if replace_dict:
                for old, new in replace_dict.items():
                    result = result.replace(old, new)
            return result
        except (IndexError, KeyError):
            return None
    return None


# Regular expression to extract exchange names
exchange_pattern = r"<:(\w+):\d+>"

# Where the price links to tells crypto (CoinGecko) from stocks (Yahoo Finance)
_LINK = re.compile(r"\]\((https?://[^)\s]+)\)")

_TA_REPLACE = {"📈": " buy,", "⌛️": " hold,", "📉": " sell"}


# Function to extract data for multiple tickers
def extract_ticker_data(fields):
    ticker_data_list = []
    current_ticker = None

    for field in fields:
        name = field.get("name", "")
        # Detect ticker by '$' in 'name'
        if "$" in name:
            value = field.get("value", "")
            regular, after_hours = extract_quotes(value)
            link = _LINK.search(value)
            current_ticker = {
                "ticker": name.split(" ")[0],
                "exchanges": re.findall(exchange_pattern, name),
                "price": regular[0] if regular else None,
                "percentage_change": regular[1] if regular else None,
                "after_hours_price": after_hours[0] if after_hours else None,
                "after_hours_change": after_hours[1] if after_hours else None,
                "source_url": link.group(1) if link else None,
            }
            ticker_data_list.append(current_ticker)
        # Extract '4h TA' and '1d TA' for the current ticker
        elif current_ticker and "TA" in name:
            for period in ("4h", "1d"):
                if period in name:
                    current_ticker[f"{period}_ta_result"] = safe_extract_value(
                        field, sub_index=0
                    )
                    current_ticker[f"{period}_ta_details"] = safe_extract_value(
                        field, sub_index=1, replace_dict=_TA_REPLACE
                    )

    return ticker_data_list


def read_records(path: str):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


async def download_image(session, semaphore, name, url, images_directory, retries=3):
    """Download one image as ``<name>.<ext>``; returns an error string or None."""
    error = None
    for attempt in range(retries):
        try:
            async with semaphore, session.get(url) as response:
                if response.status == 200:
                    ext = _EXTENSIONS.get(response.content_type, ".png")
                    with open(os.path.join(images_directory, name + ext), "wb") as f:
                        f.write(await response.read())
                    return None
                error = f"status {response.status}"
                # Expired or deleted images won't come back, don't hammer them
                if response.status in (403, 404, 410):
                    break
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            error = str(e) or type(e).__name__
        await asyncio.sleep(2**attempt)
    return f"{name}: {error} ({url})"


async def download_imgs(jsonl_file: str, images_directory: str | None = None):
    """Download every embed image of a scraped JSONL file.

    Files are named after the tweet id (message id as fallback); ones already
    on disk are skipped, so this can be re-run. Discord CDN links expire, so
    run this soon after scraping.
    """
    stem = os.path.splitext(os.path.basename(jsonl_file))[0]
    images_directory = images_directory or os.path.join(
        SCRAPE_DIR, "images", stem.replace("_", "-"), "unlabeled"
    )
    os.makedirs(images_directory, exist_ok=True)
    existing = {os.path.splitext(f)[0] for f in os.listdir(images_directory)}

    wanted = {}
    for record in read_records(jsonl_file):
        name = record.get("tweet_id") or record["message_id"]
        if record.get("image_url") and name not in existing:
            wanted[name] = record["image_url"]

    semaphore = asyncio.Semaphore(16)
    async with aiohttp.ClientSession() as session:
        results = await tqdm.gather(
            *(
                download_image(session, semaphore, name, url, images_directory)
                for name, url in wanted.items()
            ),
            desc="Downloading images",
        )

    failures = [r for r in results if r]
    logger.info(f"Downloaded {len(wanted) - len(failures)}/{len(wanted)} images")
    for failure in failures[:20]:
        logger.warning(failure)
    return failures


# --- Helpers for the older CSV scrapes (scraped/<date>/*.csv) ---------------


def merge_files(base_filename="Crypto_charts.csv", directory="scraped/"):
    # Derive the paths for the original and new files based on naming convention
    file_1 = os.path.join(directory, base_filename)
    file_2 = os.path.join(directory, f"new_{base_filename}")

    # Check if both files exist
    if not os.path.exists(file_1):
        print(f"File {file_1} not found.")
        return
    if not os.path.exists(file_2):
        print(f"File {file_2} not found.")
        return

    # Load both CSV files
    df1 = pd.read_csv(file_1)
    df2 = pd.read_csv(file_2)

    # Merge the two DataFrames
    merged_df = pd.concat([df1, df2], ignore_index=True)

    # Drop duplicates
    merged_df.drop_duplicates(subset=["description", "url"], inplace=True)

    # Drop rows with all missing values
    merged_df.dropna(how="all", inplace=True)

    # Save the merged data to a new file
    merged_filename = os.path.join(directory, f"merged_{base_filename}")
    merged_df.to_csv(merged_filename, index=False)

    print(f"Files merged and saved to {merged_filename}")

    return merged_df


def merge_all_files(directory="scraped/"):
    # Get all files in the directory
    for file in os.listdir(directory):
        # Check if the file is not a "new_" file and has a matching "new_" counterpart
        if (
            file.endswith(".csv")
            and not file.startswith("new_")
            and not file.startswith("merged_")
        ):
            merge_files(file, directory=directory)


def create_combined_csv(dir: str = "scraped/merged"):
    # List to hold dataframes from each CSV file
    all_dataframes = []

    # Loop over all CSV files in the directory
    for file in os.listdir(dir):
        if file.endswith(".csv"):
            file_path = os.path.join(dir, file)
            # Read the CSV file into a DataFrame
            df = pd.read_csv(file_path)
            all_dataframes.append(df)

    # Concatenate all the DataFrames into one
    combined_df = pd.concat(all_dataframes, ignore_index=True)

    # Drop duplicate rows
    combined_df.drop_duplicates(inplace=True)

    # Remove rows where all values are missing
    combined_df.dropna(how="all", inplace=True)

    # Save the combined DataFrame to a new CSV file
    output_file = os.path.join(dir, "financial_tweets.csv")
    combined_df.to_csv(output_file, index=False)

    print(f"Combined CSV saved to {output_file}")


def merge_csvs(files: list, output_file: str = "merged.csv"):
    dfs = []

    files = [f"scraped/merged/{file}" for file in files]

    # Merge the csv files into one
    for file in files:
        if not os.path.exists(file):
            print(f"File {file} not found.")
            return
        df = pd.read_csv(file)
        dfs.append(df)

    merged_df = pd.concat(dfs, ignore_index=True)
    merged_df.to_csv(f"scraped/merged/{output_file}", index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--after",
        default=DEFAULT_AFTER,
        help="DD/MM/YYYY to start from for channels with no file yet "
        f"(default {DEFAULT_AFTER})",
    )
    start_scraper(parser.parse_args().after)
