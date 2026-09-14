import { describe, expect, it } from "vitest"
import {
  formatActiveUsersSummary,
  formatDistribution,
  formatOrgWindowLabel,
  formatOriginDistribution,
  formatSizeDistribution,
} from "./orgMetrics"

describe("formatDistribution", () => {
  it("drops empty buckets and sorts by count", () => {
    expect(formatDistribution({ a: 1, b: 6, c: 0 })).toBe("B 6 · A 1")
  })

  it("returns null when every bucket is empty", () => {
    expect(formatDistribution({ xs: 0, s: 0, m: 0 })).toBeNull()
  })

  it("returns null for an empty or missing record", () => {
    expect(formatDistribution({})).toBeNull()
    expect(formatDistribution(null)).toBeNull()
    expect(formatDistribution(undefined)).toBeNull()
  })
})

describe("formatOriginDistribution", () => {
  it("uses readable origin labels", () => {
    expect(
      formatOriginDistribution({
        api: 6,
        webapp: 1,
        automation: 1,
        slack: 0,
        code_scan: 0,
      }),
    ).toBe("API 6 · Webapp 1 · Automation 1")
  })
})

describe("formatSizeDistribution", () => {
  it("uppercases size buckets", () => {
    expect(formatSizeDistribution({ xs: 8, s: 0, m: 0, l: 0, xl: 0 })).toBe("XS 8")
  })
})

describe("formatActiveUsersSummary", () => {
  it("reports window total alongside peaks", () => {
    expect(formatActiveUsersSummary(1, 1, 2, 3)).toBe(
      "1 in window · peak 1 daily / 2 weekly / 3 monthly",
    )
  })
})

describe("formatOrgWindowLabel", () => {
  it("describes the window length", () => {
    expect(formatOrgWindowLabel(30)).toBe("last 30 days")
  })
})
