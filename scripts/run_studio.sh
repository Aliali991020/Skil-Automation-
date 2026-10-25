#!/usr/bin/env bash
# SKIL Automation — One-Person AI Creator Studio
# Usage: ./scripts/run_studio.sh [command] [args]
#
# Commands:
#   intake "memo text"        Ingest a voice memo into script.md
#   queue                     Show pending approvals
#   approve <type> <id>       Approve a review item
#   brief                     Generate the 7:00 AM morning brief
#   server                    Start the review-queue web UI (http://localhost:8000)
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Note: no .env found — running in simulation mode (no API keys)."
  echo "Copy .env.example to .env and add keys for live integrations."
fi

python3 -m app.cli "$@"
