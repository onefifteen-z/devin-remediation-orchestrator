import type { TaskStatus } from "@/types/task"

export type TaskSortField =
  | "created_at"
  | "merged_at"
  | "status"
  | "repository"
  | "issue_number"
  | "issue_title"
  | "trigger_source"

export type TaskSortOrder = "asc" | "desc"

export type TaskTriggerSource =
  | "github_webhook"
  | "manual_api"
  | "scan"
  | "scheduled"

export interface TaskListParams {
  limit?: number
  offset?: number
  include_smoke_tests?: boolean
  status?: TaskStatus
  trigger_source?: TaskTriggerSource
  search?: string
  sort_by?: TaskSortField
  sort_order?: TaskSortOrder
}
