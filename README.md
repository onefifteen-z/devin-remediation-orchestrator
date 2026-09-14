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

## GitHub Event-Driven Workflow

```
Issue
  → devin-remediate label
  → signed webhook (issues/labeled)
  → Orchestrator
  → Devin V3 session
  → PR created
  → signed webhook (pull_request)
  → GitHub lifecycle updates
  → Merge verified
  → Metrics (merge rate, MTTR)
```

Phase 1 implements webhook ingestion and task persistence. Phase 2A adds `POST /api/remediations`. Phase 2B adds Devin session polling and PR detection. Phase 2C makes GitHub the authoritative source for PR/merge lifecycle state.

### Three distinct trust relationships

| Credential | Direction | Purpose |
|------------|-----------|---------|
| `GITHUB_WEBHOOK_SECRET` | GitHub → Orchestrator | Verifies webhook authenticity (HMAC-SHA256) |
| `GITHUB_TOKEN` | Orchestrator → GitHub | REST API: issue comments, issue close, PR fetch |
| Devin GitHub integration | Devin → GitHub | Devin's connected repo access for engineering work |

These are separate credentials with separate trust boundaries. Never expose any of them to the frontend.

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
make migrate    # apply Alembic migrations to head
make up         # docker compose up --build
make down       # docker compose down
```

### Database migrations

Schema changes are managed with [Alembic](https://alembic.sqlalchemy.org/) under `backend/alembic/`.

```bash
cd backend
alembic upgrade head          # apply pending migrations
alembic revision -m "message" # create a new migration (autogenerate: add --autogenerate)
```

Migrations run automatically when the backend starts. A database created before
Alembic was introduced is detected, stamped at the `0001` baseline, and upgraded
without deleting its existing data.

## Backend Environment Variables

| Variable | Description |
|----------|-------------|
| `DEVIN_API_KEY` | Devin service user API key (`cog_...`) |
| `DEVIN_ORG_ID` | Organization ID |
| `DEVIN_API_BASE_URL` | Default: `https://api.devin.ai/v3` |
| `DEVIN_LIVE_ENABLED` | `false` by default (safe mode — no live Devin API calls) |
| `GITHUB_TOKEN` | GitHub PAT for Orchestrator → GitHub REST (issue comment/close, PR fetch, manual scan). Requires `issues:write` for comment/close; `pull_requests:read` for PR fetch. |
| `GITHUB_WEBHOOK_SECRET` | Secret for verifying GitHub → Orchestrator webhook signatures |
| `GITHUB_SCAN_REPOSITORIES` | Comma-separated repos to scan (e.g. `owner/superset`) |
| `REMEDIATE_LABEL` | Label for webhook and manual scan (default: `devin-remediate`) |
| `SCHEDULED_LABEL` | Label for scheduled intake only (default: `devin-scheduled`) |
| `DATABASE_URL` | Default: `sqlite:///./data/app.db` |
| `MAX_ACTIVE_SESSIONS` | Concurrency limit (default: 3) |
| `MAX_RETRIES` | Max retries before escalation (default: 3) |
| `MAX_CI_REPAIR_ATTEMPTS` | Max same-session Devin CI repairs (default: 2) |
| `MAX_CI_NON_CODE_FAILURES` | Non-code CI failures before escalation (default: 3) |
| `DEVIN_SESSION_TIMEOUT_MINUTES` | Session timeout (default: 60) |
| `DEVIN_SESSION_POLL_INTERVAL_SECONDS` | Devin session poll interval in seconds (default: 15; `0` disables poller) |
| `DEVIN_POLL_MAX_FAILURES` | Consecutive poll failures before escalation (default: 10) |
| `MAX_ACU_PER_TASK` | Per-task ACU cap (optional) |
| `DAILY_ACU_CAP` | Daily ACU cap (optional) |
| `DEVIN_REMEDIATION_PLAYBOOK_ID` | Optional Devin playbook ID for remediation sessions |
| `DEVIN_SCHEDULED_ENABLED` | Enable native Devin schedule registration (`false` by default) |
| `DEVIN_SCHEDULE_CRON` | Cron expression for scheduled intake (default: `0 9 * * 1-5`) |
| `DEVIN_AUTOMATION_ID` | Existing automation ID (`auto-...` from Devin API) for idempotent updates (optional; auto-discovered via metadata when unset) |
| `DEVIN_SCHEDULE_ID` | Legacy schedules API ID (deprecated; use `DEVIN_AUTOMATION_ID` instead) |
| `ORCHESTRATOR_PUBLIC_URL` | Public URL for scheduled intake callback (required when scheduling enabled) |
| `SCHEDULED_INTAKE_TOKEN` | Bearer token for `POST /api/scheduled/intake` (required when `ORCHESTRATOR_PUBLIC_URL` or `DEVIN_SCHEDULED_ENABLED` is set) |
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
   - **Events:** Issues, Pull requests

2. Add the `devin-remediate` label to an issue to trigger remediation.

For real GitHub.com integration via tunnel (ngrok / Cloudflare Tunnel):

1. Start backend on `localhost:8000`
2. Start tunnel: `ngrok http 8000` (or equivalent)
3. Configure webhook Payload URL: `https://<tunnel>/webhooks/github`
4. Set `DEVIN_LIVE_ENABLED=false` initially and verify task creation without Devin
5. Enable `DEVIN_LIVE_ENABLED=true` for a new issue to create a real Devin session
6. After Devin opens a PR, merge webhooks update the same task to `MERGED`

## Manual Issue Scan (Backfill)

For existing open issues that already have the `devin-remediate` label, use the dashboard **Scan labeled issues** button or call:

```bash
curl -X POST http://localhost:8000/api/scan/github
```

Requirements:

- `GITHUB_TOKEN` must be configured
- `GITHUB_SCAN_REPOSITORIES` must list target repos (e.g. `owner/superset`)

Deduplication uses `(github_repository, github_issue_number)` as the business unique key. If an issue already has a task, it is skipped (`skip_if_any`).

## Manual Remediation API

Trigger a remediation task directly via the API (synchronous — the response includes session details when live mode is enabled):

```bash
curl -X POST http://localhost:8000/api/remediations \
  -H "Content-Type: application/json" \
  -d '{
    "repository": "onefifteen-z/superset",
    "issue_number": 1,
    "issue_url": "https://github.com/onefifteen-z/superset/issues/1",
    "issue_type": "mcp-backend"
  }'
```

**Safe mode (`DEVIN_LIVE_ENABLED=false`, default):** The task is persisted with status `RECEIVED`. No Devin API call is made and no ACUs are consumed. The response includes `devin_live_enabled: false` and a message indicating live execution is disabled.

**Live mode (`DEVIN_LIVE_ENABLED=true`):** A real Devin V3 session is created. The response includes `devin_session_id`, `devin_session_url`, and status `RUNNING`. This consumes ACUs — only enable when you intend to run a real remediation.

Requirements for live mode:

- `DEVIN_API_KEY` and `DEVIN_ORG_ID` must be configured
- Set `DEVIN_LIVE_ENABLED=true` in `backend/.env`

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

### Simulate a PR merge webhook locally

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

A matching remediation task (same repo + PR URL) must exist for PR webhooks to update lifecycle state.

### Simulate a check_run webhook locally

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

A matching remediation task (same repo + PR number) must exist. Other fixtures under `backend/tests/fixtures/check_run_*.json` cover cancelled, timeout, infra, success, and unknown scenarios.

## CI Failure Intelligence

**Design principle:** We invoke Devin only when CI evidence suggests autonomous engineering action is warranted. CI failure does not always mean code failure.

When GitHub CI fails on a Devin-opened PR, the orchestrator:

1. Receives a signed `check_run` webhook (`status=completed`, failure-like conclusion)
2. Normalizes the payload into `CiCheckRunEvent`
3. Associates the check with an existing remediation task via `check_run.pull_requests[0].number`
4. Classifies the failure deterministically (no LLM)
5. Persists CI metadata on the task (workflow `status` stays `PR_OPENED` / `READY_FOR_REVIEW`)
6. Applies policy based on classification

### Classification types

| Type | When | Devin invoked? |
|------|------|----------------|
| `CODE_FAILURE` | `failure` + strong code/test signals (pytest, lint, build, etc.) | Yes — same session |
| `TRANSIENT_FAILURE` | `cancelled`, `timed_out`, `stale` (takes precedence over check name) | No |
| `INFRA_FAILURE` | `startup_failure` or strong infrastructure signals | No |
| `UNKNOWN` | Insufficient evidence (e.g. bare `failure`, `action_required`) | No |

Example: **Python Unit Tests + `cancelled`** (tests passed but workflow cancelled) → `TRANSIENT_FAILURE`, not `CODE_FAILURE`.

### Same-session repair

For `CODE_FAILURE` only, when `DEVIN_LIVE_ENABLED=true` and `task.devin_session_id` exists:

- Sends `POST /v3/organizations/{org_id}/sessions/{devin_id}/messages` to the **existing** session
- Never creates a new Devin session for CI repair
- Bounded by `MAX_CI_REPAIR_ATTEMPTS` (default **2**)
- Exceeding the limit → `ESCALATED`

Non-code failures are recorded and observed. After `MAX_CI_NON_CODE_FAILURES` (default **3**) repeated non-code failures, the task escalates without invoking Devin.

### CI metadata on tasks

Stored separately from workflow status: `failure_type`, `ci_check_name`, `ci_conclusion`, `ci_classification_reason`, `ci_repair_attempts`, `last_ci_check_run_id`, `ci_repair_verified_at`.

### Example CI failure lifecycle

```
Issue labeled → Devin session → PR opened → CI fails (pytest)
  → CODE_FAILURE classified → send_message(same session)
  → Devin fixes PR → CI reruns → check_run success
  → ci_repair_verified_at set (repair success requires GitHub evidence)
```

### Real GitHub validation

1. Subscribe the repo webhook to **Check runs** (in addition to Issues and Pull requests)
2. Expose the backend via ngrok or Cloudflare tunnel
3. Trigger a real CI failure on a Devin PR
4. Confirm classification, metadata persistence, and same-session repair in logs/dashboard

Do not manufacture fake production failures if a real one is not available — local fixtures are sufficient for automated tests.

## Task Lifecycle

| Status | Meaning |
|--------|---------|
| `RECEIVED` | Webhook accepted, task persisted |
| `SESSION_CREATED` | Devin session created |
| `RUNNING` | Devin actively working |
| `PR_OPENED` | Pull request created |
| `CI_FAILED` | Legacy enum value; Phase 3 uses CI metadata fields instead |
| `READY_FOR_REVIEW` | Devin finished, PR awaiting human review |
| `MERGED` | PR merged |
| `FAILED` | Unrecoverable failure |
| `ESCALATED` | Retries/timeout/ACU cap exceeded |

## Observability Metrics

The dashboard and `GET /api/metrics` expose:

- Success rate, merge rate
- Median MTTR (merged tasks only)
- 7-day throughput
- CI recovery rate, tasks with CI failures, repair attempts/successes
- CI failure breakdown (code / transient / infra / unknown)
- Total / average ACU
- Tasks with PRs
- Active, failed, escalated task counts

All metrics are computed from real database state—empty when no tasks exist. Merge rate and median MTTR update when GitHub-verified `MERGED` tasks exist (via `pull_request` webhook with `merged=true`).

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
- Webhook deduplication via `X-GitHub-Delivery` and `check_run.id`
- `MAX_CI_REPAIR_ATTEMPTS` (default 2) for same-session CI repair
- `MAX_CI_NON_CODE_FAILURES` (default 3) before escalation on infra/transient/unknown

## Phase 1 Status

**Implemented:**

- Repository structure and configuration
- FastAPI application with health, tasks, metrics, webhook endpoints
- SQLite persistence with audit trail
- GitHub webhook HMAC verification and event filtering
- Webhook deduplication and issue-level dedup (`repo + issue_number`)
- Manual scan API and dashboard button for backfilling labeled issues
- Devin V3 client abstraction (HTTP layer, mockable)
- GitHub client skeleton
- Prompt builder and orchestration service
- Background task dispatch (gated live Devin calls)
- React operations dashboard
- Docker setup and tests

## Phase 2A Status

**Implemented:**

- `POST /api/remediations` — manual remediation entry point
- Synchronous orchestration: task creation → prompt building → Devin V3 session (when live)
- Status lifecycle: `RECEIVED` → `SESSION_CREATED` → `RUNNING`
- Devin session metadata persisted (`devin_session_id`, `devin_session_url`)
- Feature flag gating (`DEVIN_LIVE_ENABLED=false` by default)
- Orchestrator and API tests with mocked Devin responses

## Phase 2B Status

**Session lifecycle tracking — implemented:**

- `DevinClient.get_session()` — typed V3 session detail response with full error handling
- Background `SessionPoller` — polls active tasks every `DEVIN_SESSION_POLL_INTERVAL_SECONDS` (default 15)
- Devin fields consumed: `status`, `status_detail`, `origin`, `service_user_id`, `tags`, `pull_requests`, `acus_consumed`, `structured_output`
- Raw Devin execution state persisted on every poll (`devin_status`, `devin_status_detail`, etc.)
- Dual-dimension model: `status` = workflow progress; `devin_status` / `devin_status_detail` = agent execution state
- PR detection from Devin session response (`pr_url`, `pr_state`); first PR wins when multiple exist
- ACU tracking from `acus_consumed` on every poll
- Task status updates based on real Devin data (no fake transitions)
- Dashboard shows workflow status and Devin execution detail separately
- Live dashboard refresh every 15 seconds via TanStack Query

**Workflow mapping (Devin → `status`):**

| Devin `status` | `status_detail` | PR | Workflow `status` |
|----------------|-----------------|----|-------------------|
| `new`, `claimed` | — | no | `SESSION_CREATED` |
| `new`, `claimed` | — | yes | `PR_OPENED` |
| `running`, `resuming` | any | no | `RUNNING` |
| `running`, `resuming` | any | yes | `PR_OPENED` |
| `suspended` | `usage_limit_exceeded`, `out_of_credits` | no | `ESCALATED` |
| `suspended` | `usage_limit_exceeded`, `out_of_credits` | yes | `PR_OPENED` |
| `suspended` | other | any | no change |
| `error` | — | no | `FAILED` |
| `error` | — | yes | `PR_OPENED` |
| `exit` | — | yes | `READY_FOR_REVIEW` |
| `exit` | — | no | `FAILED` (or `ESCALATED` if blocked) |
| unknown | — | — | no change (logged) |

`status_detail` values (`working`, `waiting_for_user`, `waiting_for_approval`, etc.) are stored as-is and shown in the Dashboard Devin column; they do not add new workflow enum values.

- Transient poll errors preserve task state; repeated failures escalate after `DEVIN_POLL_MAX_FAILURES`

## Phase 2C Status (Current)

**GitHub event-driven lifecycle — implemented:**

- `issues` / `labeled` / `devin-remediate` webhook trigger (async dispatch)
- `pull_request` webhook support: `opened`, `reopened`, `synchronize`, `closed`
- HMAC-SHA256 verification with constant-time comparison
- Webhook delivery deduplication via `github_webhook_deliveries` table
- Normalized `RemediationEvent` and `PullRequestEvent` domain events
- PR → task association using an already-persisted exact PR URL or repository + PR number
- GitHub-authoritative `pr_state`, merge detection (`merged=true` only)
- `MERGED` transition with GitHub `merged_at` timestamp
- Post-merge issue comment and issue close via `GITHUB_TOKEN` (async, failure-safe)
- Merge rate and median MTTR metrics from verified `MERGED` tasks
- Dashboard shows Merged At column

**Status authority:**

| Dimension | Source | Examples |
|-----------|--------|----------|
| Workflow `status` | Orchestrator business logic | `RUNNING`, `PR_OPENED`, `MERGED` |
| Devin execution | Devin V3 session poll | `running`, `exit`, `suspended` |
| GitHub PR state | GitHub `pull_request` webhooks | `open`, `closed`, `merged` |

**Not yet implemented (Phase 4+):**

- Automatic PR merge

## Phase 5 Status — Advanced Devin Integration

**Implemented:**

- Structured output schema on session create (`structured_output_schema`, `structured_output_required`)
- Typed `RemediationResult` parsing and persistence (`remediation_outcome`, `root_cause`, `implementation_summary`, `blocker`, `structured_result_json`)
- Playbook support via `DEVIN_REMEDIATION_PLAYBOOK_ID` (optional; prompt-only fallback when unset)
- Standardized Devin session tags (`workflow`, `source`, `repo`, `issue`, `issue-type`, `environment`)
- Session consumption API integration (`GET /organizations/{org_id}/consumption/daily/sessions/{session_id}`)
- ACU source semantics (`acu_source`, `acu_verified`) with final consumption sync on terminal session / merge
- Organization analytics (`GET /organizations/{org_id}/consumption/daily`) exposed via metrics API
- Scheduled Devin intake via native Automations API (`schedule:recurring` trigger; `DEVIN_SCHEDULED_ENABLED=false` by default)
- Dashboard expandable structured result rows and verified ACU display

### Advanced Devin Integration

#### Structured Output

Remediation sessions request a conservative JSON Schema (Draft 7) with:

- `outcome`: `success` | `blocked` | `failed`
- `root_cause`, `implementation_summary`, `tests_performed[]`, `residual_risks[]`, `blocker`, `pr_url`

Structured output represents Devin's engineering report. It does **not** override GitHub-authoritative merge state. A task becomes `MERGED` only from GitHub merge evidence.

#### Playbook

Create a remediation playbook in Devin UI (Settings → Playbooks) covering the stable engineering process: inspect, reproduce, root cause, fix, tests, lint, regressions, PR, structured result, blockers.

Set `DEVIN_REMEDIATION_PLAYBOOK_ID` to reference it. When unset, the orchestrator uses the existing prompt-based remediation flow.

#### Tags

Every session includes tags such as `workflow=issue-remediation`, `source=github|api|scan|scheduled`, `repo=...`, `issue=...`. Task `trigger_source` remains authoritative.

#### Consumption API

Session-reported `acus_consumed` may be `0.0` even for substantial work. The orchestrator prefers the Consumption API when available:

| `acu_source` | Meaning |
|--------------|---------|
| `session_detail` | From `acus_consumed` on session GET (unverified) |
| `consumption_api` | From `GET .../consumption/daily/sessions/{session_id}` (verified) |
| `unavailable` | Consumption API not accessible (e.g. missing permission) |

Dashboard shows `3.2 ACU` (verified), `0.0 ACU (reported)` (session only), or `—` (unavailable).

#### Analytics / Metrics

Local DB remains authoritative for merge rate and MTTR. Devin org consumption supplements usage metrics when `ViewOrgConsumption` is available (Enterprise).

#### Scheduled Devin

When `DEVIN_SCHEDULED_ENABLED=true` and `DEVIN_LIVE_ENABLED=true`, the orchestrator registers a native Devin automation with a `schedule:recurring` trigger. Each run starts a Devin session that calls `POST /api/scheduled/intake` to scan issues labeled `devin-scheduled` (configurable via `SCHEDULED_LABEL`) using the same idempotent orchestration path. Webhook and manual scan continue to use `devin-remediate`.

Required configuration:

```env
DEVIN_SCHEDULED_ENABLED=false
DEVIN_SCHEDULE_CRON=0 9 * * 1-5
ORCHESTRATOR_PUBLIC_URL=https://your-orchestrator.example.com
SCHEDULED_INTAKE_TOKEN=required-when-public-url-or-scheduling-enabled
DEVIN_AUTOMATION_ID=auto-optional-existing-automation-id
```

## Phase 6 Status — Production Hardening & Dashboard Polish

**Implemented:**

- Authoritative `trigger_source` on tasks (`github_webhook`, `manual_api`, `scan`, `scheduled`); dashboard Source uses this, not `devin_origin`
- Explicit `task_kind` (`remediation` | `smoke_test`) with migration `0007`; smoke tests excluded from business metrics
- Issue-level idempotency across all trigger paths with structured duplicate logs
- Final `create_session` guard when `devin_session_id` already exists
- `SCHEDULED_INTAKE_TOKEN` required when `ORCHESTRATOR_PUBLIC_URL` or `DEVIN_SCHEDULED_ENABLED` is set (constant-time bearer validation)
- Honest leadership metrics: merge rate, MTTR, CI recovery, verified ACU only
- Dashboard attention banner, CI repair attempted vs verified, terminal task presentation, expanded audit rows

### Metric definitions

| Metric | Definition |
|--------|------------|
| **Merge rate** | `MERGED` production remediations / all production remediation tasks (`task_kind=remediation`) |
| **Median MTTR** | `median(merged_at - started_at)` for merged production remediations only |
| **CI recovery** | Tasks with `ci_repair_verified_at` / tasks with `ci_failure_at` (GitHub evidence required) |
| **Verified ACU** | Sum of `acu_used` where `acu_verified=true` only; unverified session-reported values are not mixed in |

### Safety controls

- `MAX_ACTIVE_SESSIONS`: enforced before session creation; capacity-limited tasks stay `RECEIVED` with `failure_reason=capacity_limited`
- `MAX_ACU_PER_TASK`: passed to Devin as `max_acu_limit` (hard per-session cap)
- `DAILY_ACU_CAP`: configured but not strictly enforced when consumption data is unavailable/unverified (best-effort guard only)

#### Required Devin Permissions

| Capability | Permission |
|------------|------------|
| Sessions | `UseDevinSessions` (`org.devins.use`) |
| Consumption / analytics | `ViewOrgConsumption` (Enterprise) |
| Schedules | `ManageOrgSchedules` |

#### Phase 4 Real-Validation Checklist (manual, post-merge)

1. Label issue `devin-remediate` → GitHub webhook → orchestrator
2. Verify session has playbook, tags, `structured_output_schema`
3. Devin produces PR + structured output
4. CI `check_run` → same-session repair if needed
5. Merge PR → task `MERGED` from GitHub webhook
6. Final consumption sync → dashboard shows verified/reported ACU
7. Dashboard expandable row shows structured result fields
8. (Separate) Enable `DEVIN_SCHEDULED_ENABLED` → verify schedule registered → intake creates only new tasks

## Phase 3 Status

**Implemented:**

- GitHub `check_run` webhook ingestion with HMAC verification and delivery deduplication
- `CiCheckRunEvent` normalization and deterministic failure classifier
- CI → PR → remediation task association
- CI metadata persistence on `remediation_tasks`
- Same-session Devin `send_message` for `CODE_FAILURE` only (background execution)
- Repair attempt tracking with `MAX_CI_REPAIR_ATTEMPTS`
- Escalation for max repair attempts and repeated non-code failures
- Dashboard CI metadata display
- Honest CI metrics (`ci_repair_successes` requires subsequent successful check_run)
- 37+ new tests (147 total backend tests)

**Previously listed as Phase 3 — now implemented:**

- CI `check_run` webhooks and failure classification
- Same-session `send_message` self-correction loop

## Known Limitations

- `DEVIN_LIVE_ENABLED` defaults to `false` to prevent accidental ACU spend
- A PR webhook received before Devin polling persists the task's PR URL is safely ignored
- Post-merge comment/close requires `GITHUB_TOKEN`; API failures are logged, not auto-retried
- CI repair success is verified only when a subsequent successful `check_run` webhook arrives
- `check_run` association requires `pull_requests[0]` in the webhook payload
- Database schema is managed with Alembic (`make migrate` or auto-run on backend startup)

## Future Extensions

- Jira / Linear / security scanner event sources
- Slack notifications
- Scheduled remediation jobs
- Multi-repository rollout
- Policy-based approval gates
- Customer-specific playbooks
