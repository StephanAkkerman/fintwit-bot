import csv
from io import StringIO

from util.vars import get_json_data

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36 Edg/110.0.1587.57"
}


async def ohlcv(ticker: str) -> dict:
    csv_text = await get_json_data(
        f"https://query1.finance.yahoo.com/v7/finance/download/{ticker}",
        headers=headers,
        text=True,
    )
    # Use StringIO to treat the CSV text as a file-like object
    csv_file = StringIO(csv_text)

    # Use csv.DictReader to parse the CSV text
    reader = csv.DictReader(csv_file)

    # Convert the parsed CSV data to a list of dictionaries
    data = [row for row in reader]

    # If there's only one row, return just that row as a dictionary
    if len(data) == 1:
        return data[0]

    # Return the list of dictionaries if there are multiple rows
    return data


async def all_info(ticker: str) -> dict:
    """
    _summary_

    Parameters
    ----------
    ticker : str
        _description_

    Returns
    -------
    dict
        _description_
    """
    data = await get_json_data(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
        headers=headers,
    )
    return data
