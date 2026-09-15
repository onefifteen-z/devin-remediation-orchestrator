import { ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { PAGE_SIZE_OPTIONS, totalPages } from "@/lib/taskList"
import type { TaskListParams, TaskTriggerSource } from "@/types/taskList"
import type { TaskStatus } from "@/types/task"

interface TaskListControlsProps {
  params: TaskListParams
  total: number
  onChange: (next: Partial<TaskListParams>) => void
}

const STATUS_OPTIONS: Array<{ value: "" | TaskStatus; label: string }> = [
  { value: "", label: "All statuses" },
  { value: "RECEIVED", label: "Received" },
  { value: "RUNNING", label: "Running" },
  { value: "PR_OPENED", label: "PR opened" },
  { value: "CI_FAILED", label: "CI failed" },
  { value: "READY_FOR_REVIEW", label: "Ready for review" },
  { value: "COMPLETED", label: "Completed" },
  { value: "MERGED", label: "Merged" },
  { value: "FAILED", label: "Failed" },
  { value: "ESCALATED", label: "Escalated" },
]

const SOURCE_OPTIONS: Array<{ value: "" | TaskTriggerSource; label: string }> = [
  { value: "", label: "All sources" },
  { value: "github_webhook", label: "GitHub Webhook" },
  { value: "manual_api", label: "Manual API" },
  { value: "scan", label: "Scan" },
  { value: "scheduled", label: "Scheduled" },
]

const selectClassName =
  "h-8 w-full rounded-md border border-input bg-background px-2.5 text-xs text-foreground shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"

const labelClassName =
  "text-[11px] font-medium uppercase tracking-wide text-muted-foreground"

export function TaskListControls({ params, total, onChange }: TaskListControlsProps) {
  const pageSize = params.limit ?? 25
  const offset = params.offset ?? 0
  const currentPage = Math.floor(offset / pageSize) + 1
  const pages = totalPages(total, pageSize)
  const rangeStart = total === 0 ? 0 : offset + 1
  const rangeEnd = Math.min(offset + pageSize, total)

  const resetPage = (next: Partial<TaskListParams>) => {
    onChange({ offset: 0, ...next })
  }

  return (
    <div className="mb-4 space-y-3">
      <div className="grid gap-3 md:grid-cols-3">
        <label className="grid gap-1.5">
          <span className={labelClassName}>Search</span>
          <input
            type="search"
            className={selectClassName}
            placeholder="Repo, title, or issue #"
            value={params.search ?? ""}
            onChange={(event) => resetPage({ search: event.target.value })}
          />
        </label>

        <label className="grid gap-1.5">
          <span className={labelClassName}>Status</span>
          <select
            className={selectClassName}
            value={params.status ?? ""}
            onChange={(event) =>
              resetPage({
                status: (event.target.value as TaskStatus | "") || undefined,
              })
            }
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.label} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-1.5">
          <span className={labelClassName}>Source</span>
          <select
            className={selectClassName}
            value={params.trigger_source ?? ""}
            onChange={(event) =>
              resetPage({
                trigger_source:
                  (event.target.value as TaskTriggerSource | "") || undefined,
              })
            }
          >
            {SOURCE_OPTIONS.map((option) => (
              <option key={option.label} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="flex flex-col gap-2 border-t border-border/60 pt-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-muted-foreground">
          {total === 0
            ? "No tasks match the current filters."
            : `Showing ${rangeStart}–${rangeEnd} of ${total}`}
        </p>

        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>Per page</span>
            <select
              className={`${selectClassName} w-auto min-w-[4rem]`}
              value={pageSize}
              onChange={(event) =>
                onChange({
                  limit: Number(event.target.value),
                  offset: 0,
                })
              }
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>

          <Button
            variant="outline"
            size="sm"
            disabled={currentPage <= 1}
            onClick={() => onChange({ offset: Math.max(0, offset - pageSize) })}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-[4.5rem] text-center text-xs text-muted-foreground">
            Page {currentPage} / {pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={currentPage >= pages}
            onClick={() => onChange({ offset: offset + pageSize })}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
