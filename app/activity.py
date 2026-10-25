"""agent_activity.log — every action the studio takes, visible and auditable.

Zero silent automation: every module writes structured log entries here (and to
the studio.db activity_log mirror). The daily morning brief surfaces failures
and pending approvals so nothing runs unattended.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ACTIVITY_LOG, ensure_dirs

_lock = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(
    module: str,
    action: str,
    status: str,
    detail: str = "",
    *,
    write_db: bool = True,
    db_path: str | None = None,
) -> None:
    """Append a structured activity record.

    status: ok | simulated | warn | error | skipped | approved | rejected | escalated
    """
    ensure_dirs()
    ts = now_iso()
    line = f"[{ts}] {module:18s} | {action:30s} | {status:10s} | {detail}\n"

    with _lock:
        with open(ACTIVITY_LOG, "a", encoding="utf-8") as fh:
            fh.write(line)

    if write_db:
        try:
            from .db import connect, STUDIO_DB

            conn = connect(STUDIO_DB)
            try:
                conn.execute(
                    "INSERT INTO activity_log (ts, module, action, status, detail) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (ts, module, action, status, detail),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            # Never let logging failure break the studio.
            pass


def recent(limit: int = 50) -> list[str]:
    if not ACTIVITY_LOG.exists():
        return []
    with open(ACTIVITY_LOG, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    return [l.rstrip("\n") for l in lines[-limit:]]
