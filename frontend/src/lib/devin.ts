import { isSmokeTestTask } from "@/lib/taskList"
import type { Task, TaskStatus } from "@/types/task"

const STATUS_DETAIL_LABELS: Record<string, string> = {
  usage_limit_exceeded: "usage limit exceeded",
  out_of_credits: "out of credits",
  user_request: "user request",
  inactivity: "inactivity",
  working: "working",
  waiting_for_user: "waiting for user",
  waiting_for_approval: "waiting for approval",
  finished: "finished",
}

const ORIGIN_LABELS: Record<string, string> = {
  api: "API",
  automation: "Automation",
  code_scan: "Code Scan",
}

const TRIGGER_SOURCE_LABELS: Record<string, string> = {
  github_webhook: "GitHub Webhook",
  manual_api: "Manual API",
  scan: "Scan",
  scheduled: "Scheduled",
}

const TERMINAL_TASK_STATUSES: TaskStatus[] = ["MERGED", "FAILED", "ESCALATED"]

export function formatDevinStatusDetail(detail: string | null | undefined): string | null {
  if (!detail) return null
  return STATUS_DETAIL_LABELS[detail] ?? detail.replaceAll("_", " ")
}

export function formatDevinExecution(
  devinStatus: string | null | undefined,
  devinStatusDetail: string | null | undefined,
): string {
  if (!devinStatus) return "—"
  const detailLabel = formatDevinStatusDetail(devinStatusDetail)
  return detailLabel ? `${devinStatus} · ${detailLabel}` : devinStatus
}

export function formatTaskSource(
  devinOrigin: string | null | undefined,
): string {
  if (!devinOrigin) return "—"
  return ORIGIN_LABELS[devinOrigin] ?? devinOrigin
}

export function formatTriggerSource(
  triggerSource: string | null | undefined,
): string {
  if (!triggerSource) return "Unknown"
  return TRIGGER_SOURCE_LABELS[triggerSource] ?? triggerSource.replaceAll("_", " ")
}

/**
 * Distinct hues only so multiple sources are scannable in one pass; the
 * variants carry no severity meaning.
 */
export function getTriggerSourceBadgeVariant(
  triggerSource: string | null | undefined,
): "default" | "info" | "success" | "warning" {
  switch (triggerSource) {
    case "github_webhook":
      return "info"
    case "scheduled":
      return "success"
    case "manual_api":
      return "warning"
    default:
      return "default"
  }
}

export function formatDevinExecutionForTask(
  taskStatus: TaskStatus,
  devinStatus: string | null | undefined,
  devinStatusDetail: string | null | undefined,
): string {
  if (TERMINAL_TASK_STATUSES.includes(taskStatus)) {
    if (taskStatus === "MERGED") return "Completed"
    if (taskStatus === "FAILED") return "Failed"
    return "Escalated"
  }
  return formatDevinExecution(devinStatus, devinStatusDetail)
}

export function formatRawDevinState(
  devinStatus: string | null | undefined,
  devinStatusDetail: string | null | undefined,
): string | null {
  if (!devinStatus) return null
  return formatDevinExecution(devinStatus, devinStatusDetail)
}

export function getDevinAlert(
  devinStatus: string | null | undefined,
  devinStatusDetail: string | null | undefined,
): string | null {
  const detail = devinStatusDetail?.toLowerCase()
  if (detail === "waiting_for_user" || detail === "waiting_for_approval") {
    return "Human action required"
  }
  if (devinStatus?.toLowerCase() === "error") {
    return "Devin session error"
  }
  if (
    devinStatus?.toLowerCase() === "suspended" &&
    (detail === "usage_limit_exceeded" || detail === "out_of_credits")
  ) {
    return "Usage limit exceeded"
  }
  return null
}

export function getDevinAlertForTask(
  taskStatus: TaskStatus,
  devinStatus: string | null | undefined,
  devinStatusDetail: string | null | undefined,
): string | null {
  if (TERMINAL_TASK_STATUSES.includes(taskStatus)) {
    return null
  }
  return getDevinAlert(devinStatus, devinStatusDetail)
}

export function getAttentionSummary(tasks: Task[]): {
  escalated: number
  failed: number
  needsHuman: number
} {
  let escalated = 0
  let failed = 0
  let needsHuman = 0

  for (const task of tasks) {
    if (isSmokeTestTask(task)) continue
    if (task.status === "ESCALATED") escalated += 1
    if (task.status === "FAILED") failed += 1
    if (getDevinAlertForTask(task.status, task.devin_status, task.devin_status_detail)) {
      needsHuman += 1
    }
  }

  return { escalated, failed, needsHuman }
}

export function formatPrState(prState: string | null | undefined): string | null {
  if (!prState) return null
  return prState.charAt(0).toUpperCase() + prState.slice(1)
}

export function extractPrNumber(prUrl: string): string | null {
  const match = prUrl.match(/\/pull\/(\d+)/)
  return match ? `#${match[1]}` : null
}

export const terminalTaskStatuses = TERMINAL_TASK_STATUSES

export function getRawDevinStateSnapshotNote(taskStatus: TaskStatus): string | null {
  if (!TERMINAL_TASK_STATUSES.includes(taskStatus)) {
    return null
  }
  return "Session snapshot (last sync before or at terminal state)"
}

export function getRawDevinStateClarification(
  taskStatus: TaskStatus,
  devinStatusDetail: string | null | undefined,
): string | null {
  if (
    taskStatus === "MERGED" &&
    devinStatusDetail?.toLowerCase() === "waiting_for_user"
  ) {
    return "Business outcome: merged — session may have ended after last sync"
  }
  return null
}

export function formatAcuDisplay(
  acuUsed: number | null | undefined,
  acuSource: string | null | undefined,
  acuVerified: boolean | undefined,
): string {
  if (acuSource === "unavailable") {
    return "—"
  }
  if (acuUsed == null) {
    return "—"
  }
  if (acuVerified) {
    return `${acuUsed.toFixed(1)} ACU · Verified`
  }
  return `${acuUsed.toFixed(1)} ACU · Reported`
}

export function formatVerifiedAcuTotal(verifiedTotalAcu: number): string {
  if (verifiedTotalAcu <= 0) {
    return "No API usage available"
  }
  return verifiedTotalAcu.toFixed(1)
}

/**
 * A zero total is expected rather than exceptional here: self-serve orgs are
 * billed in on-demand USD and only Enterprise plans report ACU over the API,
 * so the consumption endpoints return an empty ledger with a 200.
 */
export function getVerifiedAcuNote(
  verifiedTotalAcu: number,
  consumptionApiAvailable: boolean | null,
): string {
  if (consumptionApiAvailable === false) {
    return "Consumption API unavailable"
  }
  if (verifiedTotalAcu <= 0) {
    return "Enterprise ACU reporting unavailable"
  }
  return "Sum of consumption-verified task ACU only"
}

export function parseStructuredResult(
  structuredResultJson: string | null | undefined,
): {
  tests_performed: { command: string; result: string }[]
  residual_risks: string[]
} {
  if (!structuredResultJson) {
    return { tests_performed: [], residual_risks: [] }
  }
  try {
    const parsed = JSON.parse(structuredResultJson) as {
      tests_performed?: { command: string; result: string }[]
      residual_risks?: string[]
    }
    return {
      tests_performed: parsed.tests_performed ?? [],
      residual_risks: parsed.residual_risks ?? [],
    }
  } catch {
    return { tests_performed: [], residual_risks: [] }
  }
}
