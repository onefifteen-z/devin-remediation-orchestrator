import { ArrowDown, ArrowUp, ChevronDown, ChevronRight } from "lucide-react"
import { Fragment, useState } from "react"
import { StatusBadge } from "@/components/StatusBadge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { RemediationResultPanel } from "@/components/RemediationResultPanel"
import { formatCiRepairLine } from "@/lib/ci"
import {
  extractPrNumber,
  formatDevinExecutionForTask,
  formatPrState,
  formatTriggerSource,
  getDevinAlertForTask,
  terminalTaskStatuses,
} from "@/lib/devin"
import { formatMessageTotal, formatSessionSize } from "@/lib/sessionInsights"
import { getNextSortParams, isSmokeTestTask } from "@/lib/taskList"
import { formatDateTime } from "@/lib/utils"
import type { Task } from "@/types/task"
import type { TaskListParams, TaskSortField } from "@/types/taskList"

interface TaskTableProps {
  tasks: Task[]
  sortBy: TaskSortField
  sortOrder: TaskListParams["sort_order"]
  onSortChange: (next: Pick<TaskListParams, "sort_by" | "sort_order" | "offset">) => void
}

interface SortableHeaderProps {
  field: TaskSortField
  label: string
  sortBy: TaskSortField
  sortOrder: TaskListParams["sort_order"]
  onSort: (field: TaskSortField) => void
  className?: string
}

function SortableHeader({
  field,
  label,
  sortBy,
  sortOrder,
  onSort,
  className,
}: SortableHeaderProps) {
  const active = sortBy === field

  return (
    <TableHead className={className}>
      <button
        type="button"
        onClick={() => onSort(field)}
        className="group inline-flex items-center gap-1 text-left transition-colors hover:text-foreground"
      >
        <span>{label}</span>
        <span className="inline-flex h-3.5 w-3.5 items-center justify-center">
          {active ? (
            sortOrder === "desc" ? (
              <ArrowDown className="h-3 w-3 text-foreground" />
            ) : (
              <ArrowUp className="h-3 w-3 text-foreground" />
            )
          ) : (
            <ArrowDown className="h-3 w-3 opacity-0 transition-opacity group-hover:opacity-30" />
          )}
        </span>
      </button>
    </TableHead>
  )
}

export function TaskTable({ tasks, sortBy, sortOrder, onSortChange }: TaskTableProps) {
  const [expandedTaskIds, setExpandedTaskIds] = useState<Set<number>>(new Set())

  const handleSort = (field: TaskSortField) => {
    onSortChange(getNextSortParams({ sort_by: sortBy, sort_order: sortOrder }, field))
  }

  const toggleExpanded = (taskId: number) => {
    setExpandedTaskIds((current) => {
      const next = new Set(current)
      if (next.has(taskId)) {
        next.delete(taskId)
      } else {
        next.add(taskId)
      }
      return next
    })
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-8" />
          <SortableHeader
            field="repository"
            label="Issue"
            sortBy={sortBy}
            sortOrder={sortOrder}
            onSort={handleSort}
          />
          <SortableHeader
            field="trigger_source"
            label="Source"
            sortBy={sortBy}
            sortOrder={sortOrder}
            onSort={handleSort}
          />
          <SortableHeader
            field="status"
            label="Status"
            sortBy={sortBy}
            sortOrder={sortOrder}
            onSort={handleSort}
          />
          <TableHead>Devin</TableHead>
          <TableHead>PR / CI</TableHead>
          <TableHead>Size</TableHead>
          <SortableHeader
            field="created_at"
            label="Created"
            sortBy={sortBy}
            sortOrder={sortOrder}
            onSort={handleSort}
          />
          <SortableHeader
            field="merged_at"
            label="Merged At"
            sortBy={sortBy}
            sortOrder={sortOrder}
            onSort={handleSort}
          />
        </TableRow>
      </TableHeader>
      <TableBody>
        {tasks.map((task) => {
          const devinAlert = getDevinAlertForTask(
            task.status,
            task.devin_status,
            task.devin_status_detail,
          )
          const prNumber = task.pr_url ? extractPrNumber(task.pr_url) : null
          const prState = formatPrState(task.pr_state)
          const ciLine = formatCiRepairLine(
            task.ci_check_name,
            task.ci_conclusion,
            task.failure_type,
            task.ci_repair_attempts,
            task.max_ci_repair_attempts,
            task.ci_repair_message_sent_at,
            task.ci_repair_verified_at,
            task.ci_classification_reason,
          )
          const messageTotal = formatMessageTotal(
            task.num_user_messages,
            task.num_devin_messages,
          )
          const isExpandable = terminalTaskStatuses.includes(task.status)
          const isExpanded = expandedTaskIds.has(task.id)

          return (
            <Fragment key={task.id}>
              <TableRow>
                <TableCell>
                  {isExpandable ? (
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-foreground"
                      onClick={() => toggleExpanded(task.id)}
                      aria-label="Toggle task details"
                    >
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </button>
                  ) : null}
                </TableCell>
                <TableCell>
                  <div className="max-w-xs">
                    <a
                      href={task.github_issue_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium hover:underline"
                    >
                      {task.github_repository}#{task.github_issue_number}
                    </a>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">{task.issue_title}</p>
                    {isSmokeTestTask(task) && (
                      <p className="mt-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                        Smoke test{task.issue_type.toLowerCase() === "dummy" ? " · dummy" : ""}
                      </p>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {formatTriggerSource(task.trigger_source)}
                </TableCell>
                <TableCell>
                  <StatusBadge status={task.status} />
                </TableCell>
                <TableCell>
                  <div className="max-w-[10rem]">
                    {task.devin_session_url ? (
                      <a
                        href={task.devin_session_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono text-xs text-blue-400 hover:underline"
                      >
                        {formatDevinExecutionForTask(
                          task.status,
                          task.devin_status,
                          task.devin_status_detail,
                        )}
                      </a>
                    ) : (
                      <span className="font-mono text-xs text-muted-foreground">
                        {formatDevinExecutionForTask(
                          task.status,
                          task.devin_status,
                          task.devin_status_detail,
                        )}
                      </span>
                    )}
                    {devinAlert && (
                      <p className="mt-0.5 text-xs text-amber-500">{devinAlert}</p>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  {task.pr_url ? (
                    <div>
                      <a
                        href={task.pr_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-400 hover:underline"
                      >
                        {prNumber ?? "View PR"}
                      </a>
                      {prState && (
                        <p className="text-xs text-muted-foreground">{prState}</p>
                      )}
                      {ciLine && (
                        <p className="mt-0.5 text-xs text-muted-foreground">{ciLine}</p>
                      )}
                    </div>
                  ) : ciLine ? (
                    <p className="text-xs text-muted-foreground">{ciLine}</p>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell>
                  <div className="font-mono text-xs tabular-nums">
                    {formatSessionSize(task.session_size)}
                  </div>
                  {messageTotal && (
                    <p className="mt-0.5 text-xs text-muted-foreground">{messageTotal}</p>
                  )}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {formatDateTime(task.created_at)}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {task.merged_at ? formatDateTime(task.merged_at) : "—"}
                </TableCell>
              </TableRow>
              {isExpandable && isExpanded && (
                <TableRow>
                  <TableCell />
                  <TableCell colSpan={8} className="bg-muted/20">
                    <RemediationResultPanel task={task} />
                  </TableCell>
                </TableRow>
              )}
            </Fragment>
          )
        })}
      </TableBody>
    </Table>
  )
}
