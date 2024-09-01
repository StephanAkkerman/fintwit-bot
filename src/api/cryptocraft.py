import datetime
import re
from io import StringIO

import pandas as pd
from bs4 import BeautifulSoup

from api.http_client import get_json_data
from constants.logger import logger


async def get_crypto_calendar() -> pd.DataFrame:
    """
    Gets the economic calendar from CryptoCraft.com for the next week.

    Returns
    -------
    pd.DataFrame
        The formatted DataFrame containing the economic calendar.
    """
    html = await get_json_data(
        url="https://www.cryptocraft.com/calendar",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4240.193 Safari/537.36"
        },
        text=True,
    )

    soup = BeautifulSoup(html, "html.parser")

    # Get the first table
    table = soup.find("table")

    impact_emoji = {
        "yel": "🟨",
        "ora": "🟧",
        "red": "🟥",
        "gra": "⬜",
    }

    if table is None:
        logger.error("No table found in the CryptoCraft calendar.")
        return pd.DataFrame()

    impacts = []
    for row in table.find_all("tr")[2:]:  # Skip the header row
        # Get the impact value from the span class including "impact"
        impact = row.find("span", class_=lambda s: s and "impact" in s)
        if impact:
            impact = impact.get("class", [])[-1][-3:]
            impacts.append(impact_emoji[impact])

    # Convert the table to a string and read it into a DataFrame
    df = pd.read_html(StringIO(str(table)))[0]

    # Drop the first row
    df = df.iloc[1:]

    # Drop rows where the first and second column values are the same
    df = df[df.iloc[:, 0] != df.iloc[:, 1]]

    # Convert MultiIndex columns to regular columns
    df.columns = ["_".join(col).strip() for col in df.columns.values]

    # Rename second column to time and fifth column to event
    df.rename(
        columns={
            df.columns[0]: "date",
            df.columns[1]: "time",
            df.columns[4]: "event",
            df.columns[6]: "actual",
            df.columns[7]: "forecast",
            df.columns[8]: "previous",
        },
        inplace=True,
    )

    # Drop third and fourth column
    df.drop(df.columns[[2, 3, 5, 9]], axis=1, inplace=True)

    # Remove rows where event is NaN
    df = df[df["event"].notna()]

    # Reset index
    df.reset_index(drop=True, inplace=True)

    # Add impact column
    df["impact"] = impacts

    # Use ffill() for forward fill
    df["time"] = df["time"].ffill()

    # Mask for entries where 'time' does not match common time patterns (only checks for absence of typical hour-minute time format)
    mask_no_time_pattern = df["time"].str.contains(
        r"^\D*$|day", flags=re.IGNORECASE, na=False
    )
    # Mask for entries with specific time (i.e., typical time patterns are present)
    mask_time_specific = ~mask_no_time_pattern

    # Convert 'All Day' entries by appending the current year and no specific time
    df.loc[mask_no_time_pattern, "datetime"] = pd.to_datetime(
        df.loc[mask_no_time_pattern, "date"] + " " + str(datetime.datetime.now().year),
        format="%a %b %d %Y",
        errors="coerce",
    )

    # Convert specific time entries by appending the current year and the specific time
    df.loc[mask_time_specific, "datetime"] = pd.to_datetime(
        df.loc[mask_time_specific, "date"]
        + " "
        + str(datetime.datetime.now().year)
        + " "
        + df.loc[mask_time_specific, "time"],
        format="%a %b %d %Y %I:%M%p",
        errors="coerce",
    )

    return df
