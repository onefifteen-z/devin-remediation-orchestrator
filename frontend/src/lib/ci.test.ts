import { describe, expect, it } from "vitest"

import { formatCiRepairLine } from "./ci"

describe("formatCiRepairLine", () => {
  it("shows no Devin repair for non-code failures", () => {
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
    ).toContain("No Devin repair")
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
    expect(attempted).toContain("Repair attempted")
    expect(verified).toContain("Repair verified")
  })
})
