import { Badge } from "@/components/ui/badge"
import type { TaskStatus } from "@/types/task"

const statusConfig: Record<TaskStatus, { variant: "default" | "success" | "warning" | "destructive" | "info"; label: string }> = {
  RECEIVED: { variant: "default", label: "RECEIVED" },
  SESSION_CREATED: { variant: "info", label: "SESSION_CREATED" },
  RUNNING: { variant: "info", label: "RUNNING" },
  PR_OPENED: { variant: "warning", label: "PR_OPENED" },
  CI_FAILED: { variant: "destructive", label: "CI_FAILED" },
  READY_FOR_REVIEW: { variant: "warning", label: "READY_FOR_REVIEW" },
  MERGED: { variant: "success", label: "MERGED" },
  COMPLETED: { variant: "success", label: "Completed" },
  FAILED: { variant: "destructive", label: "FAILED" },
  ESCALATED: { variant: "destructive", label: "ESCALATED" },
}

export function StatusBadge({ status }: { status: TaskStatus }) {
  const config = statusConfig[status]
  return <Badge variant={config.variant}>{config.label}</Badge>
}
