import { describe, expect, it } from "vitest"

import {
  formatAcuDisplay,
  formatDevinUsageKpi,
  formatTriggerSource,
  getActiveTriggerSources,
  getAttentionSummary,
  getDevinPresentationState,
  getDevinUsageNote,
  getRawDevinStateClarification,
  getRawDevinStateSnapshotNote,
  getTriggerSourceBadgeVariant,
  getTriggerSourceChartColor,
  hasExplicitBlocker,
  isDevinActivelyWorking,
} from "./devin"
import { makeTask } from "./testFixtures"

describe("Devin presentation states", () => {
  it("A1: maps active Devin session to Working", () => {
    const task = makeTask({
      status: "RUNNING",
      devin_status: "running",
      devin_status_detail: "working",
    })
    expect(getDevinPresentationState(task)).toMatchObject({
      state: "working",
      label: "Working",
    })
  })

  it("A2: maps open PR with pending CI to Waiting for CI", () => {
    const task = makeTask({
      status: "PR_OPENED",
      pr_url: "https://github.com/owner/repo/pull/17",
      pr_state: "open",
      devin_status: "running",
      devin_status_detail: "waiting_for_user",
    })
    expect(getDevinPresentationState(task)).toMatchObject({
      state: "waiting_for_ci",
      label: "Waiting for CI",
    })
  })

  it("maps open PR with passed CI to Waiting for review", () => {
    const task = makeTask({
      status: "PR_OPENED",
      pr_url: "https://github.com/owner/repo/pull/19",
      pr_state: "open",
      ci_passed_at: "2026-09-15T03:07:56Z",
      devin_status: "suspended",
      devin_status_detail: "inactivity",
    })
    expect(getDevinPresentationState(task)).toMatchObject({
      state: "waiting_for_review",
      label: "Waiting for review",
    })
  })

  it("A3: maps waiting_for_user without blocker to Waiting for input", () => {
    const task = makeTask({
      status: "RUNNING",
      devin_status: "running",
      devin_status_detail: "waiting_for_user",
    })
    expect(getDevinPresentationState(task)).toMatchObject({
      state: "waiting_for_input",
      label: "Waiting for input",
    })
  })

  it("A4: maps explicit blocker to Human action required", () => {
    const task = makeTask({
      status: "RUNNING",
      devin_status: "running",
      devin_status_detail: "waiting_for_user",
      blocker: "Needs credentials",
    })
    expect(getDevinPresentationState(task)).toMatchObject({
      state: "human_action_required",
      label: "Human action required",
    })
  })

  it("A5: maps MERGED + waiting_for_user to Completed", () => {
    const task = makeTask({
      status: "MERGED",
      devin_status: "running",
      devin_status_detail: "waiting_for_user",
    })
    expect(getDevinPresentationState(task)).toMatchObject({
      state: "completed",
      label: "Completed",
    })
  })

  it("A6: maps FAILED + waiting_for_user to Failed", () => {
    const task = makeTask({
      status: "FAILED",
      devin_status: "running",
      devin_status_detail: "waiting_for_user",
    })
    expect(getDevinPresentationState(task)).toMatchObject({
      state: "failed",
      label: "Failed",
    })
  })

  it("A7: maps ESCALATED + waiting_for_user to Escalated", () => {
    const task = makeTask({
      status: "ESCALATED",
      devin_status: "running",
      devin_status_detail: "waiting_for_user",
    })
    expect(getDevinPresentationState(task)).toMatchObject({
      state: "escalated",
      label: "Escalated",
    })
  })
})

describe("hasExplicitBlocker", () => {
  it("detects blocked outcome and blocker text", () => {
    expect(hasExplicitBlocker(makeTask({ remediation_outcome: "blocked" }))).toBe(true)
    expect(hasExplicitBlocker(makeTask({ blocker: "Missing API key" }))).toBe(true)
    expect(hasExplicitBlocker(makeTask({ devin_status_detail: "waiting_for_user" }))).toBe(
      false,
    )
  })
})

describe("formatTriggerSource", () => {
  it("C13: maps GITHUB_WEBHOOK to GitHub Webhook", () => {
    expect(formatTriggerSource("github_webhook")).toBe("GitHub Webhook")
  })

  it("C14: maps MANUAL_API to Manual API", () => {
    expect(formatTriggerSource("manual_api")).toBe("Manual API")
  })

  it("C15: maps SCAN to Scan", () => {
    expect(formatTriggerSource("scan")).toBe("Scan")
  })

  it("C16: maps SCHEDULED to Scheduled", () => {
    expect(formatTriggerSource("scheduled")).toBe("Scheduled")
  })

  it("C17: devin_origin does not change trigger source display", () => {
    const webhook = makeTask({ trigger_source: "github_webhook", devin_origin: "api" })
    const manual = makeTask({ trigger_source: "manual_api", devin_origin: "automation" })
    expect(formatTriggerSource(webhook.trigger_source)).toBe("GitHub Webhook")
    expect(formatTriggerSource(manual.trigger_source)).toBe("Manual API")
  })
})

describe("getTriggerSourceBadgeVariant", () => {
  it("gives each known source a distinct variant", () => {
    const variants = ["github_webhook", "scheduled", "manual_api", "scan"].map(
      getTriggerSourceBadgeVariant,
    )
    expect(new Set(variants).size).toBe(variants.length)
  })
})

describe("throughput chart helpers", () => {
  it("returns distinct colors for each trigger source", () => {
    const colors = ["github_webhook", "manual_api", "scan", "scheduled"].map(
      getTriggerSourceChartColor,
    )
    expect(new Set(colors).size).toBe(colors.length)
  })

  it("returns only sources with non-zero counts", () => {
    const active = getActiveTriggerSources([
      {
        by_source: {
          github_webhook: 2,
          manual_api: 0,
          scan: 1,
          scheduled: 0,
        },
      },
    ])
    expect(active).toEqual(["github_webhook", "scan"])
  })
})

describe("Devin usage", () => {
  it("F25: shows verified ACU with verified note", () => {
    expect(formatDevinUsageKpi(3.2)).toBe("3.2 ACU")
    expect(getDevinUsageNote(3.2, true)).toBe("Verified")
    expect(formatAcuDisplay(3.2, "consumption_api", true)).toBe("3.2 ACU · Verified")
  })

  it("F26: shows reported ACU when unverified", () => {
    expect(formatAcuDisplay(0.0, "session_detail", false)).toBe("0.0 ACU · Reported")
  })

  it("F27: shows unavailable usage as dash", () => {
    expect(formatAcuDisplay(0.0, "unavailable", false)).toBe("—")
    expect(formatDevinUsageKpi(0, false)).toBe("Not reported")
    expect(getDevinUsageNote(0, false)).toBe("Consumption API unavailable / not reported")
  })

  it("F28: zero verified usage does not imply zero real cost", () => {
    expect(formatDevinUsageKpi(0)).toBe("No verified usage")
    expect(getDevinUsageNote(0, true)).toBe(
      "Enterprise ACU reporting unavailable (self-serve/on-demand)",
    )
  })
})

describe("COMPLETED presentation", () => {
  it("shows resolved without PR for completed tasks", () => {
    const task = makeTask({
      status: "COMPLETED",
      completion_reason: "Issue already fixed in main branch",
      remediation_outcome: "success",
    })
    const presentation = getDevinPresentationState(task)
    expect(presentation.label).toBe("Resolved without PR")
    expect(presentation.sublabel).toBe("Issue already fixed in main branch")
  })

  it("stops showing working when structured outcome exists while running", () => {
    const task = makeTask({
      status: "RUNNING",
      devin_status: "running",
      devin_status_detail: "finished",
      remediation_outcome: "success",
    })
    expect(isDevinActivelyWorking(task)).toBe(false)
  })
})

describe("getAttentionSummary", () => {
  it("G29: waiting_for_user without blocker does not count as intervention", () => {
    const summary = getAttentionSummary([
      makeTask({
        id: 1,
        status: "RUNNING",
        devin_status_detail: "waiting_for_user",
      }),
    ])
    expect(summary.needsIntervention).toBe(0)
  })

  it("G30: terminal merged task does not count as needing intervention", () => {
    const summary = getAttentionSummary([
      makeTask({
        id: 1,
        status: "MERGED",
        devin_status_detail: "waiting_for_user",
      }),
      makeTask({
        id: 2,
        status: "RUNNING",
        blocker: "Needs review",
      }),
      makeTask({ id: 3, task_kind: "smoke_test", status: "FAILED" }),
    ])
    expect(summary.needsIntervention).toBe(1)
    expect(summary.failed).toBe(0)
  })
})

describe("raw Devin state notes", () => {
  it("explains last observed Devin state snapshot", () => {
    expect(getRawDevinStateSnapshotNote()).toContain("orchestrator poller")
  })

  it("clarifies merged tasks that still show waiting_for_user", () => {
    expect(getRawDevinStateClarification("MERGED", "waiting_for_user")).toContain("merged")
  })
})
