"""Optional Adanos stock sentiment for the Discord research command."""

import re
from datetime import date

import aiohttp

BASE_URL = "https://api.adanos.org"
SOURCE_PATHS = {
    "reddit": "/reddit/stocks/v1/stock",
    "x": "/x/stocks/v1/stock",
    "news": "/news/stocks/v1/stock",
    "polymarket": "/polymarket/stocks/v1/stock",
}


async def get_stock_sentiment(
    ticker: str, source: str, start: date, end: date, api_key: str
) -> dict:
    """Fetch one dated US-stock detail response without hiding API errors."""
    ticker = ticker.upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9.]{0,9}", ticker):
        raise ValueError("Use a US stock ticker such as AAPL")
    if source not in SOURCE_PATHS:
        raise ValueError("Unsupported sentiment source")
    if start > end:
        raise ValueError("Start date must be on or before end date")

    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session, session.get(
        f"{BASE_URL}{SOURCE_PATHS[source]}/{ticker}",
        params={"from": start.isoformat(), "to": end.isoformat()},
        headers={"X-API-Key": api_key},
    ) as response:
        response.raise_for_status()
        data = await response.json()
    if not isinstance(data, dict) or not isinstance(data.get("found"), bool):
        raise TypeError("Unexpected Adanos response")
    return data


def format_stock_sentiment(
    data: dict, ticker: str, source: str, start: date, end: date
) -> str:
    """Summarize source-specific metrics without inventing missing values."""
    label = {
        "x": "X / FinTwit",
        "reddit": "Reddit",
        "news": "News",
        "polymarket": "Polymarket",
    }[source]
    heading = f"{ticker.upper()} {label} sentiment ({start} to {end} UTC)"
    if not data["found"]:
        return f"{heading}\nNo Adanos data for this ticker and window."

    lines = [heading]
    for key, name in (
        ("buzz_score", "Buzz score"),
        ("sentiment_score", "Sentiment score"),
        (
            "trade_count" if source == "polymarket" else "mentions",
            "Trades" if source == "polymarket" else "Mentions",
        ),
        ("bullish_pct", "Bullish %"),
        ("bearish_pct", "Bearish %"),
    ):
        value = data.get(key)
        if value is not None:
            lines.append(f"{name}: {value}")
    lines.append("Source: Adanos | Context only, not a trading signal")
    return "\n".join(lines)
