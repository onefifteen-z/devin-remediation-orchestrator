import type { Task, TaskStatus } from "@/types/task"

export type FailureType =
  | "CODE_FAILURE"
  | "INFRA_FAILURE"
  | "TRANSIENT_FAILURE"
  | "UNKNOWN"

export type CiSummaryState = "running" | "passed" | "failed" | "unknown"

const CI_PENDING_STATUSES: TaskStatus[] = ["PR_OPENED", "READY_FOR_REVIEW"]

export function formatCiConclusion(conclusion: string | null): string {
  if (!conclusion) return "UNKNOWN"
  return conclusion.toUpperCase()
}

export function hasOpenPr(task: Task): boolean {
  if (!task.pr_url) return false
  if (task.pr_state?.toLowerCase() === "closed") return false
  return true
}

export function hasCiFailure(task: Task): boolean {
  if (task.status === "CI_FAILED") return true
  if (task.ci_failure_at && !task.ci_repair_verified_at) return true
  return false
}

export function getCiSummaryState(task: Task): CiSummaryState {
  if (hasCiFailure(task)) return "failed"
  if (
    task.status === "MERGED" ||
    task.ci_passed_at ||
    task.ci_repair_verified_at
  ) {
    return "passed"
  }
  if (
    hasOpenPr(task) &&
    !hasCiFailure(task) &&
    CI_PENDING_STATUSES.includes(task.status)
  ) {
    return "running"
  }
  return "unknown"
}

export function formatCiSummaryLabel(state: CiSummaryState): string {
  switch (state) {
    case "running":
      return "RUNNING"
    case "passed":
      return "PASS"
    case "failed":
      return "FAIL"
    default:
      return "UNKNOWN"
  }
}

export function getValidationLabel(task: Task): string {
  switch (getCiSummaryState(task)) {
    case "running":
      return "Waiting for CI"
    case "passed":
      return "CI passed"
    case "failed":
      return "CI failed"
    default:
      return "Not run"
  }
}

function isAggregateCheckName(checkName: string): boolean {
  const lower = checkName.toLowerCase()
  return lower.endsWith("-required") || lower.endsWith("_required")
}

export function getDisplayFailureType(task: Task): string | null {
  if (!task.failure_type) return null
  const conclusion = task.ci_conclusion?.toLowerCase()
  if (
    task.ci_check_name &&
    isAggregateCheckName(task.ci_check_name) &&
    task.failure_type === "TRANSIENT_FAILURE" &&
    conclusion === "cancelled"
  ) {
    return "TRANSIENT_FAILURE"
  }
  return task.failure_type
}

export function formatCiRepairStatus(
  failureType: string | null,
  repairAttempts: number,
  maxRepairAttempts: number,
  repairMessageSentAt: string | null,
  repairVerifiedAt: string | null,
): string {
  const displayType = failureType
  if (displayType && displayType !== "CODE_FAILURE") {
    return "No repair"
  }
  if (repairVerifiedAt) {
    return `Repair ${repairAttempts}/${maxRepairAttempts} verified`
  }
  if (repairMessageSentAt) {
    return `Repair ${repairAttempts}/${maxRepairAttempts}`
  }
  if (repairAttempts > 0) {
    return `Repair ${repairAttempts}/${maxRepairAttempts}`
  }
  return "No repair"
}

export function formatCiFailureDetail(task: Task): string[] {
  if (!task.ci_check_name || !hasCiFailure(task)) return []

  const lines: string[] = []
  const displayType = getDisplayFailureType(task)
  const repairStatus = formatCiRepairStatus(
    displayType,
    task.ci_repair_attempts,
    task.max_ci_repair_attempts,
    task.ci_repair_message_sent_at,
    task.ci_repair_verified_at,
  )

  lines.push(
    [
      task.ci_check_name,
      formatCiConclusion(task.ci_conclusion),
      displayType ?? "UNKNOWN",
      repairStatus,
    ].join(" · "),
  )

  if (
    task.ci_check_name &&
    isAggregateCheckName(task.ci_check_name) &&
    task.failure_type === "TRANSIENT_FAILURE" &&
    task.ci_conclusion?.toLowerCase() === "cancelled"
  ) {
    lines.push("Aggregate check — likely downstream of an underlying failure")
  }

  return lines
}

export function formatCiRepairLine(
  checkName: string | null,
  conclusion: string | null,
  failureType: string | null,
  repairAttempts: number,
  maxRepairAttempts: number,
  repairMessageSentAt: string | null = null,
  repairVerifiedAt: string | null = null,
  classificationReason: string | null = null,
): string | null {
  if (!checkName) return null
  const parts = [
    checkName,
    formatCiConclusion(conclusion),
    failureType ?? "UNKNOWN",
    formatCiRepairStatus(
      failureType,
      repairAttempts,
      maxRepairAttempts,
      repairMessageSentAt,
      repairVerifiedAt,
    ),
  ]
  if (classificationReason) {
    parts.push(classificationReason)
  }
  return parts.join(" · ")
}
