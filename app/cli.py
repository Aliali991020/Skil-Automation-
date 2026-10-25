"""Command-line interface for the SKIL Automation studio.

Examples:
  python -m app cli intake --memo "Hook idea: ..." --source phone
  python -m app cli approve --type script --id 1 --by founder
  python -m app cli synthesize --script-id 1
  python -m app cli pipeline --script-id 1 --selfies selfie1.jpg,selfie2.jpg,selfie3.jpg
  python -m app cli brief
  python -m app cli server --port 8000
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from app.config import ensure_dirs, settings_summary
from app.db import init_all
from app.modules import (
    approve_item,
    ai_sales_reply,
    convert_lead,
    escalate_lead,
    intake_memo,
    list_leads,
    log_lead,
    morning_brief,
    pending_queue,
    reject_item,
    run_pipeline,
    synthesize_audio,
)
from .api.server import main as server_main


def cmd_intake(args: argparse.Namespace) -> None:
    memo = args.memo
    if args.memo_file:
        memo = open(args.memo_file, encoding="utf-8").read()
    result = intake_memo(memo, source=args.source, title=args.title)
    print(json_dumps(result))


def cmd_approve(args: argparse.Namespace) -> None:
    print(json_dumps(approve_item(args.type, int(args.id), decided_by=args.by, note=args.note)))


def cmd_reject(args: argparse.Namespace) -> None:
    print(json_dumps(reject_item(args.type, int(args.id), decided_by=args.by, note=args.note)))


def cmd_synthesize(args: argparse.Namespace) -> None:
    print(json_dumps(synthesize_audio(int(args.script_id))))


def cmd_pipeline(args: argparse.Namespace) -> None:
    selfies = [s.strip() for s in args.selfies.split(",")] if args.selfies else []
    print(json_dumps(run_pipeline(int(args.script_id), selfies)))


def cmd_brief(args: argparse.Namespace) -> None:
    print(morning_brief(write_file=True))


def cmd_queue(args: argparse.Namespace) -> None:
    items = pending_queue()
    print(json_dumps({"pending": items}))


def cmd_leads(args: argparse.Namespace) -> None:
    print(json_dumps({"leads": list_leads()}))


def cmd_sales(args: argparse.Namespace) -> None:
    print(json_dumps(ai_sales_reply(args.message, lead_id=args.lead_id, channel=args.channel)))


def cmd_log_lead(args: argparse.Namespace) -> None:
    print(json_dumps(log_lead(
        channel=args.channel,
        inquiry_type=args.inquiry_type,
        name=args.name,
        interest_product=args.product,
        budget_cents=int(args.budget) if args.budget else None,
        posting_frequency=args.frequency,
        business_size=args.size,
    )))


def cmd_convert(args: argparse.Namespace) -> None:
    print(json_dumps(convert_lead(int(args.id), args.product, decided_by=args.by)))


def cmd_escalate(args: argparse.Namespace) -> None:
    print(json_dumps(escalate_lead(int(args.id), args.reason)))


def cmd_settings(args: argparse.Namespace) -> None:
    print(json_dumps(settings_summary(), indent=2))


def json_dumps(obj: Any, indent: int | None = 2) -> str:
    import json

    return json.dumps(obj, default=str, indent=indent)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skil", description="SKIL Automation — One-Person AI Creator Studio")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("intake", help="Ingest a voice memo / topic into script.md")
    p.add_argument("--memo", default="", help="Raw memo text")
    p.add_argument("--memo-file", help="Path to a memo text file")
    p.add_argument("--source", default="phone", help="Source channel (phone, slack, telegram, api)")
    p.add_argument("--title", help="Script title")
    p.set_defaults(func=cmd_intake)

    p = sub.add_parser("queue", help="List pending approvals")
    p.set_defaults(func=cmd_queue)

    p = sub.add_parser("approve", help="Approve a review-queue item")
    p.add_argument("--type", required=True, choices=["script", "audio", "video", "publish"])
    p.add_argument("--id", required=True)
    p.add_argument("--by", default="founder")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("reject", help="Reject a review-queue item")
    p.add_argument("--type", required=True, choices=["script", "audio", "video", "publish"])
    p.add_argument("--id", required=True)
    p.add_argument("--by", default="founder")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_reject)

    p = sub.add_parser("synthesize", help="Voice synthesis for an approved script")
    p.add_argument("--script-id", type=int, required=True)
    p.set_defaults(func=cmd_synthesize)

    p = sub.add_parser("pipeline", help="Run Module 2 video/dub/schedule pipeline")
    p.add_argument("--script-id", type=int, required=True)
    p.add_argument("--selfies", help="Comma-separated selfie paths")
    p.set_defaults(func=cmd_pipeline)

    p = sub.add_parser("brief", help="Generate the 7:00 AM morning brief")
    p.set_defaults(func=cmd_brief)

    p = sub.add_parser("leads", help="List CRM leads")
    p.set_defaults(func=cmd_leads)

    p = sub.add_parser("sales", help="Get a reply from Maya, the AI sales agent")
    p.add_argument("message", help="Fan/lead message")
    p.add_argument("--lead-id", type=int)
    p.add_argument("--channel", default="dm")
    p.set_defaults(func=cmd_sales)

    p = sub.add_parser("log-lead", help="Log a new lead and fit-check it")
    p.add_argument("--channel", default="dm")
    p.add_argument("--inquiry-type", default="general")
    p.add_argument("--name")
    p.add_argument("--product")
    p.add_argument("--budget")
    p.add_argument("--frequency", choices=["daily", "weekly", "occasional", "unknown"], default="unknown")
    p.add_argument("--size", choices=["solo", "small", "mid", "enterprise", "unknown"], default="unknown")
    p.set_defaults(func=cmd_log_lead)

    p = sub.add_parser("convert", help="Convert a lead (Stripe + Cal.com)")
    p.add_argument("--id", required=True, type=int)
    p.add_argument("--product", default="course")
    p.add_argument("--by", default="founder")
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser("escalate", help="Escalate a lead to the human founder")
    p.add_argument("--id", required=True, type=int)
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_escalate)

    p = sub.add_parser("settings", help="Show configured services")
    p.set_defaults(func=cmd_settings)

    p = sub.add_parser("server", help="Start the review-queue web UI")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=lambda a: server_main(host=a.host, port=a.port))

    return parser


def main(argv: list[str] | None = None) -> int:
    ensure_dirs()
    init_all()
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
