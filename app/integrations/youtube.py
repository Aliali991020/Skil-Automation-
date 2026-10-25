"""YouTube Analytics — performance data for the morning brief (Module 4).

Aggregates views, followers, and revenue per video/language. Simulation mode
returns deterministic placeholder metrics.
"""

from __future__ import annotations

import os
from typing import Any

from ..activity import log
from .base import IntegrationBase


class YouTube(IntegrationBase):
    name = "youtube"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key or os.getenv("YOUTUBE_API_KEY"))

    def video_metrics(self, video_id: str | None = None, days: int = 7) -> list[dict[str, Any]]:
        """Return per-video/platform/language metrics for the last `days` days."""
        action = "youtube_metrics"
        detail = f"video_id={video_id} days={days}"
        if not self.configured:
            log(self.name, action, "simulated", detail)
            return [
                {
                    "video_id": video_id or "sim_master_en",
                    "platform": "youtube",
                    "language": "en",
                    "views": 12400,
                    "followers": 830,
                    "revenue_cents": 4120,
                    "clicks": 310,
                    "conversions": 2,
                },
                {
                    "video_id": video_id or "sim_master_es",
                    "platform": "youtube",
                    "language": "es",
                    "views": 8900,
                    "followers": 410,
                    "revenue_cents": 1950,
                    "clicks": 170,
                    "conversions": 1,
                },
            ]

        def live_call():
            import requests

            resp = requests.get(
                "https://youtube.googleapis.com/youtube/v3/videos",
                params={
                    "part": "statistics",
                    "id": video_id or "",
                    "key": self.api_key,
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()

        try:
            data = self.call_with_retry(action, live_call)
            log(self.name, action, "ok", detail)
            items = data.get("items", [])
            return [
                {
                    "video_id": it.get("id", ""),
                    "platform": "youtube",
                    "language": "en",
                    "views": int(it.get("statistics", {}).get("viewCount", 0)),
                    "followers": 0,
                    "revenue_cents": 0,
                    "clicks": 0,
                    "conversions": 0,
                }
                for it in items
            ]
        except Exception as exc:  # noqa: BLE001
            log(self.name, action, "error", f"{detail}: {exc}")
            raise

    def health(self) -> dict[str, Any]:
        return {"service": self.name, "configured": self.configured, "mode": self.mode}
