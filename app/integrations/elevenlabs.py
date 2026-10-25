"""ElevenLabs integration — voice synthesis (Module 1) and dubbing (Module 2),
plus conversational AI agents (Module 3).

Live mode requires ELEVENLABS_API_KEY. Simulation mode returns deterministic
placeholders and never touches the network.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from ..activity import log
from ..config import ASSETS_DIR, ELEVENLABS_VOICE_CLONE_ID
from .base import IntegrationBase

try:
    import requests  # type: ignore

    _HAS_REQUESTS = True
except Exception:  # pragma: no cover
    requests = None  # type: ignore[assignment]
    _HAS_REQUESTS = False


class ElevenLabs(IntegrationBase):
    name = "elevenlabs"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key or os.getenv("ELEVENLABS_API_KEY"))
        self.voice_id = ELEVENLABS_VOICE_CLONE_ID
        self.base_url = "https://api.elevenlabs.io/v1"

    # ── Module 1: voice synthesis ──────────────────────────────────────────

    def synthesize(self, text: str, script_id: int, output_name: str | None = None) -> dict[str, Any]:
        """Read a structured script with the creator's voice clone.

        Returns {path, duration_seconds, simulated}. The audio file is written
        under data/assets/ and registered in studio.db by the caller.
        """
        action = "tts_synthesize"
        detail = f"script_id={script_id} voice={self.voice_id} chars={len(text)}"

        if not self.configured or not _HAS_REQUESTS:
            safe = "".join(c for c in text if c.isalnum() or c in " .-_")[:40]
            fname = output_name or f"script_{script_id}_{hashlib.sha1(safe.encode()).hexdigest()[:8]}.mp3"
            out_path = ASSETS_DIR / fname
            out_path.write_bytes(b"SIMULATED-ELEVENLABS-AUDIO:" + text.encode("utf-8")[:200])
            duration = max(1.0, round(len(text) / 14.0, 2))  # rough chars-per-second estimate
            log(self.name, action, "simulated", f"{detail} -> {out_path}")
            return {
                "path": str(out_path),
                "duration_seconds": duration,
                "simulated": True,
                "voice_id": self.voice_id,
                "provider": "elevenlabs",
            }

        def live_call() -> dict[str, Any]:
            assert requests is not None
            resp = requests.post(
                f"{self.base_url}/text-to-speech/{self.voice_id}",
                headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
                json={"text": text, "model_id": "eleven_multilingual_v2"},
                timeout=60,
            )
            resp.raise_for_status()
            fname = output_name or f"script_{script_id}_{hashlib.sha1(text.encode()).hexdigest()[:8]}.mp3"
            out_path = ASSETS_DIR / fname
            out_path.write_bytes(resp.content)
            return {"path": str(out_path), "duration_seconds": None, "simulated": False, "voice_id": self.voice_id}

        result = self.call_with_retry(action, live_call)
        log(self.name, action, "ok", f"{detail} -> {result['path']}")
        return result

    # ── Module 2: global dubbing ───────────────────────────────────────────

    def dub(self, video_path: str, target_languages: list[tuple[str, str]]) -> list[dict[str, Any]]:
        """Dub a master video into N languages preserving voice pitch/tone.

        Returns one entry per language with a simulated (or live) dub asset path.
        """
        dubbed: list[dict[str, Any]] = []
        for code, label in target_languages:
            action = "dub_video"
            detail = f"video={video_path} lang={code} ({label})"
            if not self.configured or not _HAS_REQUESTS:
                out_path = Path(video_path).with_name(
                    f"{Path(video_path).stem}_{code}_dub.mp4"
                )
                out_path.write_bytes(b"SIMULATED-ELEVENLABS-DUB:")
                log(self.name, action, "simulated", f"{detail} -> {out_path}")
                dubbed.append(
                    {
                        "language_code": code,
                        "language": label,
                        "path": str(out_path),
                        "voice_preserved": True,
                        "simulated": True,
                    }
                )
                continue

            def live_call(code=code):  # capture loop var
                assert requests is not None
                resp = requests.post(
                    f"{self.base_url}/dubbing",
                    headers={"xi-api-key": self.api_key},
                    data={
                        "source_audio_url": video_path,
                        "target_languages": json.dumps([code]),
                        "voice_id": self.voice_id,
                    },
                    timeout=120,
                )
                resp.raise_for_status()
                return resp.json()

            try:
                result = self.call_with_retry(action, live_call)
                dubbed.append(
                    {
                        "language_code": code,
                        "language": label,
                        "path": result.get("dubbed_video_url", ""),
                        "voice_preserved": True,
                        "simulated": False,
                        "dubbing_id": result.get("dubbing_id"),
                    }
                )
                log(self.name, action, "ok", f"{detail}")
            except Exception as exc:  # noqa: BLE001
                log(self.name, action, "error", f"{detail}: {exc}")
                dubbed.append(
                    {
                        "language_code": code,
                        "language": label,
                        "path": "",
                        "voice_preserved": False,
                        "simulated": False,
                        "error": str(exc),
                    }
                )
        return dubbed

    # ── Module 3: conversational AI sales agent ────────────────────────────

    def agent_converse(self, agent_id: str, lead_id: str, message: str) -> dict[str, Any]:
        """Pass a fan/lead message through the Maya AI agent and get a reply."""
        action = "agent_converse"
        detail = f"agent={agent_id} lead={lead_id} msg_len={len(message)}"
        if not self.configured or not _HAS_REQUESTS:
            reply = (
                "Hi! I'm Maya, the AI assistant for the creator. "
                "I'm not the human creator — I'm an AI clone trained on their "
                "knowledge base. How can I help you today?"
            )
            log(self.name, action, "simulated", f"{detail} -> reply_len={len(reply)}")
            return {
                "reply": reply,
                "agent_id": agent_id,
                "lead_id": lead_id,
                "simulated": True,
                "disclosed_ai": True,
            }

        def live_call() -> dict[str, Any]:
            assert requests is not None
            resp = requests.post(
                f"{self.base_url}/agents/{agent_id}/conversations",
                headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
                json={"lead_id": lead_id, "message": message},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()

        try:
            result = self.call_with_retry(action, live_call)
            log(self.name, action, "ok", f"{detail}")
            return result
        except Exception as exc:  # noqa: BLE001
            log(self.name, action, "error", f"{detail}: {exc}")
            raise

    def health(self) -> dict[str, Any]:
        return {
            "service": self.name,
            "configured": self.configured,
            "mode": self.mode,
            "voice_id": self.voice_id,
        }
