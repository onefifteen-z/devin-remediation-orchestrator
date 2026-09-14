import { describe, expect, it } from "vitest"

import {
  buildTestsPerformedRows,
  formatOutcomeLabel,
  formatTestDisplay,
  parseRemediationResult,
} from "./remediationResult"
import { makeTask } from "./testFixtures"

describe("structured output presentation", () => {
  it("B8: outcome success is displayed correctly", () => {
    const task = makeTask({ remediation_outcome: "success" })
    expect(formatOutcomeLabel(parseRemediationResult(task).outcome)).toBe("SUCCESS")
  })

  it("B9: pre-fix expected failure does not look like remediation failure", () => {
    const row = formatTestDisplay(
      {
        command: "pytest -k legacy (with fix stashed)",
        result: "failed",
        category: "pre_fix_reproduction",
      },
      0,
    )
    expect(row.statusText).toBe("Expected failure")
    expect(row.variant).toBe("success")
  })

  it("B10: post-fix regression pass is displayed as passed", () => {
    const row = formatTestDisplay(
      {
        command: "pytest tests/regression",
        result: "passed",
        category: "regression_test",
      },
      0,
    )
    expect(row.label).toBe("Regression test")
    expect(row.statusText).toBe("Passed")
  })

  it("B11: CI not run is displayed as not run/waiting", () => {
    const task = makeTask({ status: "RUNNING" })
    const rows = buildTestsPerformedRows(task)
    expect(rows).toEqual([])
  })

  it("B12: malformed optional structured fields render safely", () => {
    const task = makeTask({
      structured_result_json: "{not-json",
      remediation_outcome: null,
    })
    const result = parseRemediationResult(task)
    expect(result.tests_performed).toEqual([])
    expect(result.residual_risks).toEqual([])
    expect(result.outcome).toBeNull()
  })
})

describe("buildTestsPerformedRows", () => {
  it("adds GitHub CI row when PR exists", () => {
    const task = makeTask({
      status: "PR_OPENED",
      pr_url: "https://github.com/owner/repo/pull/17",
      pr_state: "open",
      structured_result_json: JSON.stringify({
        tests_performed: [
          {
            command: "pytest",
            result: "passed",
            category: "post_fix_validation",
          },
        ],
      }),
    })
    const rows = buildTestsPerformedRows(task)
    expect(rows).toHaveLength(2)
    expect(rows[1].label).toBe("GitHub CI")
    expect(rows[1].statusText).toBe("Waiting")
  })
})
