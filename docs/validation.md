# Validation

Real remediation evidence — what to verify after a live run and what counts as proof that the orchestrator worked end-to-end.

Related docs: [architecture.md](architecture.md) · [operations.md](operations.md)

## Scope

This document covers **production validation** with `DEVIN_LIVE_ENABLED=true` against real GitHub and Devin. Local webhook simulation and automated tests prove handler correctness but are not remediation evidence.

## Prerequisites

Before starting a validation run:

- [ ] Backend exposed via public URL (tunnel or deployed host)
- [ ] GitHub webhook configured: Issues, Pull requests, Check runs
- [ ] `GITHUB_WEBHOOK_SECRET`, `GITHUB_TOKEN`, `DEVIN_API_KEY`, `DEVIN_ORG_ID` set
- [ ] `DEVIN_LIVE_ENABLED=true`
- [ ] Target repo connected to Devin's GitHub integration
- [ ] Test issue created (real bug or intentional small fix)

## End-to-end validation checklist

### 1. Issue intake

**Action:** Add `devin-remediate` label to the test issue.

**Evidence required:**

| Artifact | Where to verify |
|----------|-----------------|
| Webhook delivered | GitHub webhook delivery log shows `200` |
| Task created | Dashboard task row with `trigger_source=github_webhook` |
| Status `RECEIVED` → `SESSION_CREATED` | Task `status` transitions within poll interval |
| Issue dedup works | Re-labeling same issue does not create duplicate task |

```bash
curl http://localhost:8000/api/tasks?search=<issue_number>
```

### 2. Devin session

**Evidence required:**

| Artifact | Where to verify |
|----------|-----------------|
| Session created | `devin_session_id`, `devin_session_url` populated |
| Playbook attached | `playbook_id` matches `DEVIN_REMEDIATION_PLAYBOOK_ID` (if configured) |
| Tags present | `devin_tags` includes `workflow=issue-remediation`, `source=github`, `repo=...`, `issue=...` |
| Structured output requested | Devin session UI shows `structured_output_schema` |
| Status `RUNNING` | `devin_status=running` during active work |

### 3. Pull request

**Evidence required:**

| Artifact | Where to verify |
|----------|-----------------|
| PR opened by Devin | `pr_url` populated, `status=PR_OPENED` |
| GitHub PR exists | PR link opens real PR on GitHub |
| PR webhook processed | `pr_state=open` from GitHub webhook (not poll-only) |
| Structured output | `remediation_outcome`, `root_cause`, `implementation_summary` in expandable row |

Structured output is Devin's engineering report. It does **not** prove merge — only GitHub does.

### 4. CI failure and repair (if applicable)

Skip if CI passes on first run. To validate CI repair, use an issue that produces a fix requiring a CI iteration.

**Evidence required:**

| Artifact | Where to verify |
|----------|-----------------|
| `check_run` webhook received | Backend logs; `failure_type` set on task |
| Classification correct | `ci_classification_reason` matches failure type |
| Same-session repair | `ci_repair_attempts` incremented; **no new** `devin_session_id` |
| Repair message sent | `ci_repair_message_sent_at` populated |
| Repair verified | `ci_repair_verified_at` set after subsequent successful `check_run` |

**Does not count as repair success:**

- `send_message` returning 200 without a later successful `check_run`
- Manually fixing CI outside Devin
- Creating a new Devin session for the same issue

### 5. Merge and closure

**Action:** Merge the Devin PR on GitHub.

**Evidence required:**

| Artifact | Where to verify |
|----------|-----------------|
| `status=MERGED` | From GitHub `pull_request` webhook (`merged=true`) |
| `merged_at` timestamp | Matches GitHub merge time |
| Issue commented | Comment on originating issue (requires `GITHUB_TOKEN`) |
| Issue closed | Originating issue closed on GitHub |
| MTTR recorded | `mttr_seconds` = `merged_at - started_at` on task |

### 6. Consumption and insights

**Evidence required:**

| Artifact | Where to verify |
|----------|-----------------|
| ACU synced | `acu_used` populated; `acu_verified=true` when Consumption API available |
| ACU source | `acu_source=consumption_api` (verified) or `session_detail` (reported only) |
| Session insights | `session_size`, `insights_status=completed`, `insights_json` after refresh |
| Metrics updated | `GET /api/metrics` shows merge rate > 0, median MTTR populated |

```bash
curl http://localhost:8000/api/metrics
curl -X POST http://localhost:8000/api/tasks/refresh
```

### 7. Scheduled intake (optional)

**Action:** Enable `DEVIN_SCHEDULED_ENABLED=true`, label a separate issue `devin-scheduled`.

**Evidence required:**

| Artifact | Where to verify |
|----------|-----------------|
| Automation registered | Devin UI shows automation with `schedule:recurring` trigger |
| Intake called | Task with `trigger_source=scheduled` |
| Dedup respected | Re-running intake skips existing issues |
| Remediate label unaffected | `devin-remediate` issues still use webhook path |

## Evidence summary template

Record one row per validation run:

```
Date:           YYYY-MM-DD
Repository:     owner/repo
Issue:          #N — <title>
Issue URL:      https://github.com/owner/repo/issues/N
Task ID:        <orchestrator task id>
Devin Session:  <devin_session_url>
PR:             <pr_url>
Merged:         yes/no — <merged_at>
CI repair:      yes/no — attempts: N, verified: yes/no
ACU:            <value> (<acu_source>, verified: yes/no)
Outcome:        success / blocked / failed / escalated
Notes:          <any blockers or anomalies>
```

## What counts as valid remediation evidence

| Valid | Invalid |
|-------|---------|
| GitHub-verified `MERGED` with `merged_at` | Structured output `outcome=success` without merge |
| Real PR with commits from Devin session | Task `status=PR_OPENED` with no GitHub PR |
| `ci_repair_verified_at` after successful check_run | `ci_repair_message_sent_at` alone |
| `acu_verified=true` from Consumption API | Session-reported `0.0 ACU` with no consumption sync |
| Webhook delivery `200` in GitHub settings | Manually inserted DB rows |
| Dashboard + API fields match GitHub state | Screenshot of Devin UI only |

## Safe-mode smoke test

Before enabling live mode, validate webhook plumbing with `DEVIN_LIVE_ENABLED=false`:

1. Label issue → task created with `status=RECEIVED`
2. No `devin_session_id` populated
3. No ACU consumed
4. Webhook dedup returns `200` on duplicate delivery

This confirms intake and persistence but is **not** remediation evidence.
