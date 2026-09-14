const ORIGIN_LABELS: Record<string, string> = {
  webapp: "Webapp",
  slack: "Slack",
  teams: "Teams",
  api: "API",
  linear: "Linear",
  jira: "Jira",
  automation: "Automation",
  desktop: "Desktop",
  code_scan: "Code Scan",
}

export function formatOrgWindowLabel(windowDays: number): string {
  return `last ${windowDays} days`
}

/**
 * Renders a bucket map as "API 6 · Webapp 1", dropping empty buckets.
 * Devin returns all nine origin and five size buckets regardless of activity,
 * so keeping the zeros would bury the signal.
 */
export function formatDistribution(
  buckets: Record<string, number> | null | undefined,
  labels: Record<string, string> = {},
): string | null {
  if (!buckets) return null
  const parts = Object.entries(buckets)
    .filter(([, count]) => count > 0)
    .sort(([, a], [, b]) => b - a)
    .map(([key, count]) => `${labels[key] ?? key.toUpperCase()} ${count}`)
  return parts.length > 0 ? parts.join(" · ") : null
}

export function formatOriginDistribution(
  buckets: Record<string, number> | null | undefined,
): string | null {
  return formatDistribution(buckets, ORIGIN_LABELS)
}

export function formatSizeDistribution(
  buckets: Record<string, number> | null | undefined,
): string | null {
  return formatDistribution(buckets)
}

export function formatActiveUsersSummary(
  activeUsers: number,
  peakDau: number,
  peakWau: number,
  peakMau: number,
): string {
  return `${activeUsers} in window · peak ${peakDau} daily / ${peakWau} weekly / ${peakMau} monthly`
}

/**
 * Verified against live data: for the same 8 sessions in the same window,
 * /metrics/sessions reported xs 8 / s 0 while /sessions/insights reported
 * xs 5 / s 3. Both values are passed through unchanged, so the disagreement
 * is between two Devin endpoints rather than a mapping on our side.
 */
export const SESSION_SIZE_DISCLAIMER =
  "Bucketed by ACU from Devin's org metrics endpoint, which collapses to xs while " +
  "Enterprise ACU reporting is unavailable. The per-task Size column above comes " +
  "from the session insights endpoint and uses a different signal."
