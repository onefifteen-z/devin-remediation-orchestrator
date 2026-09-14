import { describe, expect, it } from "vitest"

import type { Task } from "@/types/task"
import {
  formatAcuDisplay,
  formatDevinExecutionForTask,
  formatTriggerSource,
  formatVerifiedAcuTotal,
  getAttentionSummary,
  getDevinAlertForTask,
  getRawDevinStateClarification,
  getRawDevinStateSnapshotNote,
  getTriggerSourceBadgeVariant,
  getVerifiedAcuNote,
} from "./devin"

describe("formatAcuDisplay", () => {
  it("shows verified ACU with verified suffix", () => {
    expect(formatAcuDisplay(3.2, "consumption_api", true)).toBe("3.2 ACU · Verified")
  })

  it("shows reported ACU when unverified", () => {
    expect(formatAcuDisplay(0.0, "session_detail", false)).toBe("0.0 ACU · Reported")
  })

  it("shows dash when consumption unavailable", () => {
    expect(formatAcuDisplay(0.0, "unavailable", false)).toBe("—")
  })
})

describe("formatVerifiedAcuTotal", () => {
  it("shows empty state when no verified usage", () => {
    expect(formatVerifiedAcuTotal(0)).toBe("No API usage available")
  })
})

describe("getVerifiedAcuNote", () => {
  it("explains the Enterprise requirement when the total is zero", () => {
    expect(getVerifiedAcuNote(0, true)).toBe("Enterprise ACU reporting unavailable")
  })

  it("reports an outright API failure ahead of the plan note", () => {
    expect(getVerifiedAcuNote(0, false)).toBe("Consumption API unavailable")
  })

  it("describes the metric once there is verified usage", () => {
    expect(getVerifiedAcuNote(3.2, true)).toBe("Sum of consumption-verified task ACU only")
  })
})

describe("formatTriggerSource", () => {
  it("maps trigger sources to readable labels", () => {
    expect(formatTriggerSource("github_webhook")).toBe("GitHub Webhook")
    expect(formatTriggerSource("manual_api")).toBe("Manual API")
    expect(formatTriggerSource("scan")).toBe("Scan")
    expect(formatTriggerSource("scheduled")).toBe("Scheduled")
  })
})

describe("getTriggerSourceBadgeVariant", () => {
  it("gives each known source a distinct variant", () => {
    const variants = ["github_webhook", "scheduled", "manual_api", "scan"].map(
      getTriggerSourceBadgeVariant,
    )
    expect(new Set(variants).size).toBe(variants.length)
  })

  it("falls back to the neutral variant for unknown or missing sources", () => {
    expect(getTriggerSourceBadgeVariant(null)).toBe("default")
    expect(getTriggerSourceBadgeVariant("something_new")).toBe("default")
  })
})

describe("terminal task Devin presentation", () => {
  it("does not show human action required for MERGED + waiting_for_user", () => {
    expect(
      getDevinAlertForTask("MERGED", "running", "waiting_for_user"),
    ).toBeNull()
    expect(
      formatDevinExecutionForTask("MERGED", "running", "waiting_for_user"),
    ).toBe("Completed")
  })

  it("shows human action required for RUNNING + waiting_for_user", () => {
    expect(
      getDevinAlertForTask("RUNNING", "running", "waiting_for_user"),
    ).toBe("Human action required")
  })

  it("normalizes FAILED and ESCALATED terminal labels", () => {
    expect(formatDevinExecutionForTask("FAILED", "error", "user_request")).toBe("Failed")
    expect(formatDevinExecutionForTask("ESCALATED", "suspended", "usage_limit_exceeded")).toBe(
      "Escalated",
    )
  })
})

describe("raw Devin state snapshot notes", () => {
  it("shows snapshot note for terminal tasks only", () => {
    expect(getRawDevinStateSnapshotNote("MERGED")).toBe(
      "Session snapshot (last sync before or at terminal state)",
    )
    expect(getRawDevinStateSnapshotNote("RUNNING")).toBeNull()
  })

  it("clarifies merged tasks that still show waiting_for_user", () => {
    expect(getRawDevinStateClarification("MERGED", "waiting_for_user")).toBe(
      "Business outcome: merged — session may have ended after last sync",
    )
    expect(getRawDevinStateClarification("MERGED", "finished")).toBeNull()
    expect(getRawDevinStateClarification("RUNNING", "waiting_for_user")).toBeNull()
  })
})

describe("getAttentionSummary", () => {
  const baseTask: Task = {
    id: 1,
    github_delivery_id: "d1",
    github_repository: "owner/repo",
    github_issue_number: 1,
    github_issue_url: "https://github.com/owner/repo/issues/1",
    issue_title: "Issue",
    issue_type: "bug",
    issue_labels: null,
    task_kind: "remediation",
    trigger_source: "github_webhook",
    devin_session_id: null,
    devin_session_url: null,
    devin_status: null,
    devin_status_detail: null,
    devin_origin: null,
    devin_service_user_id: null,
    devin_tags: null,
    status: "RUNNING",
    pr_url: null,
    pr_state: null,
    retry_count: 0,
    max_retries: 3,
    started_at: null,
    completed_at: null,
    merged_at: null,
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
    acu_used: null,
    acu_source: null,
    acu_verified: false,
    session_size: null,
    num_user_messages: null,
    num_devin_messages: null,
    insights_status: null,
    insights_json: null,
    remediation_outcome: null,
    root_cause: null,
    implementation_summary: null,
    structured_result_json: null,
    blocker: null,
    playbook_id: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    mttr_seconds: null,
  }

  it("excludes smoke tests and terminal merged false positives", () => {
    const summary = getAttentionSummary([
      { ...baseTask, id: 1, status: "MERGED", devin_status_detail: "waiting_for_user" },
      { ...baseTask, id: 2, status: "RUNNING", devin_status_detail: "waiting_for_user" },
      { ...baseTask, id: 3, task_kind: "smoke_test", status: "FAILED" },
    ])
    expect(summary.needsHuman).toBe(1)
    expect(summary.failed).toBe(0)
  })
})
