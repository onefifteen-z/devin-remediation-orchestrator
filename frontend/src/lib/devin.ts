import { getCiSummaryState, hasOpenPr } from "@/lib/ci"
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
  unknown: "Unknown",
}

export const TRIGGER_SOURCE_CHART_ORDER = [
  "github_webhook",
  "manual_api",
  "scan",
  "scheduled",
  "unknown",
] as const

export const TRIGGER_SOURCE_CHART_COLORS: Record<string, string> = {
  github_webhook: "#60a5fa",
  manual_api: "#fbbf24",
  scan: "#a1a1aa",
  scheduled: "#34d399",
  unknown: "#71717a",
}

const TERMINAL_TASK_STATUSES: TaskStatus[] = [
  "MERGED",
  "COMPLETED",
  "FAILED",
  "ESCALATED",
]

const ACTIVE_WORKFLOW_STATUSES: TaskStatus[] = ["RECEIVED", "SESSION_CREATED", "RUNNING"]

const CI_PENDING_STATUSES: TaskStatus[] = ["PR_OPENED", "READY_FOR_REVIEW"]

const WORKFLOW_LABELS: Record<TaskStatus, string> = {
  RECEIVED: "Received",
  SESSION_CREATED: "Session created",
  RUNNING: "Running",
  PR_OPENED: "PR opened",
  CI_FAILED: "CI failed",
  READY_FOR_REVIEW: "Ready for review",
  MERGED: "Merged",
  COMPLETED: "Completed",
  FAILED: "Failed",
  ESCALATED: "Escalated",
}

export type DevinPresentationState =
  | "completed"
  | "failed"
  | "escalated"
  | "human_action_required"
  | "working"
  | "waiting_for_ci"
  | "waiting_for_review"
  | "waiting_for_input"
  | "unknown"

export interface DevinPresentation {
  state: DevinPresentationState
  label: string
  sublabel: string | null
}

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

export function formatTaskSource(devinOrigin: string | null | undefined): string {
  if (!devinOrigin) return "—"
  return ORIGIN_LABELS[devinOrigin] ?? devinOrigin
}

export function formatTriggerSource(triggerSource: string | null | undefined): string {
  if (!triggerSource) return "Unknown"
  return TRIGGER_SOURCE_LABELS[triggerSource] ?? triggerSource.replaceAll("_", " ")
}

/**
 * Distinct hues only so multiple sources are scannable in one pass; the
 * variants carry no severity meaning.
 */
export function getTriggerSourceChartColor(triggerSource: string): string {
  return TRIGGER_SOURCE_CHART_COLORS[triggerSource] ?? TRIGGER_SOURCE_CHART_COLORS.unknown
}

export function getActiveTriggerSources(
  points: Array<{ by_source?: Record<string, number> }>,
): string[] {
  return TRIGGER_SOURCE_CHART_ORDER.filter((source) =>
    points.some((point) => (point.by_source?.[source] ?? 0) > 0),
  )
}

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

export function formatWorkflowLabel(status: TaskStatus): string {
  return WORKFLOW_LABELS[status] ?? status
}

export function hasExplicitBlocker(task: Task): boolean {
  const detail = task.devin_status_detail?.toLowerCase()
  const devinStatus = task.devin_status?.toLowerCase()

  if (task.remediation_outcome?.toLowerCase() === "blocked") return true
  if (task.blocker?.trim()) return true
  if (task.escalation_reason?.trim()) return true
  if (devinStatus === "error") return true
  if (
    devinStatus === "suspended" &&
    (detail === "usage_limit_exceeded" || detail === "out_of_credits")
  ) {
    return true
  }
  return false
}

function isWaitingForInputDetail(detail: string | null | undefined): boolean {
  const normalized = detail?.toLowerCase()
  return normalized === "waiting_for_user" || normalized === "waiting_for_approval"
}

function hasCompletionSignal(task: Task): boolean {
  if (task.remediation_outcome) return true
  return task.devin_status_detail?.toLowerCase() === "finished"
}

export function isDevinActivelyWorking(task: Task): boolean {
  const devinStatus = task.devin_status?.toLowerCase()
  const detail = task.devin_status_detail?.toLowerCase()

  if (isWaitingForInputDetail(detail)) return false
  if (devinStatus === "exit") return false
  if (hasCompletionSignal(task)) return false

  if (devinStatus === "running" || devinStatus === "resuming") return true
  if (detail === "working") return true

  if (ACTIVE_WORKFLOW_STATUSES.includes(task.status)) {
    if (task.status === "RUNNING" || !task.pr_url) return true
  }

  return false
}

function isWaitingForCi(task: Task): boolean {
  return getCiSummaryState(task) === "running" && !isDevinActivelyWorking(task)
}

function isWaitingForReview(task: Task): boolean {
  return (
    hasOpenPr(task) &&
    getCiSummaryState(task) === "passed" &&
    CI_PENDING_STATUSES.includes(task.status) &&
    !isDevinActivelyWorking(task)
  )
}

export function getDevinPresentationState(task: Task): DevinPresentation {
  if (task.status === "MERGED") {
    return { state: "completed", label: "Completed", sublabel: null }
  }
  if (task.status === "COMPLETED") {
    return {
      state: "completed",
      label: "Resolved without PR",
      sublabel: task.completion_reason ?? task.implementation_summary ?? null,
    }
  }
  if (task.status === "FAILED") {
    return { state: "failed", label: "Failed", sublabel: null }
  }
  if (task.status === "ESCALATED") {
    return { state: "escalated", label: "Escalated", sublabel: null }
  }

  if (hasExplicitBlocker(task)) {
    const devinStatus = task.devin_status?.toLowerCase()
    const detail = task.devin_status_detail?.toLowerCase()
    let sublabel: string | null = null
    if (devinStatus === "error") {
      sublabel = "Devin session error"
    } else if (
      devinStatus === "suspended" &&
      (detail === "usage_limit_exceeded" || detail === "out_of_credits")
    ) {
      sublabel = "Usage limit exceeded"
    } else if (task.blocker?.trim()) {
      sublabel = "Blocker reported"
    }
    return {
      state: "human_action_required",
      label: "Human action required",
      sublabel,
    }
  }

  if (isDevinActivelyWorking(task)) {
    return { state: "working", label: "Working", sublabel: null }
  }

  if (isWaitingForCi(task)) {
    return { state: "waiting_for_ci", label: "Waiting for CI", sublabel: null }
  }

  if (isWaitingForReview(task)) {
    return { state: "waiting_for_review", label: "Waiting for review", sublabel: null }
  }

  if (isWaitingForInputDetail(task.devin_status_detail)) {
    return { state: "waiting_for_input", label: "Waiting for input", sublabel: null }
  }

  const raw = formatDevinExecution(task.devin_status, task.devin_status_detail)
  return {
    state: "unknown",
    label: raw === "—" ? "—" : raw,
    sublabel: null,
  }
}

/** @deprecated Use getDevinPresentationState(task).label */
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

export function getAttentionSummary(tasks: Task[]): {
  escalated: number
  failed: number
  needsIntervention: number
} {
  let escalated = 0
  let failed = 0
  let needsIntervention = 0

  for (const task of tasks) {
    if (isSmokeTestTask(task)) continue
    if (task.status === "ESCALATED") escalated += 1
    if (task.status === "FAILED") failed += 1
    if (hasExplicitBlocker(task) && !TERMINAL_TASK_STATUSES.includes(task.status)) {
      needsIntervention += 1
    }
  }

  return { escalated, failed, needsIntervention }
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

export function getRawDevinStateSnapshotNote(): string {
  return "Latest state persisted by the orchestrator poller"
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

export function formatDevinUsageKpi(
  verifiedTotalAcu: number,
  consumptionApiAvailable: boolean | null = null,
): string {
  if (verifiedTotalAcu > 0) {
    return `${verifiedTotalAcu.toFixed(1)} ACU`
  }
  if (consumptionApiAvailable === false) {
    return "Not reported"
  }
  return "No verified usage"
}

export function getDevinUsageNote(
  verifiedTotalAcu: number,
  consumptionApiAvailable: boolean | null,
): string {
  if (verifiedTotalAcu > 0) {
    return "Verified"
  }
  if (consumptionApiAvailable === false) {
    return "Consumption API unavailable / not reported"
  }
  return "Enterprise ACU reporting unavailable (self-serve/on-demand)"
}

/** @deprecated Use formatDevinUsageKpi */
export function formatVerifiedAcuTotal(
  verifiedTotalAcu: number,
  consumptionApiAvailable: boolean | null = null,
): string {
  return formatDevinUsageKpi(verifiedTotalAcu, consumptionApiAvailable)
}

/** @deprecated Use getDevinUsageNote */
export function getVerifiedAcuNote(
  verifiedTotalAcu: number,
  consumptionApiAvailable: boolean | null,
): string {
  if (consumptionApiAvailable === false && verifiedTotalAcu <= 0) {
    return "Consumption API unavailable / not reported"
  }
  return getDevinUsageNote(verifiedTotalAcu, consumptionApiAvailable)
}
