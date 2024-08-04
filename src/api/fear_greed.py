from util.vars import get_json_data


async def get_feargread() -> tuple[int, str] | None:
    """
    Gets the last 2 Fear and Greed indices from the API.

    Returns
    -------
    int
        Today's Fear and Greed index.
    str
        The percentual change compared to yesterday's Fear and Greed index.
    """

    response = await get_json_data("https://api.alternative.me/fng/?limit=2")

    if "data" in response.keys():
        today = int(response["data"][0]["value"])
        yesterday = int(response["data"][1]["value"])

        change = round((today - yesterday) / yesterday * 100, 2)
        change = f"+{change}% 📈" if change > 0 else f"{change}% 📉"

        return today, change
