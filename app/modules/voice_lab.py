"""MODULE 1: Voice Lab & Scripting (Input Pipeline).

- Voice memo intake (text or audio file path)
- AI structuring into script.md with Hook / Body / CTA
- ElevenLabs voice synthesis using the creator's clone
- Human-in-the-loop approval queue (nothing proceeds without Approve)
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..activity import log
from ..config import SCRIPT_OUTPUT_DIR
from ..db import connect, STUDIO_DB, init_studio_db
from ..integrations.elevenlabs import ElevenLabs
from ..knowledge import get, search


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _segment_memo(memo: str) -> tuple[str, str, str]:
    """Structure a raw memo/topic into Hook (first 3s), Body, CTA.

    Uses knowledge-base viral hooks and brand guidelines when available.
    """
    hooks_kb = get("viral_hooks")
    brand = get("brand_guidelines")
    tone_line = ""
    for line in brand.splitlines():
        if line.lower().startswith(("tone", "voice", "style")):
            tone_line = line.strip()
            break

    memo_stripped = memo.strip()
    first_sentence = re.split(r"(?<=[.!?])\s+", memo_stripped)[0][:220]

    hook = (
        f"Hook: {first_sentence} — if you've ever wondered "
        f"how to do this in under 60 seconds, keep watching."
    )

    body = (
        f"Body: Here's the breakdown. {memo_stripped}\n\n"
        f"Step 1: Start with the outcome your audience wants.\n"
        f"Step 2: Show the one thing that changes everything.\n"
        f"Step 3: Do it yourself on camera — imperfection builds trust."
    )

    cta = (
        "CTA: Comment 'STUDIO' below and I'll send you the exact "
        "template I use. Link in bio for the Creator Accelerator ($497) "
        "and 1:1 coaching ($2,800/mo)."
    )

    if hooks_kb:
        first_bullet = ""
        for line in hooks_kb.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                first_bullet = stripped[2:].strip('"').strip()
                break
        if first_bullet:
            hook += f"\n\n[Hook reference: {first_bullet}]"
    if tone_line:
        hook = f"[{tone_line}]\n{hook}"

    return hook, body, cta


def intake_memo(memo: str, source: str = "phone", title: str | None = None) -> dict[str, Any]:
    """Ingest a 2-minute voice memo (or raw topic idea) and write script.md.

    Returns the script record. Status = draft — awaits human approval.
    """
    init_studio_db()
    action = "intake_memo"
    detail = f"source={source} memo_len={len(memo)}"
    log("voice_lab", action, "simulated", detail)

    hook, body, cta = _segment_memo(memo)
    title = title or f"Video script – {memo.strip().splitlines()[0][:60]}"

    markdown = (
        f"# {title}\n\n"
        f"_Source: {source} voice memo · Created: {now_iso()}_\n\n"
        f"---\n\n## Hook (first 3 seconds)\n{hook}\n\n"
        f"---\n\n## Body\n{body}\n\n"
        f"---\n\n## Call to Action\n{cta}\n"
    )

    safe_title = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "script"
    out_path = SCRIPT_OUTPUT_DIR / f"{safe_title}.md"
    out_path.write_text(markdown, encoding="utf-8")

    conn = connect(STUDIO_DB)
    try:
        cur = conn.execute(
            "INSERT INTO scripts (title, source_memo, hook, body, cta, markdown_path, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'draft', ?)",
            (title, memo, hook, body, cta, str(out_path), now_iso()),
        )
        script_id = cur.lastrowid
        conn.execute(
            "INSERT INTO review_queue (item_type, item_id, payload, status, created_at) "
            "VALUES ('script', ?, ?, 'pending', ?)",
            (script_id, markdown, now_iso()),
        )
        conn.commit()
    finally:
        conn.close()

    log("voice_lab", "script_written", "ok", f"script_id={script_id} path={out_path}")
    return {
        "script_id": script_id,
        "title": title,
        "hook": hook,
        "body": body,
        "cta": cta,
        "markdown_path": str(out_path),
        "status": "draft",
        "needs_approval": True,
    }


def synthesize_audio(script_id: int) -> dict[str, Any]:
    """Voice synthesis: ElevenLabs reads the script with the creator's clone.

    Creates a review_queue entry so the user can listen and Approve before any
    video/dubbing work begins.
    """
    init_studio_db()
    conn = connect(STUDIO_DB)
    try:
        row = conn.execute("SELECT * FROM scripts WHERE id = ?", (script_id,)).fetchone()
        if not row:
            raise ValueError(f"script_id={script_id} not found")
        script = dict(row)
    finally:
        conn.close()

    full_text = f"{script['hook']}\n{script['body']}\n{script['cta']}"
    tts = ElevenLabs()
    result = tts.synthesize(full_text, script_id, output_name=f"script_{script_id}_voiceover.mp3")

    conn = connect(STUDIO_DB)
    try:
        cur = conn.execute(
            "INSERT INTO assets (script_id, asset_type, provider, language, path, duration_seconds, status, created_at) "
            "VALUES (?, 'voiceover', 'elevenlabs', 'en', ?, ?, 'generated', ?)",
            (script_id, result["path"], result.get("duration_seconds"), now_iso()),
        )
        asset_id = cur.lastrowid
        conn.execute(
            "INSERT INTO review_queue (item_type, item_id, payload, status, created_at) "
            "VALUES ('audio', ?, ?, 'pending', ?)",
            (asset_id, result["path"], now_iso()),
        )
        conn.commit()
    finally:
        conn.close()

    log("voice_lab", "tts_synthesized", "ok", f"script_id={script_id} asset_id={asset_id} simulated={result.get('simulated')}")
    return {
        "script_id": script_id,
        "asset_id": asset_id,
        "audio_path": result["path"],
        "duration_seconds": result.get("duration_seconds"),
        "simulated": result.get("simulated"),
        "voice_id": result.get("voice_id"),
        "needs_approval": True,
    }


def approve_item(item_type: str, item_id: int, decided_by: str = "human", note: str = "") -> dict[str, Any]:
    """Human Approve: advance a script/audio/video/publish item through the queue."""
    init_studio_db()
    conn = connect(STUDIO_DB)
    try:
        row = conn.execute(
            "SELECT * FROM review_queue WHERE item_type = ? AND item_id = ? AND status = 'pending'",
            (item_type, item_id),
        ).fetchone()
        if not row:
            return {"approved": False, "error": "no pending review item"}
        conn.execute(
            "UPDATE review_queue SET status = 'approved', decided_at = ?, decided_by = ?, note = ? "
            "WHERE id = ?",
            (now_iso(), decided_by, note, row["id"]),
        )
        if item_type == "script":
            conn.execute(
                "UPDATE scripts SET status = 'approved', approved_at = ?, approved_by = ? WHERE id = ?",
                (now_iso(), decided_by, item_id),
            )
        elif item_type == "audio":
            conn.execute(
                "UPDATE assets SET status = 'approved' WHERE id = ?", (item_id,)
            )
        elif item_type == "video":
            conn.execute(
                "UPDATE assets SET status = 'approved' WHERE id = ?", (item_id,)
            )
        elif item_type == "publish":
            conn.execute(
                "UPDATE publish_queue SET status = 'approved' WHERE id = ?", (item_id,)
            )
        conn.commit()
    finally:
        conn.close()

    log("voice_lab", "approve", "approved", f"{item_type}_id={item_id} by={decided_by} note={note}")
    return {"approved": True, "item_type": item_type, "item_id": item_id, "decided_by": decided_by}


def reject_item(item_type: str, item_id: int, decided_by: str = "human", note: str = "") -> dict[str, Any]:
    """Human Reject: stop an item (zero silent automation)."""
    init_studio_db()
    conn = connect(STUDIO_DB)
    try:
        row = conn.execute(
            "SELECT * FROM review_queue WHERE item_type = ? AND item_id = ? AND status = 'pending'",
            (item_type, item_id),
        ).fetchone()
        if not row:
            return {"rejected": False, "error": "no pending review item"}
        conn.execute(
            "UPDATE review_queue SET status = 'rejected', decided_at = ?, decided_by = ?, note = ? "
            "WHERE id = ?",
            (now_iso(), decided_by, note, row["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    log("voice_lab", "reject", "rejected", f"{item_type}_id={item_id} by={decided_by} note={note}")
    return {"rejected": True, "item_type": item_type, "item_id": item_id, "decided_by": decided_by}


def pending_queue() -> list[dict[str, Any]]:
    init_studio_db()
    conn = connect(STUDIO_DB)
    try:
        rows = conn.execute(
            "SELECT * FROM review_queue WHERE status = 'pending' ORDER BY created_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
