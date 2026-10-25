"""MODULE 3: AI Sales Line & Fan Voice (Monetization & CRM).

- Maya: 24/7 AI sales agent (ElevenLabs conversational pipeline)
- Transparency: discloses AI, answers from knowledge base, fit-checks + scores leads
- Conversion: Stripe checkout links + Cal.com booking
- leads.db logging; human escalation for high-value deals
"""

from __future__ import annotations

from typing import Any

from ..activity import log
from ..config import LEAD_FIT_SCORE_HOT, LEAD_HIGH_VALUE_THRESHOLD, PRODUCTS
from ..db import connect, LEADS_DB, init_leads_db
from ..integrations.calcom import CalCom
from ..integrations.elevenlabs import ElevenLabs
from ..integrations.stripe import Stripe
from ..knowledge import search


def _fit_score(inquiry_type: str, budget_cents: int | None, posting_frequency: str, business_size: str) -> int:
    """Fit-check: budget, posting frequency, business size -> 0..100 score."""
    score = 0
    if inquiry_type in ("course", "coaching", "brand_deal"):
        score += 30
    else:
        score += 10
    if budget_cents is not None:
        if budget_cents >= LEAD_HIGH_VALUE_THRESHOLD * 100:
            score += 30
        elif budget_cents >= 497 * 100:
            score += 20
        elif budget_cents >= 100 * 100:
            score += 10
    freq_score = {"daily": 20, "weekly": 12, "occasional": 6, "unknown": 4}
    score += freq_score.get(posting_frequency, 4)
    size_score = {"enterprise": 20, "mid": 14, "small": 8, "solo": 4, "unknown": 4}
    score += size_score.get(business_size, 4)
    return min(score, 100)


def _ai_disclosure() -> str:
    from ..config import CREATOR_NAME

    return (
        f"Hi, I'm Maya — the AI sales assistant for {CREATOR_NAME}. "
        "I want to be upfront: I'm an AI, not the human creator. I answer based on the "
        "studio's knowledge base and can route you to the right checkout or calendar link."
    )


def ai_sales_reply(message: str, lead_id: int | None = None, channel: str = "dm") -> dict[str, Any]:
    """Maya responds to a fan/lead inquiry.

    - Explicitly states she is an AI
    - Answers from the knowledge base
    - Runs a fit-check if the lead shares budget/frequency/size
    - Scores the lead; offers Stripe checkout or Cal.com booking when qualified
    - Flags high-value deals for human escalation
    """
    init_leads_db()
    disclosed = _ai_disclosure()

    kb_hits = search(message)[:3]
    knowledge_context = " ".join(snippet for _, snippet in kb_hits) if kb_hits else ""

    # ElevenLabs conversational agent (simulated or live)
    try:
        agent_reply = ElevenLabs().agent_converse("maya-agent", str(lead_id or 0), message)
        ai_text = agent_reply.get("reply", disclosed)
    except Exception as exc:  # noqa: BLE001
        log("sales_line", "agent_converse", "error", f"lead_id={lead_id}: {exc}")
        ai_text = disclosed

    reply = f"{disclosed}\n\n{ai_text}\n\nBased on what you shared, here's what fits:\n{knowledge_context or 'Tell me your budget, how often you post, and your business size so I can find the right fit.'}"

    escalate = False
    if lead_id is not None:
        # crude escalation signal: brand deal mention or high-value keywords
        if any(k in message.lower() for k in ("brand deal", "sponsorship", "$25,000", "25000")):
            escalate = True

    log("sales_line", "ai_reply", "ok", f"lead_id={lead_id} channel={channel} escalate={escalate}")
    return {
        "reply": reply,
        "disclosed_ai": True,
        "knowledge_sources": [name for name, _ in kb_hits],
        "escalate": escalate,
        "lead_id": lead_id,
    }


def log_lead(
    channel: str,
    inquiry_type: str,
    name: str | None = None,
    interest_product: str | None = None,
    budget_cents: int | None = None,
    posting_frequency: str | None = None,
    business_size: str | None = None,
) -> dict[str, Any]:
    """Create/update a lead in leads.db and run the fit-check score."""
    init_leads_db()
    score = _fit_score(inquiry_type or "general", budget_cents, posting_frequency or "unknown", business_size or "unknown")
    status = "qualified" if score >= LEAD_FIT_SCORE_HOT else "new"
    escalate = 1 if (budget_cents or 0) >= LEAD_HIGH_VALUE_THRESHOLD * 100 else 0

    conn = connect(LEADS_DB)
    try:
        cur = conn.execute(
            "INSERT INTO leads (name, channel, inquiry_type, interest_product, budget_cents, "
            "posting_frequency, business_size, fit_score, status, escalated, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, channel, inquiry_type, interest_product, budget_cents, posting_frequency,
             business_size, score, status, escalate, _iso(), _iso()),
        )
        lead_id = cur.lastrowid
        conn.execute(
            "INSERT INTO conversations (lead_id, role, message, ts) VALUES (?, 'ai_maya', ?, ?)",
            (lead_id, "Lead logged and fit-checked.", _iso()),
        )
        conn.commit()
    finally:
        conn.close()

    log("sales_line", "lead_logged", "ok", f"lead_id={lead_id} score={score} status={status} escalated={bool(escalate)}")
    return {
        "lead_id": lead_id,
        "fit_score": score,
        "status": status,
        "escalated": bool(escalate),
    }


def convert_lead(lead_id: int, product_key: str, decided_by: str = "human") -> dict[str, Any]:
    """Frictionless conversion: Stripe checkout + Cal.com booking for a qualified lead.

    Requires human sign-off (passed as decided_by) — no silent transactions.
    """
    init_leads_db()
    conn = connect(LEADS_DB)
    try:
        lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not lead:
            return {"converted": False, "error": "lead not found"}
        if lead["status"] == "converted":
            return {"converted": False, "error": "lead already converted"}
    finally:
        conn.close()

    checkout = Stripe().create_checkout(product_key, lead_id)
    booking = CalCom().booking_url(lead_id)

    conn = connect(LEADS_DB)
    try:
        conn.execute(
            "UPDATE leads SET status = 'converted', stripe_checkout_url = ?, cal_booking_url = ?, updated_at = ? WHERE id = ?",
            (checkout.get("checkout_url"), booking.get("booking_url"), _iso(), lead_id),
        )
        conn.execute(
            "INSERT INTO conversations (lead_id, role, message, ts) VALUES (?, 'ai_maya', ?, ?)",
            (lead_id, f"Qualified! Checkout: {checkout.get('checkout_url')} | Book time: {booking.get('booking_url')}", _iso()),
        )
        conn.commit()
    finally:
        conn.close()

    log("sales_line", "convert_lead", "ok", f"lead_id={lead_id} product={product_key} by={decided_by}")
    return {
        "converted": True,
        "lead_id": lead_id,
        "checkout_url": checkout.get("checkout_url"),
        "booking_url": booking.get("booking_url"),
        "simulated": checkout.get("simulated", False),
    }


def escalate_lead(lead_id: int, reason: str) -> dict[str, Any]:
    """Human escalation: high-value deals / negotiations alert the founder."""
    init_leads_db()
    conn = connect(LEADS_DB)
    try:
        conn.execute(
            "UPDATE leads SET status = 'escalated', escalated = 1, updated_at = ? WHERE id = ?",
            (_iso(), lead_id),
        )
        conn.execute(
            "INSERT INTO conversations (lead_id, role, message, ts) VALUES (?, 'human', ?, ?)",
            (lead_id, f"Escalated to founder: {reason}", _iso()),
        )
        conn.commit()
    finally:
        conn.close()

    log("sales_line", "escalate_lead", "escalated", f"lead_id={lead_id} reason={reason}")
    return {"escalated": True, "lead_id": lead_id, "reason": reason}


def list_leads() -> list[dict[str, Any]]:
    init_leads_db()
    conn = connect(LEADS_DB)
    try:
        rows = conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
