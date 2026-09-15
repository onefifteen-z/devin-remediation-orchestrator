# Devin Remediation Orchestrator

An event-driven autonomous remediation platform powered by [Devin](https://devin.ai). The orchestrator decides **when** engineering work should happen; Devin decides **how** it gets done.

## Problem

Recurring maintenance, compatibility, security, and reliability work competes with feature development. Teams need automation that can handle issues requiring repository understanding, diagnosis, implementation, testing, and iteration—not just scripted fixes for known problems.

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
        +--> Devin V3 API (sessions, consumption, automations)
        |
        +--> GitHub REST API (PR / CI / issue actions)
        |
        v
  React Operations Dashboard
```

See [docs/architecture.md](docs/architecture.md) for detailed design.

## Capabilities

- **Event-driven intake** — GitHub `issues` / `labeled` webhook, manual API, repo scan, scheduled intake
- **Devin orchestration** — Session create/poll/message, playbooks, structured output, session insights
- **GitHub lifecycle** — PR webhooks as authoritative merge state; post-merge issue comment/close
- **CI intelligence** — `check_run` classification and same-session repair for code failures
- **Operations dashboard** — Metrics, task table with filters, CI/structured-result/insights panels
- **Production guardrails** — Concurrency limits, retries, ACU caps, webhook deduplication, issue-level idempotency

## Documentation

```
docs/
├── architecture.md    # System design, lifecycle, authority boundaries
├── operations.md      # Run, configure, monitor, troubleshoot
└── validation.md      # Real remediation evidence
```

## Repository structure

```
devin-remediation-orchestrator/
├── backend/          # FastAPI orchestrator
├── frontend/         # React operations dashboard
├── docs/
├── docker-compose.yml
└── Makefile
```

## Quick start

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
make migrate    # apply Alembic migrations to head
make up         # docker compose up --build
make down       # docker compose down
```

### Database migrations

Schema changes are managed with [Alembic](https://alembic.sqlalchemy.org/) under `backend/alembic/`. Migrations run automatically on backend startup.

```bash
cd backend
alembic upgrade head
```

## Docker

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up --build
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000

## Tests

```bash
# Backend (243 tests)
cd backend && source .venv/bin/activate && pytest -v

# Frontend (60 tests)
cd frontend && npm test
```

## Configuration

Key defaults (full reference: [docs/operations.md](docs/operations.md#configuration)):

- `DEVIN_LIVE_ENABLED=false` — safe mode; no live Devin calls or ACU spend
- `REMEDIATE_LABEL=devin-remediate` — webhook and manual scan
- `SCHEDULED_LABEL=devin-scheduled` — scheduled intake only

## Operations

Run, configure, monitor, and troubleshoot: [docs/operations.md](docs/operations.md).

Validate a real remediation run: [docs/validation.md](docs/validation.md).

## Security

- GitHub webhook HMAC-SHA256 verification with constant-time comparison
- Secrets stored in backend `.env` only — never in `VITE_*` variables or API responses
- Safe error responses (no stack traces to clients)

## Future extensions

- Jira / Linear / security scanner event sources
- Slack notifications
- Automatic PR merge
- Multi-repository rollout
- Policy-based approval gates
- Customer-specific playbooks
