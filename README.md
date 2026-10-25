# SKIL Automation — One-Person AI Creator Studio

An autonomous multi-agent orchestration system that runs a complete media creator
studio and digital business for a single founder with **zero employees**.
Built on the *One-Person AI Creator Studio (Autonomous & Zero-Employee Blueprint)* skill definition.

> ⚠️ **Absolute Safety Constraint:** nothing goes public or automated externally
> until the human founder hits **"Approve"** in the review queue.

## What's in the box

| Module | What it does |
|---|---|
| **M1 Voice Lab & Scripting** | Voice memo intake → structured `script.md` (Hook / Body / CTA) → ElevenLabs voice synthesis with the creator's clone → human-in-the-loop approval queue |
| **M2 Video, Visuals & Global Dubbing** | Higgsfield AI clips from 3 selfies → Descript edit + animated captions → ElevenLabs dubbing into 10+ languages → Metricool smart scheduling per country → per-language reach tracking |
| **M3 AI Sales Line & Fan Voice** | "Maya" AI sales agent (discloses AI, knowledge-base answers, fit-check + scoring) → Stripe checkout + Cal.com booking → `leads.db` CRM → human escalation for high-value deals |
| **M4 Studio Director & Analytics** | Omnichannel metrics (Stripe, Cal.com, YouTube, ElevenLabs) → 7:00 AM morning brief (financials, performance, next-step topic/hook) |
| **Knowledge Layer** | `/knowledge/` markdown: brand guidelines, viral hooks, pricing sheet, product catalog, language rules |

## Quick start

```bash
cd Skil-Automation-

# 1. Create a virtual env (optional but recommended)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # fastapi, uvicorn, python-dotenv, requests (optional extras)

# 2. Configure (optional — studio runs in simulation mode without keys)
cp .env.example .env
# edit .env and add ELEVENLABS_API_KEY, STRIPE_API_KEY, etc. for live mode

# 3. Ingest a voice memo / topic idea
./scripts/run_studio.sh intake --memo "I want to show creators how to dub one video into 10 languages with AI" --source phone

# 4. Review what's pending
./scripts/run_studio.sh queue

# 5. Approve the script, then synthesize audio, then approve audio
./scripts/run_studio.sh approve --type script --id 1 --by founder
./scripts/run_studio.sh synthesize --script-id 1
./scripts/run_studio.sh approve --type audio --id 1 --by founder

# 6. Run the full video/dub/schedule pipeline (needs 3 selfies for Higgsfield)
./scripts/run_studio.sh pipeline --script-id 1 --selfies selfie1.jpg,selfie2.jpg,selfie3.jpg

# 7. Morning brief (7:00 AM equivalent)
./scripts/run_studio.sh brief

# 8. Open the human-in-the-loop review-queue web UI
./scripts/run_studio.sh server   # → http://localhost:8000
```

### CLI commands

- `intake [--memo TEXT] [--memo-file PATH] [--source phone] [--title TITLE]`
- `queue` — list pending approvals
- `approve --type script\|audio\|video\|publish --id N --by founder [--note ...]`
- `reject --type ... --id N --by founder [--note ...]`
- `synthesize --script-id N`
- `pipeline --script-id N [--selfies a.jpg,b.jpg,c.jpg]`
- `brief` — write and print `data/briefs/morning_brief_YYYY-MM-DD.md`
- `leads` — CRM listing from `leads.db`
- `log-lead --channel dm --inquiry-type course --name "Alex" --budget 600`
- `convert --id N --product course --by founder` (Stripe + Cal.com)
- `escalate --id N --reason "major brand sponsorship"`
- `settings` — which services are configured (live vs simulated)
- `server [--host 0.0.0.0] [--port 8000]` — review-queue web dashboard

### Web API (the review queue)

`GET /` — dashboard with pending approvals + service config  
`GET /queue` — pending items (JSON)  
`POST /approve/<type>/<id>` — approve an item  
`POST /reject/<type>/<id>` — reject an item  
`POST /intake` — JSON `{memo, source, title}`  
`POST /synthesize/<id>` — voice synthesis  
`POST /pipeline/<id>` — JSON `{selfies: [...]}`  
`GET /brief` — morning brief (markdown)  
`GET /leads` — CRM (JSON)  
`POST /lead` — log a lead  
`POST /convert/<id>` — JSON `{product_key, decided_by}`  
`GET /health` — service health

## How safety is enforced

1. **Review queue gates everything.** Scripts, audio, video, and publishing all
   enter `data/review_queue` as `pending` and cannot proceed without an explicit
   `approve`. No silent automation.
2. **Simulation mode by default.** Without API keys, every integration
   (ElevenLabs, Higgsfield, Descript, Metricool, Stripe, Cal.com, YouTube)
   returns deterministic placeholders, writes to `agent_activity.log`, and never
   touches the network or moves money.
3. **Graceful failure.** API rate limits/failures are caught, logged to
   `agent_activity.log` and `studio.db.activity_log`, and surfaced in the morning
   brief — never swallowed.
4. **Local-first state.** `studio.db` (scripts, queue, assets, publish, metrics,
   activity) and `leads.db` (CRM + conversations) live locally under `data/`.

## Data layout

```
data/
  studio.db             # scripts, review_queue, assets, publish_queue, metrics, activity_log
  leads.db              # leads, conversations
  agent_activity.log    # append-only audit trail
  scripts_out/*.md      # generated script.md files
  assets/*.mp4|.mp3     # generated voiceover/video/dub assets
  briefs/*.md           # morning briefs
knowledge/              # brand-aligned markdown knowledge base
```

## Requirements

Python 3.10+. The stdlib-only server runs out of the box. `pip install -r
requirements.txt` adds FastAPI/uvicorn (production web server),
python-dotenv, and requests (used by live integration clients).

## Next

Add real API keys to `.env` to flip integrations from simulated to live, then
hit **Approve** in the review queue and let Studio Director run the studio — one
person, zero employees.
