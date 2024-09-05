import ast
import asyncio
import datetime
import os
import re

import aiohttp
import discord
import pandas as pd

# from tqdm import tqdm
from tqdm.asyncio import tqdm

from constants.logger import logger
from main import get_token

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


# Call this to start the on_ready event
def start_scraper():
    client.run(get_token())


@client.event
async def on_ready():
    logger.info(f"Logged in as {client.user}")
    await scrape_all()
    await client.close()


async def scrape_all():
    for category, channels in CATEGORY_CHANNEL_DICT.items():
        for channel in channels:
            await fetch_embeds(category, channel)


def extract_text(input_string):
    # Regular expression to remove emojis, special characters, and symbols
    # Keep only alphabetic characters, spaces, and digits if needed
    return re.sub(r"[^\w\s]", "", input_string).strip()


async def fetch_embeds(
    category: str = "▬▬▬ 🎰 Crypto ▬▬▬",
    channel_name: str = "📈┃charts",
    after: str = "15/11/2023",
    checkpoint: int = 5000,
):
    after = datetime.datetime.strptime(after, "%d/%m/%Y")

    data = []
    category_formatted = extract_text(category)
    channel_name_formatted = extract_text(channel_name)
    file_name = f"scraped/{category_formatted}_{channel_name_formatted}"
    print(file_name)

    if category:
        for guild in client.guilds:
            for channel in guild.channels:
                if channel.name == channel_name:
                    # Find the right channel in the right category
                    if channel.category.name == category:
                        break
    counter = 0

    if not channel:
        logger.error(f"Channel {channel_name} not found")
        return

    # Progress bar with unknown total
    pbar = tqdm(desc="Fetching embeds", total=0, unit="message", leave=True)

    try:
        async for message in channel.history(
            limit=None, before=None, after=after, around=None
        ):
            # Filter on messages from the bot and with embeds
            if message.author.id == client.user.id and message.embeds:
                # Loop through each embed in the message
                for embed in message.embeds:
                    counter += 1
                    # Update the progress bar manually since total is unknown
                    pbar.update(1)

                    # Format the data before saving it
                    data.append(format_embed(embed.to_dict()))

                    # Optionally save every N messages
                    if counter % checkpoint == 0:
                        df = pd.DataFrame(data)
                        df.to_csv(f"{file_name}_partial.csv", index=False)

    except Exception as e:
        logger.info(f"An error occurred: {e}")
    finally:
        df = pd.DataFrame(data)
        df.to_csv(f"{file_name}.csv", index=False)


def format_embed(data: dict) -> dict:
    # Convert string representations to actual Python objects
    parsed_data = convert_string_to_object(data)

    # Extract important information for tickers
    fields = parsed_data.get("fields", [])

    # The last field is the sentiment, so we extract it separately
    sentiment_field = (
        fields[-1] if len(fields) > 0 and "Sentiment" in fields[-1]["name"] else None
    )
    sentiment = (
        safe_extract_value(sentiment_field, separator="- ", sub_index=-1)
        if sentiment_field
        else None
    )

    # Remove the sentiment field before processing the financial information
    fields = fields[:-1] if sentiment_field else fields

    # Extract financial information from remaining fields
    ticker_data_list = extract_ticker_data(fields)

    # Add the financial information as a new key 'financial_info' and the sentiment separately
    parsed_data["financial_info"] = ticker_data_list
    parsed_data["sentiment"] = sentiment

    # Handle possible NaN values for 'image', 'thumbnail', 'title', and other fields
    image_data = parsed_data.get("image", {})
    thumbnail_data = parsed_data.get("thumbnail", {})
    title_data = parsed_data.get("title", "")

    # Ensure the image, thumbnail, and title fields are the correct type
    if not isinstance(image_data, dict):
        image_data = {}

    if not isinstance(thumbnail_data, dict):
        thumbnail_data = {}

    # Ensure the title is a string (handle NaN or float values)
    if not isinstance(title_data, str):
        title_data = ""

    # Now, you can print the full updated dictionary, including image, thumbnail, and financial information
    extracted_data = {
        # Image handling: Check if 'image' exists in parsed_data and if it has the required subfields
        "image_url": image_data.get("url"),
        "proxy_image_url": image_data.get("proxy_url"),
        "image_dimensions": (
            image_data.get("width"),
            image_data.get("height"),
        ),
        # Thumbnail handling: Same approach as image
        "thumbnail_url": thumbnail_data.get("url"),
        "proxy_thumbnail_url": thumbnail_data.get("proxy_url"),
        "thumbnail_dimensions": (
            thumbnail_data.get("width"),
            thumbnail_data.get("height"),
        ),
        # Basic fields that are expected to be present
        "timestamp": parsed_data.get("timestamp"),
        "description": parsed_data.get("description"),
        "url": parsed_data.get("url"),
        # Embed title - ensure it's a string
        "embed_title": title_data,
        # Tweet type logic - ensure that 'title' is a string
        "tweet_type": (
            "retweet"
            if "retweeted" in title_data
            else ("quote tweet" if "quote" in title_data else "tweet")
        ),
        # Financial info and sentiment, if available
        "financial_info": parsed_data["financial_info"],
        "sentiment": parsed_data["sentiment"],
    }

    return extracted_data


# Function to convert string representations to Python objects (dicts, lists)
def convert_string_to_object(data):
    for key, value in data.items():
        if isinstance(value, str) and (value.startswith("{") or value.startswith("[")):
            try:
                data[key] = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                print(f"Error parsing {key}, leaving as string.")
    return data


# Utility function to extract price and percentage change from a string
def extract_price_and_change(input_string):
    regex_pattern = r"\$\s*(\d+\.\d+)\s*\n*\s*\(([^)]+)\)"
    match = re.search(regex_pattern, input_string)
    if match:
        price = match.group(1)
        price_change = match.group(2).strip().split()[0]
        return price, price_change
    return None, None


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


# Function to extract data for multiple tickers
def extract_ticker_data(fields):
    ticker_data_list = []
    current_ticker = None

    for field in fields:
        # Detect ticker by '$' in 'name'
        if "name" in field and "$" in field["name"]:
            price, change = extract_price_and_change(field["value"])
            current_ticker = {
                "ticker": field["name"].split(" ")[0],
                "exchanges": re.findall(exchange_pattern, field["name"]),
                "price": price,
                "percentage_change": change,
            }
            ticker_data_list.append(current_ticker)
        # Extract '4h TA' and '1d TA' for the current ticker
        elif current_ticker and "TA" in field["name"]:
            if "4h" in field["name"]:
                current_ticker["4h_ta_result"] = safe_extract_value(field, sub_index=0)
                current_ticker["4h_ta_details"] = safe_extract_value(
                    field,
                    sub_index=1,
                    replace_dict={"📈": " buy,", "⌛️": " hold,", "📉": " sell"},
                )
            elif "1d" in field["name"]:
                current_ticker["1d_ta_result"] = safe_extract_value(field, sub_index=0)
                current_ticker["1d_ta_details"] = safe_extract_value(
                    field,
                    sub_index=1,
                    replace_dict={"📈": " buy,", "⌛️": " hold,", "📉": " sell"},
                )

    return ticker_data_list


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


async def download_image(session, index, url, images_directory):
    filename = f"{images_directory}/{index}.png"
    try:
        async with session.get(url) as response:
            if response.status == 200:
                with open(filename, "wb") as f:
                    while True:
                        chunk = await response.content.read(1024)
                        if not chunk:
                            break
                        f.write(chunk)
            else:
                return f"Failed to download image {index} with status code {response.status}"
    except Exception as e:
        return f"An error occurred at index {index}: {e}"


async def download_imgs(csv_file="crypto_charts"):
    file = f"scraped/{csv_file}.csv"
    df = pd.read_csv(file)
    last_image_index = 3242
    images_directory = f"scraped/images/{csv_file.replace('_', '-')}/unlabeled"

    # Create the directory if it does not exist
    os.makedirs(images_directory, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        tasks = []
        for index, row in df.iloc[last_image_index + 1 :].iterrows():
            image_data = row.get("image")
            if image_data and isinstance(image_data, str):
                image_data = ast.literal_eval(image_data)
                if "url" in image_data:
                    # TODO: only download if it's not a duplicate
                    url = image_data["url"]
                    tasks.append(download_image(session, index, url, images_directory))

        results = [asyncio.create_task(task) for task in tasks]
        for result in tqdm(asyncio.as_completed(results), total=len(results)):
            await result


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
    start_scraper()
