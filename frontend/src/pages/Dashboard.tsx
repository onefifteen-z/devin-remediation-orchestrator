import { useMutation, useQuery } from "@tanstack/react-query"
import { AlertCircle, RefreshCw, ScanSearch } from "lucide-react"
import { useState } from "react"
import { fetchMetrics, fetchTasks, scanGitHubIssues } from "@/api/client"
import { MetricCard } from "@/components/MetricCard"
import { TaskTable } from "@/components/TaskTable"
import { ThroughputChart } from "@/components/ThroughputChart"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDuration, formatPercent } from "@/lib/utils"

export function Dashboard() {
  const [scanMessage, setScanMessage] = useState<string | null>(null)
  const [scanError, setScanError] = useState<string | null>(null)

  const metricsQuery = useQuery({
    queryKey: ["metrics"],
    queryFn: fetchMetrics,
    refetchInterval: 30000,
  })

  const tasksQuery = useQuery({
    queryKey: ["tasks"],
    queryFn: fetchTasks,
    refetchInterval: 30000,
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

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <MetricCard
            title="Success Rate"
            value={metrics ? formatPercent(metrics.success_rate) : "—"}
            loading={isLoading}
          />
          <MetricCard
            title="Merge Rate"
            value={metrics ? formatPercent(metrics.merge_rate) : "—"}
            loading={isLoading}
          />
          <MetricCard
            title="Median MTTR"
            value={metrics ? formatDuration(metrics.median_mttr_seconds) : "—"}
            loading={isLoading}
          />
          <MetricCard
            title="Throughput (7d)"
            value={metrics ? String(metrics.throughput_7d) : "—"}
            loading={isLoading}
          />
          <MetricCard
            title="ACU Used"
            value={metrics ? metrics.total_acu.toFixed(1) : "—"}
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
          <CardHeader>
            <CardTitle>Recent Remediations</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : tasks.length === 0 ? (
              <Alert>
                <AlertTitle>No remediations yet</AlertTitle>
                <AlertDescription>
                  Add the <code className="rounded bg-muted px-1 py-0.5 text-xs">devin-remediate</code>{" "}
                  label to a GitHub issue, then click Scan labeled issues to import existing open issues.
                </AlertDescription>
              </Alert>
            ) : (
              <TaskTable tasks={tasks} />
            )}
          </CardContent>
        </Card>

        {metrics && metrics.total_tasks > 0 && (
          <div className="grid gap-4 text-xs text-muted-foreground sm:grid-cols-4">
            <div>Total tasks: {metrics.total_tasks}</div>
            <div>Active: {metrics.active_tasks}</div>
            <div>Failed: {metrics.failed_tasks}</div>
            <div>Escalated: {metrics.escalated_tasks}</div>
          </div>
        )}
      </main>
    </div>
  )
}
