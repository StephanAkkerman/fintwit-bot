from io import StringIO

import pandas as pd

from api.http_client import get_json_data
from constants.logger import logger


async def get_etf_inflow(coin: str = "btc") -> float:
    data = await get_json_data(f"https://farside.co.uk/{coin}/", text=True)
    try:
        df = pd.read_html(StringIO(data))[1]
    except ValueError:
        logger.error(f"Failed to parse ETF inflow data for {coin}")
        return 0.0

    # Use only top row for columns
    df.columns = [col[0] for col in df.columns]

    # Drop last 4 rows
    df = df[:-4]

    # Replace parentheses with a negative sign and remove commas
    df.replace(to_replace={r"\((.*?)\)": r"-\1", ",": ""}, regex=True, inplace=True)

    # Convert the 'Total' column to numeric values, treating "-" as 0.0
    df["Total"] = df["Total"].replace("-", "0.0").astype(float)

    # Filter out rows where 'Total' is not 0.0
    df_filtered = df[df["Total"] != 0.0]

    # Get the last row from the filtered DataFrame
    last_valid_row = df_filtered.iloc[-1] if not df_filtered.empty else None

    # Get total value from the last row
    return last_valid_row["Total"] if last_valid_row is not None else 0.0
