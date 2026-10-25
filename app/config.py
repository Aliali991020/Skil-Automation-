"""Studio configuration — environment-driven with safe defaults.

Nothing is read from the network at import time. All external API integrations
run in simulation mode unless the corresponding API key is present in the
environment (or a `.env` file loaded by the entry point).
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:  # pragma: no cover — dotenv is optional
    pass

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
KNOWLEDGE_DIR = ROOT / "knowledge"
SCRIPTS_DIR = ROOT / "scripts"

STUDIO_DB = DATA_DIR / "studio.db"
LEADS_DB = DATA_DIR / "leads.db"
ACTIVITY_LOG = DATA_DIR / "agent_activity.log"
REVIEW_QUEUE_DIR = DATA_DIR / "review_queue"
SCRIPT_OUTPUT_DIR = DATA_DIR / "scripts_out"
ASSETS_DIR = DATA_DIR / "assets"
BRIEFS_DIR = DATA_DIR / "briefs"

# ── External services ──────────────────────────────────────────────────────
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_CLONE_ID = os.getenv("ELEVENLABS_VOICE_CLONE_ID", "maya-cole-clone")
HIGGSFIELD_API_KEY = os.getenv("HIGGSFIELD_API_KEY")
DESCRIPT_API_KEY = os.getenv("DESCRIPT_API_KEY")
METRICOOL_API_KEY = os.getenv("METRICOOL_API_KEY")
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
STRIPE_CHECKOUT_BASE_URL = os.getenv("STRIPE_CHECKOUT_BASE_URL", "https://buy.stripe.com/")
CALCOM_API_KEY = os.getenv("CALCOM_API_KEY")
CALCOM_EVENT_TYPE_ID = os.getenv("CALCOM_EVENT_TYPE_ID")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Human-in-the-loop notification channels
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ── Studio identity ────────────────────────────────────────────────────────
CREATOR_NAME = os.getenv("CREATOR_NAME", "Maya Cole")
BUSINESS_NAME = os.getenv("BUSINESS_NAME", "One-Person AI Creator Studio")
STUDIO_TZ = os.getenv("STUDIO_TZ", "Asia/Kolkata")
MORNING_BRIEF_HOUR = int(os.getenv("MORNING_BRIEF_HOUR", "7"))

# ── Product catalog (prices in USD) ────────────────────────────────────────
PRODUCTS = {
    "course": {"name": "Creator Accelerator Course", "price": 497, "currency": "usd"},
    "coaching": {"name": "1:1 Coaching (monthly)", "price": 2800, "currency": "usd", "interval": "month"},
    "brand_deal": {"name": "Brand Partnership", "price": 25000, "currency": "usd"},
}

# Global dubbing targets (Module 2)
DUBBING_LANGUAGES = [
    ("es", "Spanish"),
    ("pt", "Portuguese"),
    ("de", "German"),
    ("hi", "Hindi"),
    ("ja", "Japanese"),
    ("fr", "French"),
    ("vi", "Vietnamese"),
    ("ar", "Arabic"),
    ("it", "Italian"),
    ("nl", "Dutch"),
]

# Optimal local publishing windows by target market (Module 2 / Metricool)
SCHEDULE_WINDOWS = {
    "ES": "19:00",   # Spain
    "BR": "20:30",   # Brazil
    "IN": "18:38",   # India
    "US": "19:00",   # United States
    "GB": "20:00",   # United Kingdom
    "DE": "19:30",   # Germany
    "JP": "21:00",   # Japan
    "FR": "19:00",   # France
    "AR": "20:00",   # Arabic-speaking markets
    "VN": "20:00",   # Vietnam
    "IT": "21:00",   # Italy
    "NL": "20:30",   # Netherlands
}

PLATFORMS = ["youtube", "tiktok", "instagram", "facebook"]

# Lead qualification thresholds (Module 3)
LEAD_HIGH_VALUE_THRESHOLD = 5000  # USD — deals above this always escalate to human
LEAD_FIT_SCORE_HOT = 70


def ensure_dirs() -> None:
    for d in (
        DATA_DIR,
        KNOWLEDGE_DIR,
        REVIEW_QUEUE_DIR,
        SCRIPT_OUTPUT_DIR,
        ASSETS_DIR,
        BRIEFS_DIR,
        SCRIPTS_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)


def is_configured(key: str | None) -> bool:
    return bool(key and key.strip())


def settings_summary() -> dict[str, str | bool]:
    return {
        "creator": CREATOR_NAME,
        "business": BUSINESS_NAME,
        "elevenlabs": is_configured(ELEVENLABS_API_KEY),
        "higgsfield": is_configured(HIGGSFIELD_API_KEY),
        "descript": is_configured(DESCRIPT_API_KEY),
        "metricool": is_configured(METRICOOL_API_KEY),
        "stripe": is_configured(STRIPE_API_KEY),
        "calcom": is_configured(CALCOM_API_KEY),
        "youtube": is_configured(YOUTUBE_API_KEY),
        "slack": is_configured(SLACK_WEBHOOK_URL),
        "telegram": is_configured(TELEGRAM_BOT_TOKEN),
    }
