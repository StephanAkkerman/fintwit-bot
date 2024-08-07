from __future__ import annotations

import json

import uncurl

from api.http_client import get_json_data
from constants.logger import logger

# Read curl.txt
try:
    with open("curl.txt", "r", encoding="utf-8") as file:
        cURL = uncurl.parse_context("".join([line.strip() for line in file]))
except Exception as e:
    cURL = None
    logger.critical(f"Error: Could not read curl.txt: {e}")


async def get_tweet():
    if cURL is None:
        logger.critical("Error: no curl.txt file found. Timelines will not be updated.")
        return []

    result = await get_json_data(
        cURL.url,
        headers=dict(cURL.headers),
        cookies=dict(cURL.cookies),
        json_data=json.loads(cURL.data),
        text=False,
    )

    if result == {}:
        return []

    # TODO: Ignore x-premium alerts
    if "data" in result:
        if "home" in result["data"]:
            if "home_timeline_urt" in result["data"]["home"]:
                if "instructions" in result["data"]["home"]["home_timeline_urt"]:
                    if (
                        "entries"
                        in result["data"]["home"]["home_timeline_urt"]["instructions"][
                            0
                        ]
                    ):
                        return result["data"]["home"]["home_timeline_urt"][
                            "instructions"
                        ][0]["entries"]

    try:
        result["data"]["home"]["home_timeline_urt"]["instructions"][0]["entries"]
    except Exception as e:
        logger.error(f"Error in get_tweet(): {e}")
        with open("logs/get_tweet_error.json", "w") as f:
            json.dump(result, f, indent=4)

    return []
