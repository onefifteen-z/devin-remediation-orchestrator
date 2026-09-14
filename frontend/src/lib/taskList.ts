import type { Task } from "@/types/task"
import type { TaskListParams } from "@/types/taskList"

export const DEFAULT_PAGE_SIZE = 25

export const PAGE_SIZE_OPTIONS = [10, 25, 50] as const

export function isSmokeTestTask(task: Task): boolean {
  return task.task_kind === "smoke_test" || task.issue_type.toLowerCase() === "dummy"
}

export function buildTaskListQuery(params: TaskListParams): string {
  const searchParams = new URLSearchParams()
  if (params.limit != null) searchParams.set("limit", String(params.limit))
  if (params.offset != null) searchParams.set("offset", String(params.offset))
  if (params.include_smoke_tests) searchParams.set("include_smoke_tests", "true")
  if (params.status) searchParams.set("status", params.status)
  if (params.trigger_source) searchParams.set("trigger_source", params.trigger_source)
  if (params.search?.trim()) searchParams.set("search", params.search.trim())
  if (params.sort_by) searchParams.set("sort_by", params.sort_by)
  if (params.sort_order) searchParams.set("sort_order", params.sort_order)
  const query = searchParams.toString()
  return query ? `?${query}` : ""
}

export function totalPages(total: number, pageSize: number): number {
  if (total <= 0) return 1
  return Math.ceil(total / pageSize)
}

const DESC_DEFAULT_FIELDS = new Set<TaskListParams["sort_by"]>([
  "created_at",
  "merged_at",
])

export function getNextSortParams(
  current: Pick<TaskListParams, "sort_by" | "sort_order">,
  field: NonNullable<TaskListParams["sort_by"]>,
): Pick<TaskListParams, "sort_by" | "sort_order" | "offset"> {
  if (current.sort_by === field) {
    return {
      sort_by: field,
      sort_order: current.sort_order === "desc" ? "asc" : "desc",
      offset: 0,
    }
  }

  return {
    sort_by: field,
    sort_order: DESC_DEFAULT_FIELDS.has(field) ? "desc" : "asc",
    offset: 0,
  }
}
