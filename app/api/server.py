"""Review-queue web API — the human-in-the-loop control panel.

Run with:  python -m app.api.server   (stdlib, no dependencies)
or:        uvicorn app.api.server:app  (if FastAPI is installed)

Endpoints:
  GET    /                      dashboard + pending queue + brief summary
  GET    /queue                 pending review items (JSON)
  POST   /approve/<type>/<id>   approve a script / audio / video / publish item
  POST   /reject/<type>/<id>    reject an item
  POST   /intake                ingest a new voice memo (JSON: {memo, source, title})
  POST   /synthesize/<id>       voice synthesis for a script
  POST   /pipeline/<id>         run the full video/dub/schedule pipeline
  GET    /brief                 morning brief (text)
  GET    /leads                 CRM leads (JSON)
  POST   /lead                  log a new lead (JSON)
  POST   /convert/<id>          convert a lead (JSON: {product_key, decided_by})
  GET    /health                service configuration status
"""

from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app.config import ensure_dirs, settings_summary
from app.db import init_all
from app.modules import (
    approve_item,
    aggregate_metrics,
    convert_lead,
    escalate_lead,
    intake_memo,
    list_leads,
    morning_brief,
    pending_queue,
    reject_item,
    run_pipeline,
    synthesize_audio,
    ai_sales_reply,
    log_lead,
)

try:
    from fastapi import FastAPI  # type: ignore

    _HAS_FASTAPI = True
except Exception:  # pragma: no cover
    FastAPI = None  # type: ignore[assignment]
    _HAS_FASTAPI = False

if _HAS_FASTAPI:
    app = FastAPI(title="SKIL Automation — Studio Director", version="1.0.0")


def _json(payload: Any, status: int = 200) -> bytes:
    body = json.dumps(payload, default=str, indent=2).encode("utf-8")
    return body


class Handler(BaseHTTPRequestHandler):
    server_version = "SKIL-Automation/1.0"

    def log_message(self, fmt, *args):  # quiet default logging
        return

    def _send(self, status: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return {}

    def _route(self) -> tuple[str, list[str]]:
        path = self.path.split("?", 1)[0]
        parts = [p for p in path.strip("/").split("/") if p]
        return parts[0] if parts else "root", parts[1:]

    # ── GET ──────────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        route, parts = self._route()

        if route == "root":
            self._send(200, _json({
                "name": "SKIL Automation — One-Person AI Creator Studio",
                "status": "running",
                "pending_approvals": len(pending_queue()),
                "config": settings_summary(),
            }))
            return

        if route == "queue":
            self._send(200, _json({"pending": pending_queue()}))
            return

        if route == "brief":
            text = morning_brief(write_file=True)
            self._send(200, text.encode("utf-8"), content_type="text/markdown; charset=utf-8")
            return

        if route == "leads":
            self._send(200, _json({"leads": list_leads()}))
            return

        if route == "metrics":
            self._send(200, _json(aggregate_metrics()))
            return

        if route == "health":
            self._send(200, _json({"configured": settings_summary()}))
            return

        self._send(404, _json({"error": "not found"}))

    # ── POST ─────────────────────────────────────────────────────────────

    def do_POST(self) -> None:
        route, parts = self._route()
        body = self._read_body()

        try:
            if route == "intake":
                result = intake_memo(
                    body.get("memo", ""),
                    source=body.get("source", "api"),
                    title=body.get("title"),
                )
                self._send(201, _json(result))
                return

            if route == "synthesize" and len(parts) >= 1:
                script_id = int(parts[0])
                result = synthesize_audio(script_id)
                self._send(200, _json(result))
                return

            if route == "pipeline" and len(parts) >= 1:
                script_id = int(parts[0])
                selfies = body.get("selfies", [])
                result = run_pipeline(script_id, selfies)
                self._send(200, _json(result))
                return

            if route == "approve" and len(parts) >= 2:
                result = approve_item(parts[0], int(parts[1]), decided_by=body.get("decided_by", "web"))
                status = 200 if result.get("approved") or result.get("rejected") else 400
                self._send(status, _json(result))
                return

            if route == "reject" and len(parts) >= 2:
                result = reject_item(parts[0], int(parts[1]), decided_by=body.get("decided_by", "web"), note=body.get("note", ""))
                status = 200 if result.get("rejected") else 400
                self._send(status, _json(result))
                return

            if route == "lead":
                result = log_lead(
                    channel=body.get("channel", "dm"),
                    inquiry_type=body.get("inquiry_type", "general"),
                    name=body.get("name"),
                    interest_product=body.get("interest_product"),
                    budget_cents=body.get("budget_cents"),
                    posting_frequency=body.get("posting_frequency"),
                    business_size=body.get("business_size"),
                )
                self._send(201, _json(result))
                return

            if route == "sales" and body.get("message"):
                result = ai_sales_reply(
                    body["message"],
                    lead_id=body.get("lead_id"),
                    channel=body.get("channel", "dm"),
                )
                self._send(200, _json(result))
                return

            if route == "convert" and len(parts) >= 1:
                result = convert_lead(
                    int(parts[0]),
                    body.get("product_key", "course"),
                    decided_by=body.get("decided_by", "web"),
                )
                self._send(200, _json(result))
                return

            if route == "escalate" and len(parts) >= 1:
                result = escalate_lead(int(parts[0]), body.get("reason", "high-value deal"))
                self._send(200, _json(result))
                return

        except ValueError as exc:
            self._send(400, _json({"error": str(exc)}))
            return
        except Exception as exc:  # noqa: BLE001
            self._send(500, _json({"error": f"internal: {exc}"}))
            return

        self._send(404, _json({"error": "not found"}))


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    ensure_dirs()
    init_all()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"SKIL Automation review queue listening on http://{host}:{port}")
    print("Open the dashboard to Approve/Reject scripts, audio, video, and publishing.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
