import re

import pandas as pd

from util.formatting import format_change
from util.vars import get_json_data


async def get_opensea(url=""):
    """
    _summary_

    Parameters
    ----------
    url : str, optional
        Can be either "trending" or empty, by default ""

    Returns
    -------
    _type_
        _description_
    """

    html_doc = await get_json_data(
        f"https://opensea.io/rankings/{url}",
        headers={"User-Agent": "Mozilla/5.0"},
        text=True,
    )

    html_doc = html_doc[html_doc.find(':pageInfo"}},') + len(':pageInfo"}},') :]
    html_doc = html_doc[: html_doc.find(":edges:10")]

    rows = html_doc.split('"node":{')

    opensea_nfts = []

    for row in rows[1:]:
        nft_dict = {}

        name = re.search(r"\"name\":\"(.*?)\"", row).group(1)
        slug = re.search(r"\"slug\":\"(.*?)\"", row)

        if slug:
            slug = slug.group(1)
        else:
            slug = ""

        price_data = re.findall(r"\"unit\":\"(.*?)\"", row)
        change = re.search(r"\"volumeChange\":(.*?),", row)
        symbol = re.search(r"\"symbol\":\"(.*?)\"", row).group(1)

        if len(price_data) == 2:
            floor_price = f"{round(float(price_data[0]),3)} {symbol}"
            volume = price_data[1]
        else:
            floor_price = "?"
            volume = price_data[0]

        volume = f"{int(float(volume))} {symbol}"
        change = float(change.group(1)) * 100

        if change != 0:
            if change > 1:
                change = int(change)
            else:
                change = round(change, 2)
            volume = f"{volume} ({format_change(change)})"

        nft_dict["symbol"] = f"[{name}](https://opensea.io/collection/{slug})"
        nft_dict["price"] = floor_price
        nft_dict["volume"] = volume

        opensea_nfts.append(nft_dict)

    return pd.DataFrame(opensea_nfts)
