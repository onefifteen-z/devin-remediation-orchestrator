import type {
  InsightsActionItem,
  InsightsClassification,
  InsightsIssue,
  InsightsTimelineEvent,
  Task,
} from "@/types/task"

export type ImpactBadgeVariant = "destructive" | "warning" | "default"

export interface ParsedSessionInsights {
  classification: InsightsClassification | null
  issues: InsightsIssue[]
  timeline: InsightsTimelineEvent[]
  action_items: InsightsActionItem[]
}

const EMPTY_INSIGHTS: ParsedSessionInsights = {
  classification: null,
  issues: [],
  timeline: [],
  action_items: [],
}

const SESSION_SIZE_LABELS: Record<string, string> = {
  xs: "XS",
  s: "S",
  m: "M",
  l: "L",
  xl: "XL",
}

const ACTION_ITEM_TYPE_LABELS: Record<string, string> = {
  machine_setup: "Machine Setup",
  repo_config: "Repo Config",
  knowledge: "Knowledge",
  prompt_improvement: "Prompt",
  external: "External",
  other: "Other",
}

export function parseSessionInsights(task: Task): ParsedSessionInsights {
  if (!task.insights_json) return EMPTY_INSIGHTS

  try {
    const parsed = JSON.parse(task.insights_json) as Partial<ParsedSessionInsights>
    return {
      classification: parsed.classification ?? null,
      issues: parsed.issues ?? [],
      timeline: parsed.timeline ?? [],
      action_items: parsed.action_items ?? [],
    }
  } catch {
    return EMPTY_INSIGHTS
  }
}

export function hasSessionInsights(task: Task): boolean {
  const insights = parseSessionInsights(task)
  return Boolean(
    task.session_size ||
      task.num_user_messages != null ||
      task.num_devin_messages != null ||
      insights.classification ||
      insights.issues.length > 0 ||
      insights.timeline.length > 0 ||
      insights.action_items.length > 0,
  )
}

export function formatSessionSize(size: string | null | undefined): string {
  if (!size) return "—"
  return SESSION_SIZE_LABELS[size.toLowerCase()] ?? size.toUpperCase()
}

export function formatMessageTotal(
  numUserMessages: number | null | undefined,
  numDevinMessages: number | null | undefined,
): string | null {
  if (numUserMessages == null && numDevinMessages == null) return null
  const total = (numUserMessages ?? 0) + (numDevinMessages ?? 0)
  return `${total} msg${total === 1 ? "" : "s"}`
}

export function formatMessageBreakdown(
  numUserMessages: number | null | undefined,
  numDevinMessages: number | null | undefined,
): string | null {
  if (numUserMessages == null && numDevinMessages == null) return null
  return `${numUserMessages ?? 0} user · ${numDevinMessages ?? 0} Devin`
}

export function formatClassificationCategory(
  classification: InsightsClassification | null,
): string | null {
  if (!classification?.category) return null
  const label = classification.category.replaceAll("_", " ")
  if (classification.confidence == null) return label
  return `${label} (${Math.round(classification.confidence * 100)}% confidence)`
}

export function getImpactBadgeVariant(impact: string): ImpactBadgeVariant {
  switch (impact.toLowerCase()) {
    case "high":
      return "destructive"
    case "medium":
      return "warning"
    default:
      return "default"
  }
}

export function formatActionItemType(type: string): string {
  return ACTION_ITEM_TYPE_LABELS[type.toLowerCase()] ?? type.replaceAll("_", " ")
}

export function formatInsightsStatusNote(
  insightsStatus: string | null | undefined,
  insights: ParsedSessionInsights,
): string | null {
  const hasFindings =
    insights.issues.length > 0 ||
    insights.timeline.length > 0 ||
    insights.action_items.length > 0
  if (hasFindings) return null
  if (insightsStatus === "completed") {
    return "Devin's analysis completed without flagging issues for this session."
  }
  if (!insightsStatus) return null
  return `Analysis ${insightsStatus.replaceAll("_", " ")}.`
}
