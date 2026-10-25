"""SQLite state management — studio.db (studio state) and leads.db (CRM).

Local-first, cloud-synced: these are the single source of truth for scripts,
the review queue, assets, publishing, metrics, leads, and conversations.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .config import LEADS_DB, STUDIO_DB

_STUDIO_SCHEMA = [
    # Scripts produced by the Voice Lab (Module 1)
    """CREATE TABLE IF NOT EXISTS scripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        source_memo TEXT NOT NULL,
        hook TEXT NOT NULL,
        body TEXT NOT NULL,
        cta TEXT NOT NULL,
        markdown_path TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft',        -- draft / approved / rejected / published
        created_at TEXT NOT NULL,
        approved_at TEXT,
        approved_by TEXT,
        audio_asset_id INTEGER,
        video_asset_id INTEGER
    )""",
    # Human-in-the-loop review queue (Module 1 + execution rules)
    """CREATE TABLE IF NOT EXISTS review_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_type TEXT NOT NULL,                      -- script / audio / video / publish
        item_id INTEGER NOT NULL,
        payload TEXT NOT NULL,                        -- JSON blob for context
        status TEXT NOT NULL DEFAULT 'pending',       -- pending / approved / rejected
        created_at TEXT NOT NULL,
        decided_at TEXT,
        decided_by TEXT,
        note TEXT
    )""",
    # Generated assets (audio, video, dubbed versions)
    """CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        script_id INTEGER NOT NULL,
        asset_type TEXT NOT NULL,                     -- voiceover / video / dub / captioned
        provider TEXT NOT NULL,                       -- elevenlabs / higgsfield / descript / metricool
        language TEXT DEFAULT 'en',
        path TEXT NOT NULL,
        duration_seconds REAL,
        status TEXT NOT NULL DEFAULT 'generated',     -- generated / approved / published / failed
        created_at TEXT NOT NULL,
        FOREIGN KEY (script_id) REFERENCES scripts(id)
    )""",
    # Scheduled / published distribution
    """CREATE TABLE IF NOT EXISTS publish_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id INTEGER NOT NULL,
        platform TEXT NOT NULL,                       -- youtube / tiktok / instagram / facebook
        language TEXT NOT NULL DEFAULT 'en',
        country TEXT,
        scheduled_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued',        -- queued / published / failed / blocked
        published_at TEXT,
        external_id TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (asset_id) REFERENCES assets(id)
    )""",
    # Omnichannel metrics (Module 4)
    """CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        platform TEXT NOT NULL,
        language TEXT NOT NULL DEFAULT 'en',
        views INTEGER DEFAULT 0,
        followers INTEGER DEFAULT 0,
        revenue_cents INTEGER DEFAULT 0,
        clicks INTEGER DEFAULT 0,
        conversions INTEGER DEFAULT 0,
        UNIQUE(date, platform, language)
    )""",
    # Activity log mirror (structured copy of agent_activity.log)
    """CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        module TEXT NOT NULL,
        action TEXT NOT NULL,
        status TEXT NOT NULL,
        detail TEXT
    )""",
]


_LEADS_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        channel TEXT NOT NULL DEFAULT 'dm',           -- instagram / tiktok / youtube / email / website
        inquiry_type TEXT NOT NULL,                   -- course / coaching / brand_deal / general
        interest_product TEXT,
        budget_cents INTEGER,
        posting_frequency TEXT,                       -- daily / weekly / occasional / unknown
        business_size TEXT,                           -- solo / small / mid / enterprise / unknown
        fit_score INTEGER DEFAULT 0,                  -- 0-100
        status TEXT NOT NULL DEFAULT 'new',           -- new / qualified / converted / escalated / closed
        stripe_checkout_url TEXT,
        cal_booking_url TEXT,
        escalated INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER NOT NULL,
        role TEXT NOT NULL,                           -- ai_maya / lead / human
        message TEXT NOT NULL,
        ts TEXT NOT NULL,
        FOREIGN KEY (lead_id) REFERENCES leads(id)
    )""",
]


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_studio_db() -> None:
    conn = connect(STUDIO_DB)
    try:
        for stmt in _STUDIO_SCHEMA:
            conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()


def init_leads_db() -> None:
    conn = connect(LEADS_DB)
    try:
        for stmt in _LEADS_SCHEMA:
            conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()


def init_all() -> None:
    from .config import ensure_dirs

    ensure_dirs()
    init_studio_db()
    init_leads_db()


def execute_many(db_path: Path, statements: list[tuple[str, tuple[Any, ...]]]) -> None:
    conn = connect(db_path)
    try:
        conn.executemany(*zip(*statements)) if statements else None
        for stmt, params in statements:
            conn.execute(stmt, params)
        conn.commit()
    finally:
        conn.close()
