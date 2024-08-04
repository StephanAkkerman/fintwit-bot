import numpy as np
import pandas as pd

from util.formatting import format_change
from util.vars import get_json_data, logger


async def top_cmc():
    data = await get_json_data(
        "https://api.coinmarketcap.com/nft/v3/nft/collectionsv2?start=0&limit=100&category=&collection=&blockchain=&sort=volume&desc=true&period=1"
    )

    # Convert to dataframe
    if "data" not in data:
        logger.error("No data found in CoinMarketCap response")
        return pd.DataFrame()
    if "collections" not in data["data"]:
        logger.error("No collections found in CoinMarketCap response")
        return pd.DataFrame()

    df = pd.DataFrame(data["data"]["collections"])

    df = df.head(10)

    # Unpack all oneDay data
    df = pd.concat([df.drop(["oneDay"], axis=1), df["oneDay"].apply(pd.Series)], axis=1)

    # name, url, price, volume, volume change
    # Conditionally concatenate "name" and "website" only when "website" is not NaN
    df["symbol"] = np.where(
        df["website"].notna() & (df["website"] != ""),
        "[" + df["name"] + "]" + "(" + df["website"] + ")",
        df["name"],
    )
    df["price"] = df["floorPriceUsd"].apply(lambda x: f"${x:,.2f}")
    df["change"] = df["averagePriceChangePercentage"].apply(lambda x: format_change(x))
    df["price"] = df["price"] + " (" + df["change"] + ")"
    df["volume"] = df["volume"].apply(lambda x: f"{x:,.0f} ETH")
    df["volume_change"] = df["volumeChangePercentage"].apply(lambda x: format_change(x))
    df["volume"] = df["volume"] + " (" + df["volume_change"] + ")"

    return df


async def upcoming_cmc():
    # Could remove category and expire from URL
    data = await get_json_data(
        "https://api.coinmarketcap.com/nft/v3/nft/upcoming-drops?start=0&limit=20&category=Popular&expire=30"
    )

    # Convert the data to a pandas DataFrame
    df = pd.DataFrame(data["data"]["data"])

    df = df.head(10)

    # name, websiteUrl, price, dropDate
    # Filter out the columns that actually exist in the DataFrame
    existing_columns = [
        col for col in ["name", "websiteUrl", "price", "dropType"] if col in df.columns
    ]

    # Use only the existing columns to filter the DataFrame
    df = df[existing_columns]

    # Use same method as #events channel time
    # Rename to start_time
    # df["start_time"] = df["dropDate"].apply(
    #    lambda x: f"<t:{int(x/1000)}:d>" if pd.notnull(x) else ""
    # )

    # Conditionally concatenate "name" and "website" only when "website" is not NaN
    df["symbol"] = np.where(
        df["websiteUrl"].notna() & (df["websiteUrl"] != ""),
        "[" + df["name"] + "]" + "(" + df["websiteUrl"] + ")",
        df["name"],
    )

    return df


async def trending():
    cmc_data = await get_json_data(
        "https://api.coinmarketcap.com/data-api/v3/topsearch/rank"
    )

    # Convert to dataframe
    cmc_df = pd.DataFrame(cmc_data["data"]["cryptoTopSearchRanks"])

    # Only save [[symbol, price + pricechange, volume]]
    cmc_df = cmc_df[["symbol", "slug", "priceChange"]]

    # Rename symbol
    cmc_df.rename(columns={"symbol": "Symbol"}, inplace=True)

    # Add website to symbol
    cmc_df["Website"] = "https://coinmarketcap.com/currencies/" + cmc_df["slug"]
    # Format the symbol
    cmc_df["Symbol"] = "[" + cmc_df["Symbol"] + "](" + cmc_df["Website"] + ")"

    # Get important information from priceChange dictionary
    cmc_df["Price"] = cmc_df["priceChange"].apply(lambda x: x["price"])
    cmc_df["% Change"] = cmc_df["priceChange"].apply(lambda x: x["priceChange24h"])
    cmc_df["Volume"] = cmc_df["priceChange"].apply(lambda x: x["volume24h"])

    return cmc_df
