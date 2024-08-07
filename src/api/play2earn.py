from __future__ import annotations

import pandas as pd
from bs4 import BeautifulSoup

from api.http_client import get_json_data
from util.formatting import format_change


async def p2e_games():
    URL = "https://playtoearn.net/blockchaingames/All-Blockchain/All-Genre/All-Status/All-Device/NFT/nft-crypto-PlayToEarn/nft-required-FreeToPlay"

    html = await get_json_data(URL, text=True)
    soup = BeautifulSoup(html, "html.parser")
    items = soup.find("table", class_="table table-bordered mainlist")

    if items is None:
        return pd.DataFrame()

    allItems = items.find_all("tr")

    p2e_games = []

    # Skip header + ad
    iterator = 2
    for iterator in range(2, 12):
        data = {}

        allItems_td = allItems[iterator].find_all("td")
        if len(allItems_td) < 11:
            continue

        name = allItems_td[2].find("div", class_="dapp_name").find_next("span").text
        url = allItems_td[2].find_next("a")["href"]
        status = allItems_td[6].get_text("title")
        social_24h_change = allItems_td[10].find_all("span")
        social_24h = social_24h_change[0].text
        if len(social_24h_change) > 1:
            social_change = social_24h_change[1].text.replace("%", "").replace(",", "")
        else:
            social_change = 0

        data["name"] = f"[{name}]({url})"
        data["status"] = status
        data["social"] = f"{social_24h} ({format_change(float(social_change))})"

        p2e_games.append(data)

    return pd.DataFrame(p2e_games)
