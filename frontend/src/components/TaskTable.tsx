import { StatusBadge } from "@/components/StatusBadge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
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
          <TableHead>Type</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Devin Session</TableHead>
          <TableHead>PR</TableHead>
          <TableHead>ACU</TableHead>
          <TableHead>Created</TableHead>
          <TableHead>Updated</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {tasks.map((task) => (
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
            <TableCell className="text-muted-foreground">{task.issue_type}</TableCell>
            <TableCell>
              <StatusBadge status={task.status} />
            </TableCell>
            <TableCell>
              {task.devin_session_url ? (
                <a
                  href={task.devin_session_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-mono text-xs text-blue-400 hover:underline"
                >
                  {task.devin_session_id ?? "View"}
                </a>
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </TableCell>
            <TableCell>
              {task.pr_url ? (
                <a
                  href={task.pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-400 hover:underline"
                >
                  View PR
                </a>
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
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
