import type { TaskStatus } from "@/types/task"

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
  if (!devinOrigin) return "GitHub"
  return ORIGIN_LABELS[devinOrigin] ?? devinOrigin
}

export function formatTriggerSource(
  triggerSource: string | null | undefined,
): string {
  if (!triggerSource) return "Unknown"
  return TRIGGER_SOURCE_LABELS[triggerSource] ?? triggerSource.replaceAll("_", " ")
}

export function formatDevinExecutionForTask(
  taskStatus: TaskStatus,
  devinStatus: string | null | undefined,
  devinStatusDetail: string | null | undefined,
): string {
  if (TERMINAL_TASK_STATUSES.includes(taskStatus)) {
    if (taskStatus === "MERGED") return "completed"
    if (taskStatus === "FAILED") return "failed"
    return "escalated"
  }
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

export function formatPrState(prState: string | null | undefined): string | null {
  if (!prState) return null
  return prState.charAt(0).toUpperCase() + prState.slice(1)
}

export function extractPrNumber(prUrl: string): string | null {
  const match = prUrl.match(/\/pull\/(\d+)/)
  return match ? `#${match[1]}` : null
}

export const terminalTaskStatuses = TERMINAL_TASK_STATUSES

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
    return `${acuUsed.toFixed(1)} ACU`
  }
  return `${acuUsed.toFixed(1)} ACU (reported)`
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
