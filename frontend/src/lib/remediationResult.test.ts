import { describe, expect, it } from "vitest"

import type { Task } from "@/types/task"
import {
  formatOutcomeLabel,
  getOutcomeBadgeVariant,
  getTestResultBadgeVariant,
  hasRemediationResult,
  parseRemediationResult,
} from "./remediationResult"

const baseTask: Task = {
  id: 1,
  github_delivery_id: "d1",
  github_repository: "owner/repo",
  github_issue_number: 1,
  github_issue_url: "https://github.com/owner/repo/issues/1",
  issue_title: "Issue",
  issue_type: "bug",
  task_kind: "remediation",
  trigger_source: "github_webhook",
  devin_session_id: "session-1",
  devin_session_url: "https://app.devin.ai/sessions/session-1",
  devin_status: "running",
  devin_status_detail: "waiting_for_user",
  devin_origin: "api",
  devin_service_user_id: null,
  devin_tags: "repo:owner/repo",
  status: "MERGED",
  pr_url: "https://github.com/owner/repo/pull/2",
  pr_state: "closed",
  retry_count: 0,
  max_retries: 3,
  started_at: "2026-01-01T00:00:00Z",
  completed_at: null,
  merged_at: "2026-01-01T01:00:00Z",
  failure_reason: null,
  escalation_reason: null,
  failure_type: null,
  ci_classification_reason: null,
  ci_check_name: null,
  ci_check_url: null,
  ci_conclusion: null,
  ci_failure_at: null,
  ci_repair_attempts: 0,
  max_ci_repair_attempts: 2,
  last_ci_check_run_id: null,
  ci_repair_message_sent_at: null,
  ci_repair_verified_at: null,
  ci_non_code_failure_count: 0,
  acu_used: 0,
  acu_source: "session_detail",
  acu_verified: false,
  session_size: null,
  num_user_messages: null,
  num_devin_messages: null,
  insights_status: null,
  insights_json: null,
  remediation_outcome: "success",
  root_cause: "Missing config key",
  implementation_summary: "Added fallback config loader",
  structured_result_json: JSON.stringify({
    outcome: "success",
    tests_performed: [
      { command: "pytest backend/tests", result: "passed" },
      { command: "npm test", result: "skipped" },
    ],
    residual_risks: ["Needs staging validation"],
  }),
  blocker: null,
  playbook_id: "playbook-123",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T01:00:00Z",
  mttr_seconds: 3600,
}

describe("remediation result helpers", () => {
  it("maps outcome labels and badge variants", () => {
    expect(formatOutcomeLabel("success")).toBe("SUCCESS")
    expect(formatOutcomeLabel("blocked")).toBe("BLOCKED")
    expect(getOutcomeBadgeVariant("success")).toBe("success")
    expect(getOutcomeBadgeVariant("failed")).toBe("destructive")
    expect(getOutcomeBadgeVariant("blocked")).toBe("warning")
  })

  it("maps test result badge variants", () => {
    expect(getTestResultBadgeVariant("passed")).toBe("success")
    expect(getTestResultBadgeVariant("failed")).toBe("destructive")
    expect(getTestResultBadgeVariant("skipped")).toBe("warning")
    expect(getTestResultBadgeVariant("not_run")).toBe("default")
  })

  it("parses remediation result from task fields and structured json", () => {
    const result = parseRemediationResult(baseTask)
    expect(result.outcome).toBe("success")
    expect(result.root_cause).toBe("Missing config key")
    expect(result.tests_performed).toHaveLength(2)
    expect(result.residual_risks).toEqual(["Needs staging validation"])
    expect(hasRemediationResult(baseTask)).toBe(true)
  })

  it("detects missing remediation result", () => {
    const emptyTask: Task = {
      ...baseTask,
      remediation_outcome: null,
      root_cause: null,
      implementation_summary: null,
      blocker: null,
      structured_result_json: null,
    }
    expect(hasRemediationResult(emptyTask)).toBe(false)
    expect(parseRemediationResult(emptyTask).tests_performed).toEqual([])
  })

  it("prefers persisted task fields over structured json duplicates", () => {
    const task: Task = {
      ...baseTask,
      root_cause: "Persisted root cause",
      structured_result_json: JSON.stringify({
        outcome: "failed",
        root_cause: "JSON root cause",
      }),
    }
    expect(parseRemediationResult(task).root_cause).toBe("Persisted root cause")
    expect(parseRemediationResult(task).outcome).toBe("success")
  })
})
