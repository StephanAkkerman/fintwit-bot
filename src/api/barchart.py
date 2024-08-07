from __future__ import annotations

from io import StringIO

import pandas as pd

from api.http_client import get_json_data


async def get_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    r = await get_json_data(
        url="https://www.barchart.com/stocks/market-performance",
        headers=headers,
        text=True,
    )
    df = pd.read_html(StringIO(r))[0]

    # Remove % from all rows
    df = df.replace("%", "", regex=True)

    # convert columns to numeric
    num_cols = [
        "5 Day Mov Avg",
        "20 Day Mov Avg",
        "50 Day Mov Avg",
        "100 Day Mov Avg",
        "150 Day Mov Avg",
        "200 Day Mov Avg",
    ]
    df[num_cols] = df[num_cols].apply(pd.to_numeric, errors="coerce")

    return df
