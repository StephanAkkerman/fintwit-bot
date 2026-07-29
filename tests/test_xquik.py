import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

logger_module = types.ModuleType("constants.logger")
logger_module.logger = Mock()
sys.modules["constants.logger"] = logger_module
xquik = importlib.import_module("api.xquik")


def tweet(tweet_id: str) -> xquik.XquikTweet:
    return xquik.XquikTweet(
        id=tweet_id,
        text="Market update",
        user_name="Example",
        user_screen_name="example",
        user_img="",
        url=f"https://x.com/example/status/{tweet_id}",
        media=[],
        tickers=[],
        hashtags=[],
        title="Example tweeted",
        media_types=[],
    )


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None

    async def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = payloads
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def get(self, url: str, headers: dict, params: dict) -> FakeResponse:
        self.requests.append((url, headers, params))
        return FakeResponse(self.payloads.pop(0))


class XquikStateTests(unittest.TestCase):
    def test_record_parser_normalizes_ids_media_and_symbols(self) -> None:
        parsed = xquik._tweet_from_record(
            {
                "id": 123,
                "text": "$btc update #markets",
                "author": {
                    "name": "Example",
                    "username": "example",
                    "profilePicture": "https://example.com/avatar.png",
                },
                "media": [
                    {
                        "mediaUrl": "https://example.com/chart.png",
                        "type": "photo",
                    }
                ],
            }
        )

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.id, "123")
        self.assertEqual(parsed.user_screen_name, "example")
        self.assertEqual(
            parsed.media, [xquik.XquikMedia("https://example.com/chart.png")]
        )
        self.assertEqual(parsed.media_types, ["photo"])
        self.assertEqual(parsed.tickers, ["BTC"])
        self.assertEqual(parsed.hashtags, ["MARKETS"])

    def test_search_configuration_is_bounded(self) -> None:
        with patch.dict(
            os.environ,
            {
                xquik.XQUIK_SEARCH_LIMIT_ENV: "999",
                xquik.XQUIK_SEARCH_MAX_PAGES_ENV: "999",
            },
            clear=False,
        ):
            self.assertEqual(xquik._xquik_search_limit(), 200)
            self.assertEqual(xquik._xquik_search_max_pages(), 100)

    def test_first_poll_seeds_state_then_returns_only_unseen_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = os.path.join(directory, "seen.json")
            with patch.object(xquik, "SEEN_IDS_PATH", state_path):
                self.assertEqual(
                    xquik._filter_new_tweets(
                        [tweet("opaque-new"), tweet("opaque-old")]
                    ),
                    [],
                )
                self.assertEqual(
                    xquik._filter_new_tweets(
                        [tweet("opaque-next"), tweet("opaque-new")]
                    ),
                    [tweet("opaque-next")],
                )

            with open(state_path, "r", encoding="utf-8") as state_file:
                self.assertEqual(
                    json.load(state_file),
                    ["opaque-next", "opaque-new", "opaque-old"],
                )

    def test_duplicate_ids_are_returned_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = os.path.join(directory, "seen.json")
            with open(state_path, "w", encoding="utf-8") as state_file:
                json.dump(["seen"], state_file)

            with patch.object(xquik, "SEEN_IDS_PATH", state_path):
                self.assertEqual(
                    xquik._filter_new_tweets(
                        [tweet("unseen"), tweet("unseen"), tweet("seen")]
                    ),
                    [tweet("unseen")],
                )

    def test_invalid_state_is_reseeded_without_returning_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = os.path.join(directory, "seen.json")
            with open(state_path, "w", encoding="utf-8") as state_file:
                state_file.write("{invalid")

            with patch.object(xquik, "SEEN_IDS_PATH", state_path):
                self.assertEqual(
                    xquik._filter_new_tweets([tweet("opaque-id")]),
                    [],
                )

            with open(state_path, "r", encoding="utf-8") as state_file:
                self.assertEqual(json.load(state_file), ["opaque-id"])


class XquikFetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_repeated_cursor_stops_without_advancing_state(self) -> None:
        payloads = [
            {
                "tweets": [{"id": "one", "text": "First"}],
                "has_next_page": True,
                "next_cursor": "repeated",
            },
            {
                "tweets": [{"id": "two", "text": "Second"}],
                "has_next_page": True,
                "next_cursor": "repeated",
            },
        ]
        session = FakeSession(payloads)

        with tempfile.TemporaryDirectory() as directory:
            state_path = os.path.join(directory, "seen.json")
            with open(state_path, "w", encoding="utf-8") as state_file:
                json.dump(["existing"], state_file)

            with (
                patch.object(xquik, "SEEN_IDS_PATH", state_path),
                patch.object(xquik.aiohttp, "ClientSession", return_value=session),
                patch.dict(
                    os.environ,
                    {
                        xquik.XQUIK_API_KEY_ENV: "xq_test",
                        xquik.XQUIK_SEARCH_MAX_PAGES_ENV: "10",
                    },
                    clear=False,
                ),
            ):
                self.assertIsNone(await xquik.fetch_xquik_tweets("market"))

            with open(state_path, "r", encoding="utf-8") as state_file:
                self.assertEqual(json.load(state_file), ["existing"])

        self.assertEqual(len(session.requests), 2)
        self.assertEqual(
            session.requests[0][0],
            "https://xquik.com/api/v1/x/tweets/search",
        )
        self.assertEqual(session.requests[0][1]["x-api-key"], "xq_test")


if __name__ == "__main__":
    unittest.main()
