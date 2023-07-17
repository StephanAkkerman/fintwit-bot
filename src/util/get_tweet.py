import json

from util.vars import config, get_json_data

# Maybe improve this using params with variables and features
# see https://github.com/HitomaruKonpaku/twspace-crawler/blob/7c98653f4915a8690491052e2a1415cc7beb74ab/src/api/api/twitter-graphql.api.ts#L213
url = "https://twitter.com/i/api/graphql/g9l6dvixcXvObSkIE8Pajg/HomeLatestTimeline?variables=%7B%22count%22%3A40%2C%22cursor%22%3A%22DAABCgABF0rqRkTAJxEKAAIXSuo3TZYAAQgAAwAAAAEAAA%22%2C%22includePromotedContent%22%3Atrue%2C%22latestControlAvailable%22%3Atrue%2C%22requestContext%22%3A%22ptr%22%7D&features=%7B%22rweb_lists_timeline_redesign_enabled%22%3Atrue%2C%22responsive_web_graphql_exclude_directive_enabled%22%3Atrue%2C%22verified_phone_label_enabled%22%3Afalse%2C%22creator_subscriptions_tweet_preview_api_enabled%22%3Atrue%2C%22responsive_web_graphql_timeline_navigation_enabled%22%3Atrue%2C%22responsive_web_graphql_skip_user_profile_image_extensions_enabled%22%3Afalse%2C%22tweetypie_unmention_optimization_enabled%22%3Atrue%2C%22responsive_web_edit_tweet_api_enabled%22%3Atrue%2C%22graphql_is_translatable_rweb_tweet_is_translatable_enabled%22%3Atrue%2C%22view_counts_everywhere_api_enabled%22%3Atrue%2C%22longform_notetweets_consumption_enabled%22%3Atrue%2C%22responsive_web_twitter_article_tweet_consumption_enabled%22%3Afalse%2C%22tweet_awards_web_tipping_enabled%22%3Afalse%2C%22freedom_of_speech_not_reach_fetch_enabled%22%3Atrue%2C%22standardized_nudges_misinfo%22%3Atrue%2C%22tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled%22%3Atrue%2C%22longform_notetweets_rich_text_read_enabled%22%3Atrue%2C%22longform_notetweets_inline_media_enabled%22%3Atrue%2C%22responsive_web_media_download_video_enabled%22%3Afalse%2C%22responsive_web_enhance_cards_enabled%22%3Afalse%7D&fieldToggles=%7B%22withArticleRichContentState%22%3Afalse%7D"

headers = {
    "Origin": "https://twitter.com",
    "Referer": "https://twitter.com/",
    "Sec-Ch-Ua": '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "Authorization": f"Bearer {config['TWITTER']['HEADERS']['BEARER']}",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "X-Client-Uuid": config["TWITTER"]["HEADERS"]["X-CLIENT-UUID"],
    "X-Csrf-Token": config["TWITTER"]["HEADERS"]["X-CRSF-TOKEN"],
    "X-Twitter-Active-User": "yes",
    "X-Twitter-Auth-Type": "OAuth2Session",
    "X-Twitter-Client-Language": "en",
    "X-Twitter-Polling": "true",
}

cookies = {
    "_ga": config["TWITTER"]["COOKIES"]["_GA"],
    "g_state": '{"i_l":0}',
    "lang": "en",
    "guest_id": config["TWITTER"]["COOKIES"]["GUEST_ID"],
    "kdt": config["TWITTER"]["COOKIES"]["KDT"],
    "auth_token": config["TWITTER"]["COOKIES"]["AUTH_TOKEN"],
    "ct0": config["TWITTER"]["HEADERS"]["X-CRSF-TOKEN"],
    "twid": config["TWITTER"]["COOKIES"]["TWID"],
    "guest_id_marketing": config["TWITTER"]["COOKIES"]["GUEST_ID"],
    "guest_id_ads": config["TWITTER"]["COOKIES"]["GUEST_ID"],
    "personalization_id": f'"{config["TWITTER"]["COOKIES"]["PERSONALIZATION_ID"]}"',
}


async def get_tweet():
    result = await get_json_data(
        url,
        headers=headers,
        cookies=cookies,
        text=False,
    )

    if "data" in result:
        if "home" in result["data"]:
            if "home_timeline_urt" in result["data"]["home"]:
                if "instructions" in result["data"]["home"]["home_timeline_urt"]:
                    if (
                        "entries"
                        in ["data"]["home"]["home_timeline_urt"]["instructions"][0]
                    ):
                        return result["data"]["home"]["home_timeline_urt"][
                            "instructions"
                        ][0]["entries"]

    try:
        result["data"]["home"]["home_timeline_urt"]["instructions"][0]["entries"]
    except KeyError as e:
        print("Error: wrong json format\n", e)
        with open("no_entries.json", "w") as f:
            json.dump(result, f, indent=4)

        return []
