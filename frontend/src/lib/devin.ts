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

export function formatPrState(prState: string | null | undefined): string | null {
  if (!prState) return null
  return prState.charAt(0).toUpperCase() + prState.slice(1)
}

export function extractPrNumber(prUrl: string): string | null {
  const match = prUrl.match(/\/pull\/(\d+)/)
  return match ? `#${match[1]}` : null
}
