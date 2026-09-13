import { ChevronDown, ChevronRight } from "lucide-react"
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
import { formatCiRepairLine } from "@/lib/ci"
import {
  extractPrNumber,
  formatAcuDisplay,
  formatDevinExecutionForTask,
  formatPrState,
  formatTriggerSource,
  getDevinAlertForTask,
  parseStructuredResult,
  terminalTaskStatuses,
} from "@/lib/devin"
import { formatDateTime } from "@/lib/utils"
import type { Task } from "@/types/task"

interface TaskTableProps {
  tasks: Task[]
}

function StructuredResultDetails({ task }: { task: Task }) {
  const structured = parseStructuredResult(task.structured_result_json)
  const hasDetails =
    task.root_cause ||
    task.implementation_summary ||
    structured.tests_performed.length > 0 ||
    structured.residual_risks.length > 0 ||
    task.blocker ||
    task.playbook_id ||
    task.devin_tags

  if (!hasDetails) {
    return <p className="text-xs text-muted-foreground">No structured result recorded.</p>
  }

  return (
    <div className="grid gap-2 text-xs sm:grid-cols-2">
      {task.root_cause && (
        <div>
          <p className="font-medium text-foreground">Root Cause</p>
          <p className="text-muted-foreground">{task.root_cause}</p>
        </div>
      )}
      {task.implementation_summary && (
        <div>
          <p className="font-medium text-foreground">Implementation</p>
          <p className="text-muted-foreground">{task.implementation_summary}</p>
        </div>
      )}
      {structured.tests_performed.length > 0 && (
        <div>
          <p className="font-medium text-foreground">Tests</p>
          <ul className="list-disc pl-4 text-muted-foreground">
            {structured.tests_performed.map((test) => (
              <li key={`${test.command}-${test.result}`}>
                {test.command} — {test.result}
              </li>
            ))}
          </ul>
        </div>
      )}
      {structured.residual_risks.length > 0 && (
        <div>
          <p className="font-medium text-foreground">Residual Risks</p>
          <ul className="list-disc pl-4 text-muted-foreground">
            {structured.residual_risks.map((risk) => (
              <li key={risk}>{risk}</li>
            ))}
          </ul>
        </div>
      )}
      {task.blocker && (
        <div>
          <p className="font-medium text-foreground">Blocker</p>
          <p className="text-muted-foreground">{task.blocker}</p>
        </div>
      )}
      {task.playbook_id && (
        <div>
          <p className="font-medium text-foreground">Playbook</p>
          <p className="font-mono text-muted-foreground">{task.playbook_id}</p>
        </div>
      )}
      {task.devin_tags && (
        <div>
          <p className="font-medium text-foreground">Devin Tags</p>
          <p className="font-mono text-muted-foreground">{task.devin_tags}</p>
        </div>
      )}
    </div>
  )
}

export function TaskTable({ tasks }: TaskTableProps) {
  const [expandedTaskIds, setExpandedTaskIds] = useState<Set<number>>(new Set())

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
                      aria-label="Toggle structured result details"
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
                  {formatAcuDisplay(task.acu_used, task.acu_source, task.acu_verified)}
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
              {isExpandable && isExpanded && (
                <TableRow>
                  <TableCell />
                  <TableCell colSpan={9} className="bg-muted/20">
                    <StructuredResultDetails task={task} />
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
