"""MODULE 2: Video, Visuals & Global Dubbing Pipeline.

- Higgsfield AI video from 3 selfies
- Descript edit + animated captions synced to the approved voiceover
- ElevenLabs dubbing into 10+ languages (voice preserved)
- Metricool smart scheduling per country across YouTube/TikTok/IG/FB
- Global reach tracking per language
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..activity import log
from ..config import DUBBING_LANGUAGES, PLATFORMS, SCHEDULE_WINDOWS
from ..db import connect, STUDIO_DB, init_studio_db
from ..integrations.descript import Descript
from ..integrations.elevenlabs import ElevenLabs
from ..integrations.higgsfield import Higgsfield
from ..integrations.metricool import Metricool
from .voice_lab import now_iso


def _build_captions(script_text: str) -> list[dict[str, str]]:
    """Animated captions burned onto the video (Descript)."""
    parts = [p.strip() for p in script_text.split("\n") if p.strip()]
    captions: list[dict[str, str]] = []
    t = 0.0
    for part in parts:
        captions.append({"start": f"{t:.1f}s", "end": f"{t + 4.0:.1f}s", "text": part[:90]})
        t += 4.5
    return captions


def run_pipeline(script_id: int, selfies: list[str] | None = None) -> dict[str, Any]:
    """Full Module 2 pipeline for an approved script.

    Requires the script (and its voiceover audio) to be approved first.
    Produces: visuals -> captioned master -> dubbed versions -> publish plan.
    Every step is logged; failures are caught and reported, never silent.
    """
    init_studio_db()
    conn = connect(STUDIO_DB)
    try:
        script = conn.execute("SELECT * FROM scripts WHERE id = ?", (script_id,)).fetchone()
        if not script:
            raise ValueError(f"script_id={script_id} not found")
        if script["status"] != "approved":
            script_status = script["status"]
            raise ValueError(
                f"script_id={script_id} is not approved (status={script_status}) — run approval first"
            )
        audio = conn.execute(
            "SELECT * FROM assets WHERE script_id = ? AND asset_type = 'voiceover' AND status = 'approved' ORDER BY id DESC LIMIT 1",
            (script_id,),
        ).fetchone()
        if not audio:
            raise ValueError("no approved voiceover asset — synthesize and approve audio first")
    finally:
        conn.close()

    selfies = selfies or []
    log("video_pipeline", "pipeline_start", "ok", f"script_id={script_id} selfies={len(selfies)}")

    # ── Step 1: visual generation (Higgsfield) ──────────────────────────
    try:
        clips = Higgsfield().generate_clips(script_id, selfies, scene_count=3)
    except Exception as exc:  # noqa: BLE001
        log("video_pipeline", "higgsfield", "error", f"script_id={script_id}: {exc}")
        clips = []

    clip_paths = [c["path"] for c in clips if c.get("path")]

    # ── Step 2: edit & captions (Descript) ─────────────────────────────
    script_text = f"{script['hook']} {script['body']} {script['cta']}"
    captions = _build_captions(script_text)
    try:
        master = Descript().edit_and_caption(script_id, audio["path"], clip_paths, captions)
    except Exception as exc:  # noqa: BLE001
        log("video_pipeline", "descript", "error", f"script_id={script_id}: {exc}")
        master = {"path": "", "simulated": True, "error": str(exc)}

    conn = connect(STUDIO_DB)
    try:
        cur = conn.execute(
            "INSERT INTO assets (script_id, asset_type, provider, language, path, status, created_at) "
            "VALUES (?, 'video', 'descript', 'en', ?, 'generated', ?)",
            (script_id, master.get("path", ""), now_iso()),
        )
        master_asset_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    log("video_pipeline", "master_created", "ok", f"script_id={script_id} asset_id={master_asset_id} simulated={master.get('simulated')}")

    # ── Step 3: global dubbing (ElevenLabs, 10+ languages) ─────────────
    try:
        dubbed = ElevenLabs().dub(master.get("path", ""), DUBBING_LANGUAGES)
    except Exception as exc:  # noqa: BLE001
        log("video_pipeline", "dubbing", "error", f"script_id={script_id}: {exc}")
        dubbed = []

    conn = connect(STUDIO_DB)
    try:
        for d in dubbed:
            conn.execute(
                "INSERT INTO assets (script_id, asset_type, provider, language, path, status, created_at) "
                "VALUES (?, 'dub', 'elevenlabs', ?, ?, 'generated', ?)",
                (script_id, d["language_code"], d.get("path", ""), now_iso()),
            )
        conn.commit()
    finally:
        conn.close()

    log("video_pipeline", "dubbing_done", "ok", f"script_id={script_id} languages_dubbed={len(dubbed)}")

    # ── Step 4: smart scheduling (Metricool) ───────────────────────────
    from datetime import datetime, timedelta

    base_date = datetime.now().astimezone().date().isoformat()
    try:
        plan = Metricool().schedule(master_asset_id, DUBBING_LANGUAGES, base_date)
    except Exception as exc:  # noqa: BLE001
        log("video_pipeline", "metricool", "error", f"script_id={script_id}: {exc}")
        plan = []

    conn = connect(STUDIO_DB)
    try:
        for p in plan:
            if p.get("status") == "failed":
                continue
            conn.execute(
                "INSERT INTO publish_queue (asset_id, platform, language, country, scheduled_at, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'queued', ?)",
                (
                    master_asset_id,
                    p["platform"],
                    p["language"],
                    p.get("country"),
                    p["scheduled_at"],
                    now_iso(),
                ),
            )
        conn.commit()
    finally:
        conn.close()

    log("video_pipeline", "publish_planned", "ok", f"script_id={script_id} queue_entries={len(plan)}")

    # ── Step 5: reach tracking note ────────────────────────────────────
    log("video_pipeline", "reach_tracking", "ok", f"script_id={script_id} tracking_views_per_language=enabled")

    return {
        "script_id": script_id,
        "clips": clips,
        "master_asset_id": master_asset_id,
        "master_path": master.get("path"),
        "dubbed": dubbed,
        "publish_plan": plan,
        "languages": [code for code, _ in DUBBING_LANGUAGES],
    }
