import { StatusBadge } from "@/components/StatusBadge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatCiRepairLine } from "@/lib/ci"
import {
  extractPrNumber,
  formatDevinExecutionForTask,
  formatPrState,
  formatTriggerSource,
  getDevinAlertForTask,
} from "@/lib/devin"
import { formatDateTime } from "@/lib/utils"
import type { Task } from "@/types/task"

interface TaskTableProps {
  tasks: Task[]
}

export function TaskTable({ tasks }: TaskTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Issue</TableHead>
          <TableHead>Source</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Devin</TableHead>
          <TableHead>PR</TableHead>
          <TableHead>ACU</TableHead>
          <TableHead>Created</TableHead>
          <TableHead>Updated</TableHead>
          <TableHead>Merged At</TableHead>
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
          )

          return (
            <TableRow key={task.id}>
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
                      <p className="mt-0.5 text-xs text-muted-foreground">CI: {ciLine}</p>
                    )}
                  </div>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </TableCell>
              <TableCell className="font-mono text-xs tabular-nums">
                {task.acu_used != null ? task.acu_used.toFixed(1) : "—"}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {formatDateTime(task.created_at)}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {formatDateTime(task.updated_at)}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {task.merged_at ? formatDateTime(task.merged_at) : "—"}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
