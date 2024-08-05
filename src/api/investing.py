import datetime

import pandas as pd
import pytz
from lxml.html import fromstring

from api.http_client import post_json_data


# For loop: events
async def get_events() -> pd.DataFrame:
    """
    Gets the economic calendar from Investing.com for the next week.
    The data contains the most important information for the USA and EU.

    Forked from: https://github.com/alvarobartt/investpy/blob/master/investpy/news.py
    """

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }

    data = {
        "country[]": [72, 5],  # USA and EU
        "importance[]": 3,  # Highest importance, 3 stars
        "timeZone": 8,
        "timeFilter": "timeRemain",
        "currentTab": "nextWeek",
        "submitFilters": 1,
        "limit_from": 0,
    }

    url = "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData"

    req = await post_json_data(url, headers=headers, data=data)
    root = fromstring(req["data"])
    table = root.xpath(".//tr")

    results = []

    for reversed_row in table[::-1]:
        id_ = reversed_row.get("id")
        if id_ is not None:
            id_ = id_.replace("eventRowId_", "")

    for row in table:
        id_ = row.get("id")
        if id_ is None:
            curr_timescope = int(row.xpath("td")[0].get("id").replace("theDay", ""))
            curr_date = datetime.datetime.fromtimestamp(
                curr_timescope, tz=pytz.timezone("GMT")
            ).strftime("%d/%m/%Y")
        else:
            id_ = id_.replace("eventRowId_", "")

            time = zone = currency = event = actual = forecast = previous = None

            if row.get("id").__contains__("eventRowId_"):
                for value in row.xpath("td"):
                    if value.get("class").__contains__("first left"):
                        time = value.text_content()
                    elif value.get("class").__contains__("flagCur"):
                        zone = value.xpath("span")[0].get("title").lower()
                        currency = value.text_content().strip()
                    elif value.get("class") == "left event":
                        event = value.text_content().strip()
                    elif value.get("id") == "eventActual_" + id_:
                        actual = value.text_content().strip()
                    elif value.get("id") == "eventForecast_" + id_:
                        forecast = value.text_content().strip()
                    elif value.get("id") == "eventPrevious_" + id_:
                        previous = value.text_content().strip()

            results.append(
                {
                    "id": id_,
                    "date": curr_date,
                    "time": time,
                    "zone": zone,
                    "currency": None if currency == "" else currency,
                    "event": event,
                    "actual": None if actual == "" else actual,
                    "forecast": None if forecast == "" else forecast,
                    "previous": None if previous == "" else previous,
                }
            )

    return pd.DataFrame(results)
