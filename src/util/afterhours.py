# Standard libraries
import datetime

# 3rd party libraries
from pandas.tseries.holiday import USFederalHolidayCalendar

# Get the public holidays
cal = USFederalHolidayCalendar()
us_holidays = cal.holidays(
    start=datetime.date(datetime.date.today().year, 1, 1).strftime("%Y-%m-%d"),
    end=datetime.date(datetime.date.today().year, 12, 31).strftime("%Y-%m-%d"),
).to_pydatetime()


def afterHours():
    """
    Simple code to check if the current time is after hours in the US.
    return: True if after hours, False otherwise

    source: https://www.reddit.com/r/algotrading/comments/9x9xho/python_code_to_check_if_market_is_open_in_your/
    """

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-6), "EST"))
    openTime = datetime.time(hour=9, minute=30, second=0)
    closeTime = datetime.time(hour=16, minute=0, second=0)

    # If a holiday
    if now.strftime("%Y-%m-%d") in us_holidays:
        return True

    # If before 0930 or after 1600
    if (now.time() < openTime) or (now.time() > closeTime):
        return True

    # If it's a weekend
    if now.date().weekday() > 4:
        return True

    # Otherwise the market is open
    return False
