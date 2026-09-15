import { describe, expect, it } from "vitest"

import {
  formatCiFailureDetail,
  formatCiRepairLine,
  formatCiSummaryLabel,
  getCiSummaryState,
  getDisplayFailureType,
  getValidationLabel,
  hasCiFailure,
} from "./ci"
import { makeTask } from "./testFixtures"

describe("getCiSummaryState", () => {
  it("D18: CI running is not a failure", () => {
    const task = makeTask({
      status: "PR_OPENED",
      pr_url: "https://github.com/owner/repo/pull/17",
      pr_state: "open",
    })
    expect(getCiSummaryState(task)).toBe("running")
    expect(formatCiSummaryLabel(getCiSummaryState(task))).toBe("RUNNING")
    expect(getValidationLabel(task)).toBe("Waiting for CI")
    expect(hasCiFailure(task)).toBe(false)
  })

  it("D19: CI success is reported as passed", () => {
    const task = makeTask({
      status: "MERGED",
      pr_url: "https://github.com/owner/repo/pull/2",
      merged_at: "2026-01-02T00:00:00Z",
    })
    expect(getCiSummaryState(task)).toBe("passed")
    expect(getValidationLabel(task)).toBe("CI passed")
  })

  it("reports passed when ci_passed_at is set on an open PR", () => {
    const task = makeTask({
      status: "PR_OPENED",
      pr_url: "https://github.com/owner/repo/pull/17",
      pr_state: "open",
      ci_passed_at: "2026-01-02T00:00:00Z",
    })
    expect(getCiSummaryState(task)).toBe("passed")
    expect(getValidationLabel(task)).toBe("CI passed")
  })

  it("D20: CI failure shows classification in detail", () => {
    const task = makeTask({
      status: "CI_FAILED",
      pr_url: "https://github.com/owner/repo/pull/16",
      ci_check_name: "Python Unit Tests",
      ci_conclusion: "failure",
      failure_type: "CODE_FAILURE",
      ci_failure_at: "2026-01-01T01:00:00Z",
      ci_repair_attempts: 1,
    })
    expect(getCiSummaryState(task)).toBe("failed")
    const lines = formatCiFailureDetail(task)
    expect(lines[0]).toContain("Python Unit Tests")
    expect(lines[0]).toContain("CODE_FAILURE")
    expect(lines[0]).toContain("Repair 1/2")
  })

  it("D21: aggregate required failure is softened for cancelled transient checks", () => {
    const task = makeTask({
      status: "CI_FAILED",
      ci_check_name: "unit-tests-required",
      ci_conclusion: "cancelled",
      failure_type: "TRANSIENT_FAILURE",
      ci_failure_at: "2026-01-01T01:00:00Z",
    })
    expect(getDisplayFailureType(task)).toBe("TRANSIENT_FAILURE")
    const lines = formatCiFailureDetail(task)
    expect(lines.some((line) => line.includes("Aggregate check"))).toBe(true)
  })
})

describe("formatCiRepairLine", () => {
  it("shows no repair for non-code failures", () => {
    expect(
      formatCiRepairLine(
        "Python Unit Tests",
        "cancelled",
        "TRANSIENT_FAILURE",
        0,
        2,
        null,
        null,
      ),
    ).toContain("No repair")
  })

  it("distinguishes repair attempted from verified", () => {
    const attempted = formatCiRepairLine(
      "Python Unit Tests",
      "failure",
      "CODE_FAILURE",
      1,
      2,
      "2026-01-01T00:00:00Z",
      null,
    )
    const verified = formatCiRepairLine(
      "Python Unit Tests",
      "failure",
      "CODE_FAILURE",
      1,
      2,
      "2026-01-01T00:00:00Z",
      "2026-01-01T01:00:00Z",
    )
    expect(attempted).toContain("Repair 1/2")
    expect(verified).toContain("verified")
  })
})
