"""SKIL Automation modules — the four studio pipelines."""

from .voice_lab import intake_memo, synthesize_audio, approve_item, reject_item, pending_queue
from .video_pipeline import run_pipeline
from .sales_line import ai_sales_reply, log_lead, convert_lead, escalate_lead, list_leads
from .director import aggregate_metrics, next_topic_recommendation, morning_brief, run_morning_brief

__all__ = [
    "intake_memo",
    "synthesize_audio",
    "approve_item",
    "reject_item",
    "pending_queue",
    "run_pipeline",
    "ai_sales_reply",
    "log_lead",
    "convert_lead",
    "escalate_lead",
    "list_leads",
    "aggregate_metrics",
    "next_topic_recommendation",
    "morning_brief",
    "run_morning_brief",
]
