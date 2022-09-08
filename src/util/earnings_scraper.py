## > Imports
# Standard imports
import json
import requests
import time


class YahooEarningsCalendar:
    """
    This is the class for fetching earnings data from Yahoo! Finance, built by https://github.com/wenboyu2.
    """

    def _get_data_dict(self, url: str) -> dict:

        # Sleep 60*60 / 2000 = 1.8 seconds to prevent rate limit
        time.sleep(1.8)
        page = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36"
            },
        )
        page_content = page.content.decode(encoding="utf-8", errors="strict")
        page_data_string = [
            row
            for row in page_content.split("\n")
            if row.startswith("root.App.main = ")
        ][0][:-1]
        page_data_string = page_data_string.split("root.App.main = ", 1)[1]

        return json.loads(page_data_string)

    def get_next_earnings_date(self, symbol: str):
        """Gets the next earnings date of symbol
        Args:
            symbol: A ticker symbol
        Returns:
            Unix timestamp of the next earnings date
        Raises:
            Exception: When symbol is invalid or earnings date is not available
        """
        url = f"https://finance.yahoo.com/quote/{symbol}"

        try:
            page_data_dict = self._get_data_dict(url)
            return page_data_dict["context"]["dispatcher"]["stores"][
                "QuoteSummaryStore"
            ]["calendarEvents"]["earnings"]["earningsDate"][0]["raw"]
        except:
            raise Exception("Invalid Symbol or Unavailable Earnings Date")

    def get_earnings_of(self, symbol: str) -> list:
        """Returns all the earnings dates of a symbol
        Args:
            symbol: A ticker symbol
        Returns:
            Array of all earnings dates with supplemental information
        Raises:
            Exception: When symbol is invalid or earnings date is not available
        """
        url = f"https://finance.yahoo.com/calendar/earnings?symbol={symbol}"

        try:
            page_data_dict = self._get_data_dict(url)
            return page_data_dict["context"]["dispatcher"]["stores"][
                "ScreenerResultsStore"
            ]["results"]["rows"]
        except:
            raise Exception("Invalid Symbol or Unavailable Earnings Date")
