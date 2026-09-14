import { describe, expect, it } from "vitest"
import {
  buildTaskListQuery,
  getDisplayIssueLabels,
  getNextSortParams,
  isSmokeTestTask,
  parseIssueLabels,
  totalPages,
} from "@/lib/taskList"
import { makeTask } from "@/lib/testFixtures"

describe("taskList helpers", () => {
  it("detects smoke tests by task_kind or dummy issue_type", () => {
    expect(isSmokeTestTask(makeTask({ task_kind: "smoke_test" }))).toBe(true)
    expect(isSmokeTestTask(makeTask({ issue_type: "dummy" }))).toBe(true)
    expect(isSmokeTestTask(makeTask())).toBe(false)
  })

  it("parses issue labels from the JSON text column", () => {
    expect(parseIssueLabels('["helm", "infrastructure"]')).toEqual(["helm", "infrastructure"])
  })

  it("E22: issue labels are visible after filtering orchestration labels", () => {
    expect(
      getDisplayIssueLabels('["bug", "helm", "devin-remediate", "infrastructure"]'),
    ).toEqual(["bug", "helm", "infrastructure"])
  })

  it("E23: orchestration labels do not dominate the main row", () => {
    expect(
      getDisplayIssueLabels('["devin-remediate", "devin-scheduled", "backend", "compatibility"]'),
    ).toEqual(["backend", "compatibility"])
  })

  it("E24: missing labels render safely", () => {
    expect(getDisplayIssueLabels(null)).toEqual([])
    expect(getDisplayIssueLabels("not-json")).toEqual([])
    expect(getDisplayIssueLabels("[]")).toEqual([])
  })

  it("caps displayed labels at three", () => {
    expect(
      getDisplayIssueLabels('["a", "b", "c", "d", "e"]', 3),
    ).toEqual(["a", "b", "c"])
  })

  it("builds query strings from list params", () => {
    expect(
      buildTaskListQuery({
        limit: 25,
        offset: 0,
        include_smoke_tests: false,
        sort_by: "created_at",
        sort_order: "desc",
      }),
    ).toBe("?limit=25&offset=0&sort_by=created_at&sort_order=desc")
  })

  it("toggles sort order for the same field", () => {
    expect(
      getNextSortParams({ sort_by: "created_at", sort_order: "desc" }, "created_at"),
    ).toEqual({ sort_by: "created_at", sort_order: "asc", offset: 0 })
  })

  it("computes total pages", () => {
    expect(totalPages(0, 25)).toBe(1)
    expect(totalPages(26, 25)).toBe(2)
  })
})
