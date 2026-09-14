import { useMutation, useQuery } from "@tanstack/react-query"
import { AlertCircle, RefreshCw, ScanSearch } from "lucide-react"
import { useState } from "react"
import { fetchMetrics, fetchTasks, scanGitHubIssues } from "@/api/client"
import { MetricCard } from "@/components/MetricCard"
import { TaskListControls } from "@/components/TaskListControls"
import { TaskTable } from "@/components/TaskTable"
import { ThroughputChart } from "@/components/ThroughputChart"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { formatVerifiedAcuTotal, getAttentionSummary } from "@/lib/devin"
import { DEFAULT_PAGE_SIZE } from "@/lib/taskList"
import { formatDuration, formatPercent } from "@/lib/utils"
import type { TaskListParams } from "@/types/taskList"

const DEFAULT_TASK_LIST_PARAMS: TaskListParams = {
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
  include_smoke_tests: false,
  sort_by: "created_at",
  sort_order: "desc",
}

export function Dashboard() {
  const [scanMessage, setScanMessage] = useState<string | null>(null)
  const [scanError, setScanError] = useState<string | null>(null)
  const [taskListParams, setTaskListParams] = useState<TaskListParams>(
    DEFAULT_TASK_LIST_PARAMS,
  )

  const metricsQuery = useQuery({
    queryKey: ["metrics"],
    queryFn: fetchMetrics,
    refetchInterval: 15000,
  })

  const tasksQuery = useQuery({
    queryKey: ["tasks", taskListParams],
    queryFn: () => fetchTasks(taskListParams),
    refetchInterval: 15000,
  })

  const attentionQuery = useQuery({
    queryKey: ["tasks", "attention"],
    queryFn: () =>
      fetchTasks({
        include_smoke_tests: false,
        limit: 500,
        offset: 0,
        sort_by: "created_at",
        sort_order: "desc",
      }),
    refetchInterval: 15000,
  })

  const isLoading = metricsQuery.isLoading || tasksQuery.isLoading
  const isError = metricsQuery.isError || tasksQuery.isError

  const scanMutation = useMutation({
    mutationFn: scanGitHubIssues,
    onSuccess: (result) => {
      setScanError(null)
      setScanMessage(
        `Scan complete: ${result.created} created, ${result.skipped} skipped (${result.scanned} scanned).`
      )
      metricsQuery.refetch()
      tasksQuery.refetch()
    },
    onError: (error: Error) => {
      setScanMessage(null)
      setScanError(error.message)
    },
  })

  const refetch = () => {
    metricsQuery.refetch()
    tasksQuery.refetch()
  }

  const metrics = metricsQuery.data
  const tasks = tasksQuery.data?.items ?? []
  const taskTotal = tasksQuery.data?.total ?? 0
  const attention = getAttentionSummary(attentionQuery.data?.items ?? [])
  const attentionCount = attention.escalated + attention.failed + attention.needsHuman

  return (
    <div className="min-h-screen">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Devin Remediation</h1>
            <p className="text-sm text-muted-foreground">
              Autonomous remediation operations console
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => scanMutation.mutate()}
              disabled={scanMutation.isPending}
            >
              <ScanSearch className="mr-2 h-3.5 w-3.5" />
              {scanMutation.isPending ? "Scanning..." : "Scan labeled issues"}
            </Button>
            <Button variant="outline" size="sm" onClick={refetch} disabled={isLoading}>
              <RefreshCw className="mr-2 h-3.5 w-3.5" />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-6 py-6">
        {scanMessage && (
          <Alert>
            <AlertTitle>Scan result</AlertTitle>
            <AlertDescription>{scanMessage}</AlertDescription>
          </Alert>
        )}

        {scanError && (
          <Alert variant="destructive">
            <AlertTitle>Scan failed</AlertTitle>
            <AlertDescription>{scanError}</AlertDescription>
          </Alert>
        )}

        {isError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Backend unavailable</AlertTitle>
            <AlertDescription className="flex items-center justify-between gap-4">
              <span>Unable to reach the orchestrator API. Check that the backend is running.</span>
              <Button variant="outline" size="sm" onClick={refetch}>
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {attentionCount > 0 && (
          <Alert>
            <AlertTitle>Needs attention</AlertTitle>
            <AlertDescription>
              {attention.escalated > 0 && `${attention.escalated} escalated`}
              {attention.escalated > 0 && attention.failed > 0 && " · "}
              {attention.failed > 0 && `${attention.failed} failed`}
              {(attention.escalated > 0 || attention.failed > 0) && attention.needsHuman > 0 && " · "}
              {attention.needsHuman > 0 && `${attention.needsHuman} waiting for human`}
            </AlertDescription>
          </Alert>
        )}

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <MetricCard
            title="Active"
            value={metrics ? String(metrics.active_tasks) : "—"}
            description="Production remediations in progress"
            loading={isLoading}
          />
          <MetricCard
            title="Merge Rate"
            value={metrics ? formatPercent(metrics.merge_rate) : "—"}
            description="Merged / production remediation tasks (excludes smoke tests)"
            loading={isLoading}
          />
          <MetricCard
            title="Median MTTR"
            value={metrics ? formatDuration(metrics.median_mttr_seconds) : "—"}
            description="merged_at − started_at for merged production tasks"
            loading={isLoading}
          />
          <MetricCard
            title="CI Recovery"
            value={metrics ? formatPercent(metrics.ci_recovery_rate) : "—"}
            description="Verified CI recoveries / tasks with CI failures"
            loading={isLoading}
          />
          <MetricCard
            title="Verified ACU"
            value={
              metrics ? formatVerifiedAcuTotal(metrics.verified_total_acu) : "—"
            }
            description={
              metrics?.consumption_api_available === false
                ? "Consumption API unavailable"
                : "Sum of consumption-verified task ACU only"
            }
            loading={isLoading}
          />
        </section>

        {isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <ThroughputChart data={metrics?.throughput_by_day ?? []} />
        )}

        <Separator />

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
            <CardTitle>Recent Remediations</CardTitle>
            <label
              htmlFor="show-smoke-tests"
              className="flex items-center gap-2 text-xs text-muted-foreground"
            >
              <span className="hidden sm:inline">Show smoke tests</span>
              <span className="sm:hidden">Smoke tests</span>
              <Switch
                id="show-smoke-tests"
                checked={Boolean(taskListParams.include_smoke_tests)}
                onCheckedChange={(checked) =>
                  setTaskListParams((current) => ({
                    ...current,
                    include_smoke_tests: checked,
                    offset: 0,
                  }))
                }
              />
            </label>
          </CardHeader>
          <CardContent>
            <TaskListControls
              params={taskListParams}
              total={taskTotal}
              onChange={(next) =>
                setTaskListParams((current) => ({ ...current, ...next }))
              }
            />
            {isLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : tasks.length === 0 ? (
              <Alert>
                <AlertTitle>No tasks match</AlertTitle>
                <AlertDescription>
                  {taskListParams.include_smoke_tests ||
                  taskListParams.status ||
                  taskListParams.search ||
                  taskListParams.trigger_source
                    ? "Try clearing filters or enabling smoke tests."
                    : (
                      <>
                        Add the{" "}
                        <code className="rounded bg-muted px-1 py-0.5 text-xs">devin-remediate</code>{" "}
                        label to a GitHub issue, then click Scan labeled issues to import existing
                        open issues.
                      </>
                    )}
                </AlertDescription>
              </Alert>
            ) : (
              <TaskTable
                tasks={tasks}
                sortBy={taskListParams.sort_by ?? "created_at"}
                sortOrder={taskListParams.sort_order ?? "desc"}
                onSortChange={(next) =>
                  setTaskListParams((current) => ({ ...current, ...next }))
                }
              />
            )}
          </CardContent>
        </Card>

        {metrics && metrics.total_tasks > 0 && (
          <div className="grid gap-4 text-xs text-muted-foreground sm:grid-cols-4">
            <div>Production tasks: {metrics.total_tasks}</div>
            <div>Active: {metrics.active_tasks}</div>
            <div>Failed: {metrics.failed_tasks}</div>
            <div>Escalated: {metrics.escalated_tasks}</div>
          </div>
        )}
      </main>
    </div>
  )
}
