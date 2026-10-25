"""Higgsfield — AI video generation from reference selfies (Module 2).

Generates matching AI video clips from 3 user selfies/reference images so the
creator never has to film. Simulation mode writes placeholder clips.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..activity import log
from ..config import ASSETS_DIR
from .base import IntegrationBase


class Higgsfield(IntegrationBase):
    name = "higgsfield"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key or os.getenv("HIGGSFIELD_API_KEY"))

    def generate_clips(
        self,
        script_id: int,
        reference_images: list[str],
        scene_count: int = 3,
    ) -> list[dict[str, Any]]:
        """Produce AI video clips matching the creator's appearance.

        reference_images: paths to 3 selfies. Returns clip descriptors with
        local paths (simulated) or live URLs.
        """
        if len(reference_images) < 3:
            log(self.name, "generate_clips", "error", f"script_id={script_id} only {len(reference_images)} selfies provided (need 3)")
            raise ValueError("Higgsfield requires exactly 3 reference selfies")

        action = "generate_clips"
        clips: list[dict[str, Any]] = []
        for i in range(scene_count):
            detail = f"script_id={script_id} scene={i + 1}/{scene_count}"
            out_path = ASSETS_DIR / f"script_{script_id}_scene_{i + 1}.mp4"
            if not self.configured:
                out_path.write_bytes(b"SIMULATED-HIGGSFIELD-CLIP:")
                log(self.name, action, "simulated", f"{detail} -> {out_path}")
                clips.append(
                    {
                        "scene": i + 1,
                        "path": str(out_path),
                        "duration_seconds": 6.0,
                        "simulated": True,
                        "provider": "higgsfield",
                    }
                )
                continue

            def live_call(i=i):
                import requests  # local import to keep hard dep optional

                resp = requests.post(
                    "https://api.higgsfield.ai/v1/generate",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "reference_images": reference_images,
                        "scene_index": i,
                    },
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                out_path.write_bytes(requests.get(data["video_url"], timeout=120).content)
                return data

            try:
                data = self.call_with_retry(action, live_call)
                clips.append(
                    {
                        "scene": i + 1,
                        "path": str(out_path),
                        "duration_seconds": data.get("duration_seconds", 6.0),
                        "simulated": False,
                        "provider": "higgsfield",
                        "external_id": data.get("id"),
                    }
                )
                log(self.name, action, "ok", f"{detail}")
            except Exception as exc:  # noqa: BLE001
                log(self.name, action, "error", f"{detail}: {exc}")
                clips.append(
                    {
                        "scene": i + 1,
                        "path": "",
                        "duration_seconds": 0.0,
                        "simulated": False,
                        "error": str(exc),
                    }
                )
        return clips

    def health(self) -> dict[str, Any]:
        return {"service": self.name, "configured": self.configured, "mode": self.mode}
