import { describe, expect, it } from "vitest"

import {
  formatDevinExecutionForTask,
  formatTriggerSource,
  getDevinAlertForTask,
} from "./devin"

describe("formatTriggerSource", () => {
  it("maps github_webhook to a readable label", () => {
    expect(formatTriggerSource("github_webhook")).toBe("GitHub Webhook")
  })
})

describe("terminal task Devin presentation", () => {
  it("does not show human action required for MERGED + waiting_for_user", () => {
    expect(
      getDevinAlertForTask("MERGED", "running", "waiting_for_user"),
    ).toBeNull()
    expect(
      formatDevinExecutionForTask("MERGED", "running", "waiting_for_user"),
    ).toBe("completed")
  })

  it("shows human action required for RUNNING + waiting_for_user", () => {
    expect(
      getDevinAlertForTask("RUNNING", "running", "waiting_for_user"),
    ).toBe("Human action required")
  })

  it("normalizes MERGED + suspended to completed", () => {
    expect(
      formatDevinExecutionForTask("MERGED", "suspended", "inactivity"),
    ).toBe("completed")
  })
})
