"""Metricool — smart multi-platform scheduling (Module 2).

Calculates the optimal local publishing time per target country and queues the
content across YouTube, TikTok, Instagram, and Facebook. Nothing is actually
queued on the platforms until the human approves publishing.
"""

from __future__ import annotations

import os
from typing import Any

from ..activity import log
from ..config import PLATFORMS, SCHEDULE_WINDOWS
from .base import IntegrationBase


class Metricool(IntegrationBase):
    name = "metricool"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key or os.getenv("METRICOOL_API_KEY"))

    def schedule(
        self,
        asset_id: int,
        languages: list[tuple[str, str]],
        base_date_iso: str,
    ) -> list[dict[str, Any]]:
        """Produce a per-country/per-platform publish plan.

        Returns queue entries with scheduled local times. The entries are
        inserted into publish_queue (status=queued) by the caller after approval.
        """
        action = "schedule_publish"
        plan: list[dict[str, Any]] = []

        from datetime import datetime, timedelta

        base = datetime.fromisoformat(base_date_iso)
        for code, _label in languages:
            country = code.upper()
            local_time = SCHEDULE_WINDOWS.get(country, "19:00")
            hour, minute = map(int, local_time.split(":"))
            scheduled = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if scheduled <= base:
                scheduled += timedelta(days=1)

            for platform in PLATFORMS:
                detail = f"asset_id={asset_id} lang={code} platform={platform} at={scheduled.isoformat()}"
                if not self.configured:
                    log(self.name, action, "simulated", detail)
                    plan.append(
                        {
                            "asset_id": asset_id,
                            "platform": platform,
                            "language": code,
                            "country": country,
                            "scheduled_at": scheduled.isoformat(),
                            "simulated": True,
                        }
                    )
                    continue

                def live_call(c=code, p=platform, s=scheduled.isoformat()):
                    import requests

                    resp = requests.post(
                        "https://api.metricool.com/v1/schedule",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={
                            "asset_id": asset_id,
                            "platform": p,
                            "language": c,
                            "scheduled_at": s,
                        },
                        timeout=60,
                    )
                    resp.raise_for_status()
                    return resp.json()

                try:
                    data = self.call_with_retry(action, live_call)
                    log(self.name, action, "ok", detail)
                    plan.append(
                        {
                            "asset_id": asset_id,
                            "platform": platform,
                            "language": code,
                            "country": country,
                            "scheduled_at": scheduled.isoformat(),
                            "simulated": False,
                            "external_id": data.get("schedule_id"),
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    log(self.name, action, "error", f"{detail}: {exc}")
                    plan.append(
                        {
                            "asset_id": asset_id,
                            "platform": platform,
                            "language": code,
                            "country": country,
                            "scheduled_at": scheduled.isoformat(),
                            "simulated": False,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )
        return plan

    def health(self) -> dict[str, Any]:
        return {"service": self.name, "configured": self.configured, "mode": self.mode}
