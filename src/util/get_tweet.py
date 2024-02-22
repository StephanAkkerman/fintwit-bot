import json
import uncurl

from util.vars import get_json_data

# Read curl.txt
with open("curl.txt", "r", encoding="utf-8") as file:
    cURL = uncurl.parse_context("".join([line.strip() for line in file]))


async def get_tweet():
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
        print("Error in get_tweet():", e)
        with open("logs/get_tweet_error.json", "w") as f:
            json.dump(result, f, indent=4)

    return []
