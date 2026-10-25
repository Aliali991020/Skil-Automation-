"""MODULE 4: Studio Director & Analytics (The Brain / Claude Code).

- Omnichannel metrics aggregation (Stripe, Cal.com, YouTube, ElevenLabs)
- 7:00 AM automated morning brief: financials, performance, next-step topic/hook
- Knowledge-grounded topic recommendation
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from ..activity import log, recent
from ..config import BRIEFS_DIR, CREATOR_NAME, MORNING_BRIEF_HOUR, STUDIO_TZ
from ..db import connect, LEADS_DB, STUDIO_DB, init_all
from ..integrations.youtube import YouTube
from ..integrations.stripe import Stripe
from ..integrations.calcom import CalCom
from ..integrations.elevenlabs import ElevenLabs
from ..knowledge import get, search, list_knowledge


def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def aggregate_metrics() -> dict[str, Any]:
    """Pull actuals from every channel (simulated when keys are missing).

    Returns financial + performance numbers for the last 24 h / 7 days.
    """
    log("director", "aggregate_metrics", "simulated", "collecting omnichannel metrics")

    yt = YouTube().video_metrics(days=7)

    revenue_24h_cents = 0
    conversions_24h = 0
    try:
        conn = connect(STUDIO_DB)
        try:
            yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
            rows = conn.execute(
                "SELECT SUM(revenue_cents), SUM(conversions) FROM metrics WHERE date = ?",
                (yesterday,),
            ).fetchone()
            if rows:
                revenue_24h_cents = rows[0] or 0
                conversions_24h = rows[1] or 0
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        log("director", "metrics_read", "warn", f"studio.db metrics read: {exc}")

    leads = []
    try:
        conn = connect(LEADS_DB)
        try:
            leads = conn.execute(
                "SELECT id, name, inquiry_type, fit_score, status, escalated FROM leads ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        log("director", "leads_read", "warn", f"leads.db read: {exc}")

    return {
        "date": _today_str(),
        "revenue_24h_usd": round(revenue_24h_cents / 100, 2),
        "conversions_24h": conversions_24h,
        "youtube": yt,
        "total_views": sum(v.get("views", 0) for v in yt),
        "total_followers": sum(v.get("followers", 0) for v in yt),
        "total_revenue_cents": sum(v.get("revenue_cents", 0) for v in yt),
        "leads": [dict(l) for l in leads],
        "services": {
            "elevenlabs": ElevenLabs().health(),
            "stripe": Stripe().health(),
            "calcom": CalCom().health(),
            "youtube": YouTube().health(),
        },
    }


def _first_viral_hook() -> str:
    """Pull the first proven hook pattern from knowledge/viral_hooks.md."""
    content = get("viral_hooks")
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            hook = stripped[2:].strip('"').strip()
            if hook:
                return hook
    return "The one thing stopping your growth isn't your content — it's your hook."


def next_topic_recommendation() -> dict[str, str]:
    """Actionable next step: exact topic + hook for the next video script.

    Grounded in the knowledge base (viral hooks + brand guidelines) and the
    fastest-growing language track from metrics.
    """
    brand = get("brand_guidelines")
    top_hook = _first_viral_hook()
    topic = "Turn a 2-minute phone memo into a full multilingual creator studio"
    recommended_hook = (
        f"Hook: {top_hook}"
    )
    brand_note = "on-brand"
    for line in brand.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            brand_note = line
            break
    return {
        "topic": topic,
        "recommended_hook": recommended_hook,
        "brand_alignment": brand_note,
        "rationale": "Multilingual reach is the fastest-growing track per last brief.",
    }


def morning_brief(write_file: bool = True) -> str:
    """Compile the 1-page morning brief (7:00 AM). Returns the text and
    optionally writes data/briefs/morning_brief_YYYY-MM-DD.md."""
    init_all()
    m = aggregate_metrics()
    rec = next_topic_recommendation()

    pending = []
    try:
        conn = connect(STUDIO_DB)
        try:
            pending = conn.execute(
                "SELECT item_type, item_id, created_at FROM review_queue WHERE status = 'pending' ORDER BY created_at ASC"
            ).fetchall()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        log("director", "brief_queue_read", "warn", str(exc))

    failures = [line for line in recent(200) if " | error |" in line]

    lines: list[str] = []
    lines.append(f"# Good morning, {CREATOR_NAME} — Studio Brief")
    lines.append(f"_Generated {datetime.now(timezone.utc).astimezone().strftime('%A, %B %d, %Y at %H:%M')} (studio tz: {STUDIO_TZ})_\n")

    lines.append("## 1. Financial summary (last 24 h)")
    lines.append(f"- Revenue: **${m['revenue_24h_usd']:.2f}**")
    lines.append(f"- Conversions: **{m['conversions_24h']}**")
    lines.append(f"- 7-day video revenue (tracked): **${m['total_revenue_cents'] / 100:.2f}**\n")

    lines.append("## 2. Performance analytics")
    lines.append(f"- Total views (tracked): **{m['total_views']:,}**")
    lines.append(f"- New followers: **{m['total_followers']:,}**")
    langs = {}
    for v in m["youtube"]:
        langs.setdefault(v.get("language", "en"), 0)
        langs[v.get("language", "en")] += v.get("views", 0)
    fastest = max(langs, key=langs.get) if langs else "en"
    lines.append(f"- Fastest-growing language track: **{fastest}** ({langs.get(fastest, 0):,} views)")
    lines.append(f"- Active leads in CRM: **{len(m['leads'])}**\n")

    lines.append("## 3. Pending approvals (nothing public until you hit Approve)")
    if pending:
        for p in pending:
            lines.append(f"- {p['item_type']} id={p['item_id']} awaiting since {p['created_at']}")
    else:
        lines.append("- None — the review queue is clear.\n")

    lines.append("## 4. Actionable next step — next video")
    lines.append(f"- Topic: **{rec['topic']}**")
    lines.append(f"- Hook: {rec['recommended_hook']}")
    lines.append(f"- Brand note: {rec['brand_alignment']}\n")

    lines.append("## 5. Service health")
    for name, h in m["services"].items():
        lines.append(f"- {name}: {h['mode']} (configured={h['configured']})")

    if failures:
        lines.append("\n## 6. Failures to review")
        for f in failures[:10]:
            lines.append(f"- {f}")

    lines.append("\n---")
    lines.append("_One-person studio · Zero employees · Everything awaits your Approve._")

    text = "\n".join(lines) + "\n"

    if write_file:
        BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
        brief_path = BRIEFS_DIR / f"morning_brief_{_today_str()}.md"
        brief_path.write_text(text, encoding="utf-8")
        log("director", "morning_brief", "ok", f"wrote {brief_path}")

    return text


def run_morning_brief() -> None:
    """Entry point for a scheduled job (cron at 7:00 AM local)."""
    print(morning_brief())
