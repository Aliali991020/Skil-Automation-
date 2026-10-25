"""Descript — editing & animated captions (Module 2).

Cuts generated clips to match the approved voiceover and burns dynamic,
high-engagement captions onto the video. Simulation mode produces a
captioned master asset.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..activity import log
from ..config import ASSETS_DIR
from .base import IntegrationBase


class Descript(IntegrationBase):
    name = "descript"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key or os.getenv("DESCRIPT_API_KEY"))

    def edit_and_caption(
        self,
        script_id: int,
        voiceover_path: str,
        clip_paths: list[str],
        captions: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Assemble the master video: cuts + voiceover sync + burned captions.

        captions: list of {start, end, text}. Returns the master asset path.
        """
        action = "edit_and_caption"
        detail = f"script_id={script_id} clips={len(clip_paths)} captions={len(captions)}"
        out_path = ASSETS_DIR / f"script_{script_id}_master.mp4"

        if not self.configured:
            out_path.write_bytes(b"SIMULATED-DESCRIPT-MASTER:")
            log(self.name, action, "simulated", f"{detail} -> {out_path}")
            return {
                "path": str(out_path),
                "duration_seconds": 18.0,
                "simulated": True,
                "provider": "descript",
                "captions_burned": len(captions),
            }

        def live_call():
            import requests

            resp = requests.post(
                "https://api.descript.com/v1/projects",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "voiceover": voiceover_path,
                    "clips": clip_paths,
                    "captions": captions,
                },
                timeout=180,
            )
            resp.raise_for_status()
            data = resp.json()
            out_path.write_bytes(requests.get(data["master_url"], timeout=180).content)
            return data

        try:
            data = self.call_with_retry(action, live_call)
            out_path.write_bytes(b"LIVE-DESCRIPT-PLACEHOLDER")  # replace with real download in production
            log(self.name, action, "ok", f"{detail}")
            return {
                "path": str(out_path),
                "duration_seconds": data.get("duration_seconds", 18.0),
                "simulated": False,
                "provider": "descript",
                "external_id": data.get("id"),
            }
        except Exception as exc:  # noqa: BLE001
            log(self.name, action, "error", f"{detail}: {exc}")
            raise

    def health(self) -> dict[str, Any]:
        return {"service": self.name, "configured": self.configured, "mode": self.mode}
