import { describe, expect, it } from "vitest"
import {
  buildTaskListQuery,
  getNextSortParams,
  isSmokeTestTask,
  totalPages,
} from "@/lib/taskList"
import type { Task } from "@/types/task"

const baseTask: Task = {
  id: 1,
  github_delivery_id: "delivery-1",
  github_repository: "owner/repo",
  github_issue_number: 1,
  github_issue_url: "https://github.com/owner/repo/issues/1",
  issue_title: "Bug",
  issue_type: "bug",
  task_kind: "remediation",
  trigger_source: "github_webhook",
  devin_session_id: null,
  devin_session_url: null,
  devin_status: null,
  devin_status_detail: null,
  devin_origin: null,
  devin_service_user_id: null,
  devin_tags: null,
  status: "RECEIVED",
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

describe("taskList helpers", () => {
  it("detects smoke tests by task_kind or dummy issue_type", () => {
    expect(isSmokeTestTask({ ...baseTask, task_kind: "smoke_test" })).toBe(true)
    expect(isSmokeTestTask({ ...baseTask, issue_type: "dummy" })).toBe(true)
    expect(isSmokeTestTask(baseTask)).toBe(false)
  })

  it("builds query string with smoke-test and pagination params", () => {
    expect(
      buildTaskListQuery({
        limit: 25,
        offset: 50,
        include_smoke_tests: true,
        status: "MERGED",
        search: "helm",
        sort_by: "merged_at",
        sort_order: "asc",
      }),
    ).toBe(
      "?limit=25&offset=50&include_smoke_tests=true&status=MERGED&search=helm&sort_by=merged_at&sort_order=asc",
    )
  })

  it("computes total pages", () => {
    expect(totalPages(0, 25)).toBe(1)
    expect(totalPages(26, 25)).toBe(2)
  })

  it("toggles sort order on repeated header clicks", () => {
    expect(
      getNextSortParams({ sort_by: "created_at", sort_order: "desc" }, "created_at"),
    ).toEqual({ sort_by: "created_at", sort_order: "asc", offset: 0 })

    expect(
      getNextSortParams({ sort_by: "status", sort_order: "asc" }, "created_at"),
    ).toEqual({ sort_by: "created_at", sort_order: "desc", offset: 0 })
  })
})
