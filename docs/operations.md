# Operations

How to run, configure, monitor, and troubleshoot the Devin Remediation Orchestrator.

Related docs: [architecture.md](architecture.md) · [validation.md](validation.md)

## Local development

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

Migrations run automatically on backend startup. Manual apply: `cd backend && alembic upgrade head`.

### Docker

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up --build
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000

### Tests

```bash
# Backend (243 tests)
cd backend && source .venv/bin/activate && pytest -v

# Frontend (60 tests)
cd frontend && npm test
```

## Configuration

Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env`.

### Backend environment variables

| Variable | Description |
|----------|-------------|
| `DEVIN_API_KEY` | Devin service user API key (`cog_...`) |
| `DEVIN_ORG_ID` | Organization ID |
| `DEVIN_API_BASE_URL` | Default: `https://api.devin.ai/v3` |
| `DEVIN_LIVE_ENABLED` | `false` by default — safe mode; no live Devin API calls |
| `GITHUB_TOKEN` | GitHub PAT for Orchestrator → GitHub REST. Requires `issues:write` and `pull_requests:read`. |
| `GITHUB_WEBHOOK_SECRET` | Secret for verifying GitHub → Orchestrator webhook signatures |
| `GITHUB_SCAN_REPOSITORIES` | Comma-separated repos to scan (e.g. `owner/repo`) |
| `REMEDIATE_LABEL` | Label for webhook and manual scan (default: `devin-remediate`) |
| `SCHEDULED_LABEL` | Label for scheduled intake only (default: `devin-scheduled`) |
| `DATABASE_URL` | Default: `sqlite:///./data/app.db` |
| `MAX_ACTIVE_SESSIONS` | Concurrency limit (default: 3) |
| `MAX_RETRIES` | Max retries before escalation (default: 3) |
| `MAX_CI_REPAIR_ATTEMPTS` | Max same-session Devin CI repairs (default: 2) |
| `MAX_CI_NON_CODE_FAILURES` | Non-code CI failures before escalation (default: 3) |
| `DEVIN_SESSION_TIMEOUT_MINUTES` | Session timeout (default: 60) |
| `DEVIN_SESSION_POLL_INTERVAL_SECONDS` | Devin session poll interval (default: 15; `0` disables poller) |
| `DEVIN_POLL_MAX_FAILURES` | Consecutive poll failures before escalation (default: 10) |
| `MAX_ACU_PER_TASK` | Per-task ACU cap passed to Devin as `max_acu_limit` (optional) |
| `DAILY_ACU_CAP` | Daily ACU cap — best-effort only when consumption data is unavailable |
| `DEVIN_REMEDIATION_PLAYBOOK_ID` | Optional Devin playbook ID for remediation sessions |
| `DEVIN_SCHEDULED_ENABLED` | Enable native Devin automation registration (`false` by default) |
| `DEVIN_SCHEDULE_CRON` | Cron expression for scheduled intake (default: `0 9 * * 1-5`) |
| `DEVIN_AUTOMATION_ID` | Existing automation ID (`auto-...`) for idempotent updates (optional) |
| `ORCHESTRATOR_PUBLIC_URL` | Public URL for scheduled intake callback |
| `SCHEDULED_INTAKE_TOKEN` | Bearer token for `POST /api/scheduled/intake` (required when public URL or scheduling enabled) |
| `CORS_ORIGINS` | Comma-separated origins |
| `LOG_LEVEL` | Logging level |

### Frontend environment variables

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | Backend URL (default: `http://localhost:8000`) |

Never put secrets in `VITE_*` variables.

### Required Devin permissions

| Capability | Permission |
|------------|------------|
| Sessions | `UseDevinSessions` (`org.devins.use`) |
| Consumption / analytics | `ViewOrgConsumption` (Enterprise) |
| Schedules / automations | `ManageOrgSchedules` |

### Scheduled intake

When `DEVIN_SCHEDULED_ENABLED=true` and `DEVIN_LIVE_ENABLED=true`:

```env
DEVIN_SCHEDULED_ENABLED=false
DEVIN_SCHEDULE_CRON=0 9 * * 1-5
ORCHESTRATOR_PUBLIC_URL=https://your-orchestrator.example.com
SCHEDULED_INTAKE_TOKEN=required-when-public-url-or-scheduling-enabled
DEVIN_AUTOMATION_ID=auto-optional-existing-automation-id
```

## API reference

Base URL: `http://localhost:8000`. Interactive OpenAPI: `/docs`.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `GET` | `/api/tasks` | Paginated task list with filters |
| `GET` | `/api/tasks/{id}` | Single task |
| `POST` | `/api/tasks/refresh` | Manual Devin sync + session insights |
| `POST` | `/api/remediations` | Manual remediation trigger |
| `POST` | `/api/scan/github` | Backfill labeled issues |
| `POST` | `/api/scheduled/intake` | Scheduled intake (bearer auth) |
| `GET` | `/api/metrics` | Task and org metrics |
| `POST` | `/webhooks/github` | GitHub event receiver |

### `GET /api/tasks` query parameters

| Param | Default | Description |
|-------|---------|-------------|
| `limit` | 25 | Page size (1–500) |
| `offset` | 0 | Pagination offset |
| `include_smoke_tests` | `false` | Include `task_kind=smoke_test` tasks |
| `status` | — | Filter by workflow status |
| `trigger_source` | — | `github_webhook`, `manual_api`, `scan`, `scheduled` |
| `search` | — | Free-text search (max 200 chars) |
| `sort_by` | `created_at` | `created_at`, `merged_at`, `status`, `repository`, `issue_number`, `issue_title`, `trigger_source` |
| `sort_order` | `desc` | `asc` or `desc` |

### `POST /api/remediations` outcomes

| Outcome | Meaning |
|---------|---------|
| `created` | New task created |
| `skipped` | Not processed (e.g. capacity limited) |
| `duplicate_issue_trigger` | Issue already has a task |
| `existing_active` | Active task already exists |
| `existing_devin_session` | Session already attached |
| `already_remediated` | Issue already remediated |
| `existing_terminal` | Terminal task exists |

**Safe mode** (`DEVIN_LIVE_ENABLED=false`): task persisted as `RECEIVED`; no Devin call.

**Live mode** (`DEVIN_LIVE_ENABLED=true`): creates a Devin V3 session; response includes `devin_session_id` and status `RUNNING`.

## GitHub webhook setup

1. In repository settings, add a webhook:
   - **Payload URL:** `https://<your-host>/webhooks/github`
   - **Content type:** `application/json`
   - **Secret:** same value as `GITHUB_WEBHOOK_SECRET`
   - **Events:** Issues, Pull requests, **Check runs**

2. Add the `devin-remediate` label to an issue to trigger remediation.

### Tunnel setup (ngrok / Cloudflare)

1. Start backend on `localhost:8000`
2. Start tunnel: `ngrok http 8000`
3. Configure webhook Payload URL: `https://<tunnel>/webhooks/github`
4. Set `DEVIN_LIVE_ENABLED=false` initially and verify task creation without Devin
5. Enable `DEVIN_LIVE_ENABLED=true` for a new issue to create a real Devin session
6. After Devin opens a PR, merge webhooks update the same task to `MERGED`

## Manual triggers

### Scan labeled issues (backfill)

Dashboard **Scan labeled issues** button or:

```bash
curl -X POST http://localhost:8000/api/scan/github
```

Requires `GITHUB_TOKEN` and `GITHUB_SCAN_REPOSITORIES`.

### Manual remediation

```bash
curl -X POST http://localhost:8000/api/remediations \
  -H "Content-Type: application/json" \
  -d '{
    "repository": "owner/repo",
    "issue_number": 1,
    "issue_url": "https://github.com/owner/repo/issues/1",
    "issue_type": "mcp-backend"
  }'
```

## Monitoring

### Dashboard

- Metrics cards: merge rate, MTTR, CI recovery, verified ACU
- Throughput chart and Devin org metrics section
- Task table with pagination, filtering, sorting, expandable rows
- Structured result, CI metadata, and session insights panels
- **Scan labeled issues** and **Refresh** (Devin sync) actions
- Auto-refresh every 15 seconds

### Metrics (`GET /api/metrics`)

All business metrics exclude `task_kind=smoke_test` tasks.

| Metric | Definition |
|--------|------------|
| Success Rate | `(MERGED + COMPLETED) / terminal production remediations` |
| Merge Rate | `MERGED production remediations / all production remediation tasks` |
| Median MTTR | `median(merged_at - started_at)` for `MERGED` production remediations only |
| Throughput | Production remediation tasks created in last 7 days |
| CI Recovery Rate | Tasks with `ci_repair_verified_at` / tasks with `ci_failure_at` |
| Verified ACU | Sum of `acu_used` where `acu_verified=true` only |
| Devin Org Metrics | From Devin analytics API; org-wide, not comparable to task metrics |
| Active Sessions | Production remediations in `SESSION_CREATED`, `RUNNING`, `PR_OPENED` |

### What to watch during a live run

| Signal | Where |
|--------|-------|
| Task created | Dashboard task table, `GET /api/tasks` |
| Devin session active | `devin_status`, `devin_session_url` on task |
| PR opened | `pr_url`, `status=PR_OPENED` |
| CI failure classified | `failure_type`, `ci_classification_reason` |
| CI repair sent | `ci_repair_attempts`, `ci_repair_message_sent_at` |
| CI passed (first run) | `ci_passed_at` from successful `check_run` webhook |
| CI repair verified | `ci_repair_verified_at` (requires subsequent successful check_run) |
| Resolved without PR | `status=COMPLETED`, `completion_reason` from Devin structured output |
| Merge confirmed | `status=MERGED`, `merged_at` from GitHub webhook |
| ACU finalized | `acu_verified=true`, `acu_source=consumption_api` |

## Local webhook simulation

### Issue labeled

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

### PR merged

```bash
SECRET="test-webhook-secret"
BODY='{"action":"closed","number":123,"pull_request":{"number":123,"html_url":"https://github.com/owner/superset/pull/123","state":"closed","merged":true,"merged_at":"2026-03-13T12:00:00Z","head":{"sha":"abc123"}},"repository":{"full_name":"owner/superset"}}'
SIG="sha256=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')"

curl -X POST http://localhost:8000/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -H "X-GitHub-Delivery: pr-delivery-001" \
  -H "X-Hub-Signature-256: $SIG" \
  -d "$BODY"
```

### Check run failure

```bash
SECRET="test-webhook-secret"
BODY=$(cat backend/tests/fixtures/check_run_failure.json)
SIG="sha256=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')"

curl -X POST http://localhost:8000/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: check_run" \
  -H "X-GitHub-Delivery: check-run-delivery-001" \
  -H "X-Hub-Signature-256: $SIG" \
  -d "$BODY"
```

Fixtures under `backend/tests/fixtures/check_run_*.json` cover cancelled, timeout, infra, success, and unknown scenarios.

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Webhook returns 401 | HMAC mismatch | Verify `GITHUB_WEBHOOK_SECRET` matches GitHub webhook secret |
| Task stays `RECEIVED` | Safe mode or capacity limit | Check `DEVIN_LIVE_ENABLED`; check `failure_reason=capacity_limited` |
| No Devin session created | Missing credentials or live mode off | Set `DEVIN_API_KEY`, `DEVIN_ORG_ID`, `DEVIN_LIVE_ENABLED=true` |
| PR webhook ignored | Task has no matching PR URL yet | Wait for Devin poller to persist `pr_url`; re-deliver webhook if needed |
| CI repair not triggered | Non-code failure or no session | Check `failure_type`; verify `devin_session_id` exists |
| `ci_repair_verified_at` not set | No subsequent successful check_run | Wait for CI rerun; verify Check runs webhook subscribed |
| Merge not reflected | PR webhook not received or `merged=false` | Confirm `pull_request` event with `merged=true` delivered |
| Post-merge issue not closed | `GITHUB_TOKEN` missing or lacks `issues:write` | Check backend logs; `MERGED` status is preserved regardless |
| CI stays RUNNING after green CI | `check_run` webhook missed or arrived before `pr_url` | Click **Refresh** (backfills `ci_passed_at` from GitHub); or redeliver success `check_run` webhook |
| Task stays RUNNING after Devin done | `devin_status=running` + `finished` not yet synced | Click **Refresh**; task should move to `COMPLETED` when structured output is `success` |
| Metrics show 0% merge rate | No merged tasks yet | Expected on fresh install; see [validation.md](validation.md) |
| ACU shows `0.0 (reported)` | Consumption API unavailable | Enterprise `ViewOrgConsumption` required for verified ACU |

### Known limitations

- `DEVIN_LIVE_ENABLED` defaults to `false` to prevent accidental ACU spend
- CI repair success requires a subsequent successful `check_run` webhook
- `check_run` association requires `pull_requests[0]` in the webhook payload
- Post-merge comment/close failures are logged, not auto-retried
- Automatic PR merge is not implemented
- `DAILY_ACU_CAP` is best-effort when consumption data is unavailable
