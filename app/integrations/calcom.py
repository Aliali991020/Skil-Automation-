"""Cal.com — calendar booking for qualified leads (Module 3).

Routes qualified leads to a booking link so the human founder only spends time
on high-value conversations.
"""

from __future__ import annotations

import os
from typing import Any

from ..activity import log
from ..config import CALCOM_EVENT_TYPE_ID
from .base import IntegrationBase


class CalCom(IntegrationBase):
    name = "calcom"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key or os.getenv("CALCOM_API_KEY"))

    def booking_url(self, lead_id: int, event_type_id: str | None = None) -> dict[str, Any]:
        """Generate a Cal.com booking link for a qualified lead."""
        etid = event_type_id or CALCOM_EVENT_TYPE_ID or "general"
        action = "calcom_booking"
        detail = f"lead_id={lead_id} event_type={etid}"

        if not self.configured:
            url = f"https://cal.com/mayacole/{etid}?lead={lead_id}"
            log(self.name, action, "simulated", f"{detail} -> {url}")
            return {"booking_url": url, "event_type_id": etid, "simulated": True}

        def live_call():
            import requests

            resp = requests.post(
                f"https://api.cal.com/v1/scheduling-links",
                headers={"Cal-API-Key": self.api_key, "Content-Type": "application/json"},
                json={"eventTypeId": int(etid) if etid.isdigit() else etid, "metadata": {"lead_id": lead_id}},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()

        try:
            data = self.call_with_retry(action, live_call)
            log(self.name, action, "ok", detail)
            return {"booking_url": data.get("url", ""), "event_type_id": etid, "simulated": False}
        except Exception as exc:  # noqa: BLE001
            log(self.name, action, "error", f"{detail}: {exc}")
            raise

    def health(self) -> dict[str, Any]:
        return {"service": self.name, "configured": self.configured, "mode": self.mode}
