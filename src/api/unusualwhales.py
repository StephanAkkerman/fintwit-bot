import pandas as pd

from api.http_client import get_json_data


async def get_spy_heatmap(date: str = "one_day") -> pd.DataFrame:
    """
    Fetches the S&P 500 heatmap data from Unusual Whales API.

    Parameters
    ----------
    date : str, optional
        Options are: one_day, after_hours, yesterday, one_week, one_month, ytd, one_year, by default "one_day"

    Returns
    -------
    pd.DataFrame
        The S&P 500 heatmap data as a DataFrame.
    """
    data = await get_json_data(
        f"https://phx.unusualwhales.com/api/etf/SPY/heatmap?date_range={date}",
        headers={
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36"
        },
    )

    # Create DataFrame
    df = pd.DataFrame(data["data"])

    # Convert relevant columns to numeric types
    df["call_premium"] = pd.to_numeric(df["call_premium"])
    df["close"] = pd.to_numeric(df["close"])
    df["high"] = pd.to_numeric(df["high"])
    df["low"] = pd.to_numeric(df["low"])
    df["marketcap"] = pd.to_numeric(df["marketcap"])
    df["open"] = pd.to_numeric(df["open"])
    df["prev_close"] = pd.to_numeric(df["prev_close"])
    df["put_premium"] = pd.to_numeric(df["put_premium"])

    # Add change column
    df["percentage_change"] = (df["close"] - df["prev_close"]) / df["prev_close"] * 100

    # Drop rows where the marketcap == 0
    df = df[df["marketcap"] > 0]

    return df
