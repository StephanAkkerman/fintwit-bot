import datetime
import glob
import json
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from xml.etree import ElementTree

import aiohttp
import pandas as pd
import requests
from tqdm import tqdm

from util.vars import get_json_data, logger


# Use in loop: fudning_heatmap
class BinanceClient(object):
    # https://github.com/AlchemyHub/A1chemy/blob/master/a1chemy/data_source/binance.py
    def __init__(self) -> None:
        self.headers = {
            "authority": "www.binance.com",
            "x-trace-id": "c829406a-6c1f-45b6-a55a-cec1bb858ad1",
            "csrftoken": "d41d8cd98f00b204e9800998ecf8427e",
            "x-ui-request-trace": "c829406a-6c1f-45b6-a55a-cec1bb858ad1",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
            "content-type": "application/json",
            "lang": "zh-CN",
            "fvideo-id": "31b3fe32b4dba62987d3203e5ad881d76b6fef2a",
            "sec-ch-ua-mobile": "?0",
            "device-info": "eyJzY3JlZW5fcmVzb2x1dGlvbiI6IjI1NjAsMTQ0MCIsImF2YWlsYWJsZV9zY3JlZW5fcmVzb2x1dGlvbiI6IjI1NjAsMTM1MiIsInN5c3RlbV92ZXJzaW9uIjoiTWFjIE9TIDEwLjE1LjciLCJicmFuZF9tb2RlbCI6InVua25vd24iLCJzeXN0ZW1fbGFuZyI6ImVuIiwidGltZXpvbmUiOiJHTVQrOCIsInRpbWV6b25lT2Zmc2V0IjotNDgwLCJ1c2VyX2FnZW50IjoiTW96aWxsYS81LjAgKE1hY2ludG9zaDsgSW50ZWwgTWFjIE9TIFggMTBfMTVfNykgQXBwbGVXZWJLaXQvNTM3LjM2IChLSFRNTCwgbGlrZSBHZWNrbykgQ2hyb21lLzkyLjAuNDUxNS4xNTkgU2FmYXJpLzUzNy4zNiIsImxpc3RfcGx1Z2luIjoiQ2hyb21lIFBERiBQbHVnaW4sQ2hyb21lIFBERiBWaWV3ZXIsTmF0aXZlIENsaWVudCIsImNhbnZhc19jb2RlIjoiYTMxMWNjZTEiLCJ3ZWJnbF92ZW5kb3IiOiJJbnRlbCBJbmMuIiwid2ViZ2xfcmVuZGVyZXIiOiJJbnRlbCBJcmlzIFBybyBPcGVuR0wgRW5naW5lIiwiYXVkaW8iOiIxMjQuMDQzNDc2NTc4MDgxMDMiLCJwbGF0Zm9ybSI6Ik1hY0ludGVsIiwid2ViX3RpbWV6b25lIjoiQXNpYS9TaGFuZ2hhaSIsImRldmljZV9uYW1lIjoiQ2hyb21lIFY5Mi4wLjQ1MTUuMTU5IChNYWMgT1MpIiwiZmluZ2VycHJpbnQiOiIxYjJlNDcxMmQ0MTE2MjMyNzRmM2JmY2UyZWYwNDkwNSIsImRldmljZV9pZCI6IiIsInJlbGF0ZWRfZGV2aWNlX2lkcyI6IiJ9",
            "bnc-uuid": "bde6dfb0-cafa-4be3-988d-9cc313cddf26",
            "clienttype": "web",
            "sec-ch-ua": '"Chromium";v="92", " Not A;Brand";v="99", "Google Chrome";v="92"',
            "accept": "*/*",
            "origin": "https://www.binance.com",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "accept-language": "en",
        }
        main_page_response = requests.get(
            "https://www.binance.com/", headers=self.headers
        )
        self.cookies = main_page_response.cookies

    async def get_funding_rate_history(self, symbol: str, rows: int = 100) -> dict:
        # https://www.binance.com/en/futures/funding-history/perpetual/funding-fee-history
        data = {"symbol": symbol, "page": 1, "rows": rows}  # can do 10_000 max
        url = "https://www.binance.com/bapi/futures/v1/public/future/common/get-funding-rate-history"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=self.headers, cookies=self.cookies, data=json.dumps(data)
            ) as response:
                response_data = (
                    await response.json()
                )  # or use response.text() if you expect a non-JSON response
                return response_data

    async def fund_rating(self, symbol: str, rows: int = 100) -> pd.DataFrame:
        response = await self.get_funding_rate_history(symbol, rows)
        df = pd.DataFrame(response["data"])

        if df.empty:
            logger.warn(f"No data found for {symbol}")
            return df

        # Convert timestamp to datetime
        df["calcTime"] = pd.to_datetime(df["calcTime"], unit="ms")

        return df


# Use in loop: funding
async def get_funding_rate() -> tuple[pd.DataFrame, datetime.timedelta]:
    # Get the JSON data from the Binance API
    binance_data = await get_json_data("https://fapi.binance.com/fapi/v1/premiumIndex")

    # If the call did not work
    if not binance_data:
        logger.warn("Could not get funding data...")
        return

    # Cast to dataframe
    try:
        df = pd.DataFrame(binance_data)
    except Exception as e:
        logger.error(f"Could not cast to dataframe, error: {e}")
        return

    # Keep only the USDT pairs
    df = df[df["symbol"].str.contains("USDT")]

    # Remove USDT from the symbol
    df["symbol"] = df["symbol"].str.replace("USDT", "")

    # Set it to numeric
    df["lastFundingRate"] = df["lastFundingRate"].apply(pd.to_numeric)

    # Sort on lastFundingRate, lowest to highest
    sorted = df.sort_values(by="lastFundingRate", ascending=True)

    # Multiply by 100 to get the funding rate in percent
    sorted["lastFundingRate"] = sorted["lastFundingRate"] * 100

    # Round to 4 decimal places
    sorted["lastFundingRate"] = sorted["lastFundingRate"].round(4)

    # Convert them back to string
    sorted = sorted.astype(str)

    # Add percentage to it
    sorted["lastFundingRate"] = sorted["lastFundingRate"] + "%"

    # Post the top 15 lowest
    lowest = sorted.head(15)

    # Get time to next funding, unix is in milliseconds
    nextFundingTime = int(lowest["nextFundingTime"].tolist()[0]) // 1000
    nextFundingTime = datetime.datetime.fromtimestamp(nextFundingTime)

    # Get difference
    timeToNextFunding = nextFundingTime - datetime.datetime.now()

    return lowest, timeToNextFunding


async def get_gainers_losers():
    binance_data = await get_json_data("https://api.binance.com/api/v3/ticker/24hr")

    # If the call did not work
    if not binance_data:
        return

    # Cast to dataframe
    try:
        df = pd.DataFrame(binance_data)
    except Exception as e:
        logger.error(f"Could not cast to dataframe, error: {e}")
        return

    # Keep only the USDT pairs
    df = df[df["symbol"].str.contains("USDT")]

    # Remove USDT from the symbol
    df["symbol"] = df["symbol"].str.replace("USDT", "")

    df[["priceChangePercent", "weightedAvgPrice", "volume"]] = df[
        ["priceChangePercent", "weightedAvgPrice", "volume"]
    ].apply(pd.to_numeric)

    # Sort on priceChangePercent
    sorted = df.sort_values(by="priceChangePercent", ascending=False)

    sorted.rename(
        columns={
            "symbol": "Symbol",
            "priceChangePercent": "% Change",
            "weightedAvgPrice": "Price",
            "volume": "Volume",
        },
        inplace=True,
    )

    # Add website to symbol
    sorted["Symbol"] = (
        "["
        + sorted["Symbol"]
        + "](https://www.binance.com/en/price/"
        + sorted["Symbol"]
        + ")"
    )

    # Post the top 10 highest
    gainers = sorted.head(10)

    # Post the top 10 lowest
    losers = sorted.tail(10)
    losers = losers.iloc[::-1]

    return gainers, losers


# For loop: liquidations


def get_existing_files() -> list[str]:
    # TODO: make this async
    response = requests.get(
        "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/daily/liquidationSnapshot/BTCUSDT/"
    )
    tree = ElementTree.fromstring(response.content)

    files = []
    for content in tree.findall("{http://s3.amazonaws.com/doc/2006-03-01/}Contents"):
        key = content.find("{http://s3.amazonaws.com/doc/2006-03-01/}Key").text
        if key.endswith(".zip"):
            files.append(key)

    return files


def extract_date_from_filename(filename: str) -> str:
    return filename.split("liquidationSnapshot-")[-1].split(".")[0]


def get_local_dates(base_path: str, symbol: str, market: str):
    path_pattern = os.path.join(base_path, symbol, market, "*.csv")
    local_files = glob.glob(path_pattern)
    local_dates = {
        extract_date_from_filename(os.path.basename(file)) for file in local_files
    }
    return local_dates


def download_and_extract_zip(
    symbol: str, date: datetime, market: str = "cm", base_extract_to="./data"
):
    """
    Downloads a ZIP file from the given URL and extracts its contents to a subdirectory named after the symbol.

    Args:
    symbol (str): The symbol to download data for.
    date (datetime): The date for the data.
    market (str): The market type. Defaults to "cm".
    base_extract_to (str): The base directory to extract the contents to. Defaults to "./data".

    Returns:
    None
    """
    # Ensure the base_extract_to directory exists
    os.makedirs(base_extract_to, exist_ok=True)

    # Create a subdirectory for the symbol
    extract_to = os.path.join(base_extract_to, symbol)
    os.makedirs(extract_to, exist_ok=True)

    # Subdirectory for the market
    extract_to = os.path.join(extract_to, market)
    os.makedirs(extract_to, exist_ok=True)

    date_str = date.strftime("%Y-%m-%d")
    url = f"https://data.binance.vision/data/futures/{market}/daily/liquidationSnapshot/{symbol}/{symbol}-liquidationSnapshot-{date_str}.zip"

    try:
        # Step 1: Download the ZIP file
        response = requests.get(url)
        response.raise_for_status()  # Ensure the request was successful

        # Step 2: Extract the contents of the ZIP file
        with zipfile.ZipFile(BytesIO(response.content)) as zip_ref:
            zip_ref.extractall(extract_to)
    except requests.RequestException as e:
        logger.error(f"Failed to download {url}: {e}")
    except zipfile.BadZipFile as e:
        logger.error(f"Failed to extract {url}: {e}")


def get_new_data(
    symbol: str, market: str = "cm", base_extract_to: str = "./data"
) -> set[str]:
    existing_files = get_existing_files()
    existing_dates = {extract_date_from_filename(file) for file in existing_files}

    local_dates = get_local_dates(base_extract_to, symbol, market)
    missing_dates = existing_dates - local_dates

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(
                download_and_extract_zip,
                symbol,
                datetime.strptime(date, "%Y-%m-%d"),
                market,
                base_extract_to,
            )
            for date in missing_dates
        ]
        if futures:
            for future in tqdm(
                as_completed(futures), total=len(futures), desc="Downloading files"
            ):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error occurred: {e}")

    return missing_dates


def convert_timestamp_to_date(timestamp):
    return datetime.datetime.utcfromtimestamp(timestamp / 1000).strftime("%Y-%m-%d")


def summarize_liquidations(coin="BTCUSDT", market="um"):
    file_pattern = f"data/{coin}/{market}/*.csv"
    # Read all CSV files matching the pattern
    all_files = glob.glob(file_pattern)

    df_list = []
    for file in all_files:
        df = pd.read_csv(file)
        df_list.append(df)

    # Concatenate all DataFrames into a single DataFrame
    all_data = pd.concat(df_list, ignore_index=True)

    # Remove duplicate rows
    all_data.drop_duplicates(inplace=True)

    # Convert the 'time' column to date
    all_data["date"] = all_data["time"].apply(convert_timestamp_to_date)

    # Calculate total volume in USD
    all_data["volume"] = all_data["original_quantity"] * all_data["average_price"]

    # Summarize the data
    summary = (
        all_data.groupby(["date", "side"])
        .agg(
            total_volume=("volume", "sum"),
            total_liquidations=("original_quantity", "sum"),  # used for avg price
        )
        .reset_index()
    )

    summary["average_price"] = summary["total_volume"] / summary["total_liquidations"]

    # Pivot the summary to have separate columns for buy and sell sides
    pivot_summary = summary.pivot(
        index="date", columns="side", values=["total_volume", "average_price"]
    ).fillna(0)
    pivot_summary.columns = [
        "_".join(col).strip() for col in pivot_summary.columns.values
    ]
    pivot_summary = pivot_summary.rename(
        columns={
            "total_volume_BUY": "Buy Volume (USD)",
            "total_volume_SELL": "Sell Volume (USD)",
            "average_price_BUY": "Average Buy Price",
            "average_price_SELL": "Average Sell Price",
        }
    )

    # Calculate overall average price
    pivot_summary["Average Price"] = (
        pivot_summary["Average Buy Price"] * pivot_summary["Buy Volume (USD)"]
        + pivot_summary["Average Sell Price"] * pivot_summary["Sell Volume (USD)"]
    ) / (pivot_summary["Buy Volume (USD)"] + pivot_summary["Sell Volume (USD)"])

    # Drop individual average price columns if only overall average price is needed
    pivot_summary.drop(
        columns=["Average Buy Price", "Average Sell Price"], inplace=True
    )

    # Rename columns as required
    pivot_summary.rename(
        columns={
            "Buy Volume (USD)": "Shorts",
            "Sell Volume (USD)": "Longs",
            "Average Price": "price",
        },
        inplace=True,
    )

    # Convert the index to datetime and set it as index
    pivot_summary["date"] = pd.to_datetime(pivot_summary.index)
    pivot_summary = pivot_summary.set_index("date")

    # Save it locally
    os.makedirs("data/summary", exist_ok=True)
    os.makedirs(f"data/summary/{coin}", exist_ok=True)
    os.makedirs(f"data/summary/{coin}/{market}", exist_ok=True)
    pivot_summary.to_csv(f"data/summary/{coin}/{market}/liquidation_summary.csv")
