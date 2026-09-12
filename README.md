# Devin Remediation Orchestrator

An event-driven autonomous remediation platform powered by [Devin](https://devin.ai). The orchestrator decides **when** engineering work should happen; Devin decides **how** it gets done.

## Problem Statement

Recurring maintenance, compatibility, security, and reliability work competes with feature development. Teams need automation that can handle issues requiring repository understanding, diagnosis, implementation, testing, and iteration—not just scripted fixes for known problems.

## Why Devin

Deterministic automation works when the fix path is known in advance. Devin enables automation of engineering tasks where remediation requires:

- Understanding repository context
- Diagnosing root causes
- Implementing safe fixes
- Adding regression tests
- Iterating on CI failures

## Architecture

```
GitHub Issue (devin-remediate label)
        |
        v
  Signed Webhook (HMAC-SHA256)
        |
        v
  FastAPI Orchestrator
        |
        +--> SQLite (audit trail + metrics)
        |
        +--> Devin V3 API (session create / message)  [Phase 2]
        |
        +--> GitHub REST API (PR / CI)                [Phase 2]
        |
        v
  React Operations Dashboard
```

See [docs/architecture.md](docs/architecture.md) for detailed design.

## Event-Driven Lifecycle

```
Issue → Webhook → Orchestrator → Devin → PR → CI → Review → Merge
```

Phase 1 implements the foundation through webhook ingestion and task persistence. Live Devin session creation is gated behind `DEVIN_LIVE_ENABLED=false` by default.

## Repository Structure

```
devin-remediation-orchestrator/
├── backend/          # FastAPI orchestrator
├── frontend/         # React operations dashboard
├── docs/             # Architecture documentation
├── docker-compose.yml
└── Makefile
```

## Local Development

### Prerequisites

- Python 3.12+
- Node.js 22+
- Docker (optional)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in credentials
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Dashboard: http://localhost:3000

### Makefile shortcuts

```bash
make backend    # start backend
make frontend   # start frontend
make test       # run backend tests
make up         # docker compose up --build
make down       # docker compose down
```

## Backend Environment Variables

| Variable | Description |
|----------|-------------|
| `DEVIN_API_KEY` | Devin service user API key (`cog_...`) |
| `DEVIN_ORG_ID` | Organization ID |
| `DEVIN_API_BASE_URL` | Default: `https://api.devin.ai/v3` |
| `DEVIN_LIVE_ENABLED` | `false` in Phase 1 (prevents live session creation) |
| `GITHUB_TOKEN` | GitHub PAT for REST API (Phase 2) |
| `GITHUB_WEBHOOK_SECRET` | Webhook HMAC secret |
| `DATABASE_URL` | Default: `sqlite:///./data/app.db` |
| `MAX_ACTIVE_SESSIONS` | Concurrency limit (default: 3) |
| `MAX_RETRIES` | Max retries before escalation (default: 3) |
| `DEVIN_SESSION_TIMEOUT_MINUTES` | Session timeout (default: 60) |
| `MAX_ACU_PER_TASK` | Per-task ACU cap (optional) |
| `DAILY_ACU_CAP` | Daily ACU cap (optional) |
| `CORS_ORIGINS` | Comma-separated origins |
| `LOG_LEVEL` | Logging level |

## Frontend Environment Variables

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | Backend URL (default: `http://localhost:8000`) |

Never put secrets in `VITE_*` variables.

## Docker Setup

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up --build
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000

## Running Tests

```bash
cd backend
source .venv/bin/activate
pytest -v
```

## GitHub Webhook Configuration

1. In your repository settings, add a webhook:
   - **Payload URL:** `https://<your-host>/webhooks/github`
   - **Content type:** `application/json`
   - **Secret:** same value as `GITHUB_WEBHOOK_SECRET`
   - **Events:** Issues

2. Add the `devin-remediate` label to an issue to trigger remediation.

## Simulate a Webhook Locally

```bash
SECRET="test-webhook-secret"
BODY='{"action":"labeled","issue":{"number":1,"title":"Test issue","html_url":"https://github.com/owner/repo/issues/1","labels":[{"name":"devin-remediate"},{"name":"bug"}]},"repository":{"full_name":"owner/repo"},"label":{"name":"devin-remediate"}}'
SIG="sha256=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')"

curl -X POST http://localhost:8000/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: issues" \
  -H "X-GitHub-Delivery: test-delivery-001" \
  -H "X-Hub-Signature-256: $SIG" \
  -d "$BODY"
```

## Task Lifecycle

| Status | Meaning |
|--------|---------|
| `RECEIVED` | Webhook accepted, task persisted |
| `SESSION_CREATED` | Devin session created |
| `RUNNING` | Devin actively working |
| `PR_OPENED` | Pull request created |
| `CI_FAILED` | CI failed on PR |
| `READY_FOR_REVIEW` | CI passed, awaiting human review |
| `MERGED` | PR merged |
| `FAILED` | Unrecoverable failure |
| `ESCALATED` | Retries/timeout/ACU cap exceeded |

## Observability Metrics

The dashboard and `GET /api/metrics` expose:

- Success rate, merge rate
- Median MTTR (merged tasks only)
- 7-day throughput
- CI recovery rate
- Total / average ACU
- Active, failed, escalated task counts

All metrics are computed from real database state—empty when no tasks exist.

## Security Model

- GitHub webhook HMAC-SHA256 verification with constant-time comparison
- Secrets stored in backend `.env` only
- No credentials in API responses or frontend
- Safe error responses (no stack traces to clients)

## Production Guardrails

- `MAX_ACTIVE_SESSIONS` concurrency limit
- `MAX_RETRIES` with escalation
- `DEVIN_SESSION_TIMEOUT_MINUTES`
- Optional `MAX_ACU_PER_TASK` and `DAILY_ACU_CAP`
- Webhook deduplication via `X-GitHub-Delivery`

## Phase 1 Status (Current)

**Implemented:**

- Repository structure and configuration
- FastAPI application with health, tasks, metrics, webhook endpoints
- SQLite persistence with audit trail
- GitHub webhook HMAC verification and event filtering
- Webhook deduplication
- Devin V3 client abstraction (HTTP layer, mockable)
- GitHub client skeleton
- Prompt builder and orchestration service
- Background task dispatch (gated live Devin calls)
- React operations dashboard
- Docker setup and tests

**Not yet implemented (Phase 2):**

- Live Devin session creation from webhooks (`DEVIN_LIVE_ENABLED=true`)
- Session polling and PR/CI detection
- CI failure → same-session message loop
- GitHub REST API integration
- ACU consumption tracking from Devin billing API
- Issue auto-close on merge
- First real Superset remediation

## Known Limitations

- `DEVIN_LIVE_ENABLED` defaults to `false` to prevent accidental ACU spend
- GitHub client methods raise `NotImplementedError`
- Session poller is a skeleton
- CI recovery rate uses simplified heuristics without full status history
- No database migrations (uses `create_all` on startup)

## Future Extensions

- Jira / Linear / security scanner event sources
- Slack notifications
- Scheduled remediation jobs
- Multi-repository rollout
- Policy-based approval gates
- Customer-specific playbooks
