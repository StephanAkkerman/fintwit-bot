"""Local contract tests for the opt-in Adanos API adapter."""

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from api import adanos


class AdanosTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_stock_sources_use_header_and_explicit_dates(self):
        seen = []

        async def handle(request):
            seen.append(request)
            return web.json_response({"found": False, "daily_trend": None})

        app = web.Application()
        app.router.add_get("/{tail:.*}", handle)
        async with TestServer(app) as server:
            with patch.object(
                adanos, "BASE_URL", str(server.make_url("/")).rstrip("/")
            ):
                for source in adanos.SOURCE_PATHS:
                    result = await adanos.get_stock_sentiment(
                        "AAPL", source, date(2026, 9, 1), date(2026, 9, 7), "test-key"
                    )
                    self.assertFalse(result["found"])

        self.assertEqual(
            [request.path for request in seen],
            [f"{path}/AAPL" for path in adanos.SOURCE_PATHS.values()],
        )
        for request in seen:
            self.assertEqual(request.headers["X-API-Key"], "test-key")
            self.assertEqual(request.query["from"], "2026-09-01")
            self.assertEqual(request.query["to"], "2026-09-07")
            self.assertNotIn("days", request.query)

    async def test_permission_error_is_not_turned_into_no_data(self):
        async def deny(_):
            return web.Response(status=403)

        app = web.Application()
        app.router.add_get("/{tail:.*}", deny)
        async with TestServer(app) as server:
            with (
                patch.object(adanos, "BASE_URL", str(server.make_url("/")).rstrip("/")),
                self.assertRaises(aiohttp.ClientResponseError) as caught,
            ):
                await adanos.get_stock_sentiment(
                    "AAPL", "news", date(2026, 9, 1), date(2026, 9, 7), "test-key"
                )
        self.assertEqual(caught.exception.status, 403)
        self.assertNotIn("test-key", str(caught.exception))

    def test_source_specific_summary_preserves_missing_data(self):
        start, end = date(2026, 9, 1), date(2026, 9, 7)
        missing = adanos.format_stock_sentiment(
            {"found": False}, "AAPL", "news", start, end
        )
        self.assertIn("No Adanos data", missing)
        self.assertNotIn("Sentiment score", missing)

        result = adanos.format_stock_sentiment(
            {"found": True, "trade_count": 4, "sentiment_score": 0.2},
            "AAPL",
            "polymarket",
            start,
            end,
        )
        self.assertIn("Trades: 4", result)
        self.assertNotIn("Mentions", result)


if __name__ == "__main__":
    unittest.main()
