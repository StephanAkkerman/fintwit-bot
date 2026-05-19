from __future__ import annotations

from typing import List

from xclient import XTimelineClient

from constants.logger import logger


async def get_tweet() -> List[dict]:
    """Fetch raw timeline entries using the x-timeline-scraper XTimelineClient.

    Returns a list of timeline "entries" dicts (same shape as before) so callers
    like the timeline loop can continue to operate unchanged.
    """
    try:
        async with XTimelineClient(
            "curl.txt", persist_last_id_path="state/last_id.txt"
        ) as xc:
            payload = await xc.fetch_raw(text=False)
            if not isinstance(payload, dict) or not payload:
                return []
            # Use the client's internal extractor to get the raw "entries" list
            try:
                entries = xc._get_entries(payload)
            except Exception:
                logger.error("Failed to extract entries from payload")
                return []
            return entries or []
    except Exception as e:
        logger.error(f"Error fetching timeline with XTimelineClient: {e}")
        return []
