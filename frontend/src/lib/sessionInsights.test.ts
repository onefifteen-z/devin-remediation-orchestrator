import { describe, expect, it } from "vitest"

import type { Task } from "@/types/task"
import {
  formatActionItemType,
  formatClassificationCategory,
  formatInsightsStatusNote,
  formatMessageBreakdown,
  formatMessageTotal,
  formatSessionSize,
  getImpactBadgeVariant,
  hasSessionInsights,
  parseSessionInsights,
} from "./sessionInsights"

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
  devin_session_id: "session-1",
  devin_session_url: "https://app.devin.ai/sessions/session-1",
  devin_status: "suspended",
  devin_status_detail: "inactivity",
  devin_origin: "api",
  devin_service_user_id: null,
  devin_tags: null,
  status: "MERGED",
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
  updated_at: "2026-01-01T01:00:00Z",
  mttr_seconds: null,
}

const richInsightsJson = JSON.stringify({
  classification: {
    category: "feature_development",
    confidence: 0.95,
    programming_languages: ["YAML", "Python"],
    tools_and_frameworks: ["Helm"],
  },
  issues: [
    {
      id: "1",
      title: "Helm tooling not pre-installed",
      issue: "Devin installed helm manually.",
      impact: "low",
      label: "Environment issue",
    },
  ],
  timeline: [
    {
      title: "PR merged successfully",
      description: "Merged without user intervention.",
      color: "#34D399",
      issue_id: null,
    },
  ],
  action_items: [
    {
      action_item: "Pre-install helm in the blueprint.",
      type: "machine_setup",
      issue_id: "1",
    },
  ],
})

describe("session insights parsing", () => {
  it("parses the persisted analysis payload", () => {
    const insights = parseSessionInsights({ ...baseTask, insights_json: richInsightsJson })

    expect(insights.classification?.category).toBe("feature_development")
    expect(insights.timeline).toHaveLength(1)
    expect(insights.timeline[0].color).toBe("#34D399")
    expect(insights.issues[0].impact).toBe("low")
    expect(insights.action_items[0].type).toBe("machine_setup")
  })

  it("returns empty insights for missing or malformed json", () => {
    expect(parseSessionInsights(baseTask).timeline).toEqual([])
    expect(parseSessionInsights({ ...baseTask, insights_json: "{not json" }).issues).toEqual([])
  })

  it("detects presence of insights from scalar fields alone", () => {
    expect(hasSessionInsights(baseTask)).toBe(false)
    expect(hasSessionInsights({ ...baseTask, session_size: "xs" })).toBe(true)
    expect(hasSessionInsights({ ...baseTask, num_devin_messages: 3 })).toBe(true)
  })
})

describe("session insights formatting", () => {
  it("formats session size labels", () => {
    expect(formatSessionSize("xs")).toBe("XS")
    expect(formatSessionSize("l")).toBe("L")
    expect(formatSessionSize(null)).toBe("—")
  })

  it("formats message counts", () => {
    expect(formatMessageTotal(1, 3)).toBe("4 msgs")
    expect(formatMessageTotal(1, 0)).toBe("1 msg")
    expect(formatMessageTotal(null, null)).toBeNull()
    expect(formatMessageBreakdown(1, 3)).toBe("1 user · 3 Devin")
    expect(formatMessageBreakdown(null, null)).toBeNull()
  })

  it("formats classification with confidence", () => {
    expect(
      formatClassificationCategory({
        category: "feature_development",
        confidence: 0.95,
        programming_languages: [],
        tools_and_frameworks: [],
      }),
    ).toBe("feature development (95% confidence)")
    expect(formatClassificationCategory(null)).toBeNull()
  })

  it("maps issue impact to badge variants", () => {
    expect(getImpactBadgeVariant("high")).toBe("destructive")
    expect(getImpactBadgeVariant("medium")).toBe("warning")
    expect(getImpactBadgeVariant("low")).toBe("default")
  })

  it("formats action item types", () => {
    expect(formatActionItemType("machine_setup")).toBe("Machine Setup")
    expect(formatActionItemType("prompt_improvement")).toBe("Prompt")
    expect(formatActionItemType("unmapped_type")).toBe("unmapped type")
  })

  it("explains an empty completed analysis instead of showing nothing", () => {
    const empty = parseSessionInsights(baseTask)
    expect(formatInsightsStatusNote("completed", empty)).toBe(
      "Devin's analysis completed without flagging issues for this session.",
    )
    expect(formatInsightsStatusNote(null, empty)).toBeNull()
  })

  it("stays silent when findings exist", () => {
    const rich = parseSessionInsights({ ...baseTask, insights_json: richInsightsJson })
    expect(formatInsightsStatusNote("completed", rich)).toBeNull()
  })
})
