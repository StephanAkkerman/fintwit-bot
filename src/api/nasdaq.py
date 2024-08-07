import datetime
import ftplib
import io
from io import StringIO

import pandas as pd
from dateutil import tz

from api.http_client import get_json_data, post_json_data


def tickers_nasdaq(include_company_data=False):
    """Downloads list of tickers currently listed in the NASDAQ
    source: https://github.com/atreadw1492/yahoo_fin/blob/master/yahoo_fin/stock_info.py#L151
    """

    ftp = ftplib.FTP("ftp.nasdaqtrader.com")
    ftp.login()
    ftp.cwd("SymbolDirectory")

    r = io.BytesIO()
    ftp.retrbinary("RETR nasdaqlisted.txt", r.write)

    if include_company_data:
        r.seek(0)
        data = pd.read_csv(r, sep="|")
        return data

    info = r.getvalue().decode()
    splits = info.split("|")

    tickers = [x for x in splits if "\r\n" in x]
    tickers = [x.split("\r\n")[1] for x in tickers if "NASDAQ" not in x != "\r\n"]
    tickers = [ticker for ticker in tickers if "File" not in ticker]

    ftp.close()

    return tickers


async def get_earnings_for_date(date: datetime.datetime) -> pd.DataFrame:
    # Convert datetime to string YYYY-MM-DD
    date = date.strftime("%Y-%m-%d")
    url = f"https://api.nasdaq.com/api/calendar/earnings?date={date}"
    # Add headers to avoid 403 error
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en,nl-NL;q=0.9,nl;q=0.8,en-CA;q=0.7,ja;q=0.6",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    }
    json = await get_json_data(url, headers=headers)
    # Automatically ordered from highest to lowest market cap
    if "data" not in json:
        return pd.DataFrame()
    df = pd.DataFrame(json["data"]["rows"])
    if df.empty:
        return df
    # Replace time with emojis
    emoji_dict = {
        "time-after-hours": "🌙",
        "time-pre-market": "🌞",
        "time-not-supplied": "❓",
    }
    df["time"] = df["time"].replace(emoji_dict)
    return df


def get_halt_data():
    html = fetch_halt_data
    if html == {}:
        return pd.DataFrame()

    df = pd.read_html(StringIO(html["result"]))[0]

    # Drop NaN columns
    df = df.dropna(axis=1, how="all")

    # Drop columns where halt date is not today
    df = df[df["Halt Date"] == pd.Timestamp.today().strftime("%m/%d/%Y")]

    # Combine columns into one singular datetime column
    df["Time"] = df["Halt Date"] + " " + df["Halt Time"]
    df["Time"] = pd.to_datetime(df["Time"], format="%m/%d/%Y %H:%M:%S")

    # Do for resumption as well if the column is not NaN
    if "Resumption Date" in df.columns and "Resumption Trade Time" in df.columns:
        # Combine columns into one singular datetime column
        df["Resumption Time"] = (
            df["Resumption Date"] + " " + df["Resumption Trade Time"]
        )
        df["Resumption Time"] = pd.to_datetime(
            df["Resumption Time"], format="%m/%d/%Y %H:%M:%S"
        )

        df["Resumption Time"] = (
            df["Resumption Time"]
            .dt.tz_localize("US/Eastern")
            .dt.tz_convert(tz.tzlocal())
        )

        df["Resumption Time"] = df["Resumption Time"].dt.strftime("%H:%M:%S")

    # Convert to my own timezone
    df["Time"] = df["Time"].dt.tz_localize("US/Eastern").dt.tz_convert(tz.tzlocal())

    # Convert times to string
    df["Time"] = df["Time"].dt.strftime("%H:%M:%S")

    # Replace NaN with ?
    df = df.fillna("?")

    # Keep the necessary columns
    if "Resumption Time" in df.columns:
        df = df[["Time", "Issue Symbol", "Resumption Time"]]
    else:
        df = df[["Time", "Issue Symbol"]]

    return df


async def fetch_halt_data() -> dict:
    # Based on https://github.com/reorx/nasdaqtrader-rss/blob/e675af99ace7d384950d6c75144e9efb1d80b5a7/rss/index.py#L18
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://www.nasdaqtrader.com",
        "Referer": "https://www.nasdaqtrader.com/trader.aspx?id=tradehalts",
        "Sec-Ch-Ua": '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    }
    req_data = {
        "id": 3,
        "method": "BL_TradeHalt.GetTradeHalts",
        "params": "[]",
        "version": "1.1",
    }

    html = await post_json_data(
        "https://www.nasdaqtrader.com/RPCHandler.axd",
        headers=headers,
        json=req_data,
    )

    # Convert to DataFrame
    return html
