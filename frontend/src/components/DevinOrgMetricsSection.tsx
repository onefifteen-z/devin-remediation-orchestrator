import { MetricCard } from "@/components/MetricCard"
import { Card, CardContent } from "@/components/ui/card"
import {
  SESSION_SIZE_DISCLAIMER,
  formatActiveUsersSummary,
  formatOrgWindowLabel,
  formatOriginDistribution,
  formatSizeDistribution,
} from "@/lib/orgMetrics"
import type { DevinOrgMetrics } from "@/types/metrics"

interface DevinOrgMetricsSectionProps {
  orgMetrics: DevinOrgMetrics | null
  windowDays: number
  loading?: boolean
}

function BreakdownRow({
  label,
  value,
  note,
}: {
  label: string
  value: string | null
  note?: string
}) {
  return (
    <div>
      <p className="text-xs font-medium text-foreground">{label}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{value ?? "None"}</p>
      {note && <p className="mt-0.5 text-[11px] text-muted-foreground">{note}</p>}
    </div>
  )
}

export function DevinOrgMetricsSection({
  orgMetrics,
  windowDays,
  loading,
}: DevinOrgMetricsSectionProps) {
  const windowLabel = formatOrgWindowLabel(windowDays)

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-sm font-semibold text-foreground">
          Devin Organization · {windowLabel}
        </h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Counts every session in the Devin org, including playbook and automation runs,
          so these are not comparable to the remediation metrics above.
        </p>
      </div>

      {!loading && !orgMetrics ? (
        <Card>
          <CardContent className="py-4">
            <p className="text-xs text-muted-foreground">
              Org metrics unavailable from the Devin API.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <MetricCard
              title="Org Sessions"
              value={orgMetrics ? String(orgMetrics.usage.sessions_count) : "—"}
              description={`Sessions created in the ${windowLabel}`}
              loading={loading}
            />
            <MetricCard
              title="PRs Created"
              value={orgMetrics ? String(orgMetrics.pull_requests.prs_created_count) : "—"}
              description="Pull requests opened by Devin sessions"
              loading={loading}
            />
            <MetricCard
              title="PRs Merged"
              value={orgMetrics ? String(orgMetrics.pull_requests.prs_merged_count) : "—"}
              description="Pull requests merged org-wide"
              loading={loading}
            />
            <MetricCard
              title="PRs Closed"
              value={orgMetrics ? String(orgMetrics.pull_requests.prs_closed_count) : "—"}
              description="Closed without merging"
              loading={loading}
            />
            <MetricCard
              title="Peak DAU"
              value={orgMetrics ? String(orgMetrics.peak_dau) : "—"}
              description="Highest daily active users in window"
              loading={loading}
            />
          </div>

          {orgMetrics && (
            <Card>
              <CardContent className="grid gap-3 py-4 sm:grid-cols-2">
                <BreakdownRow
                  label="Sessions by Origin"
                  value={formatOriginDistribution(orgMetrics.sessions.sessions_created_by_origin)}
                />
                <BreakdownRow
                  label="Sessions by Size"
                  value={formatSizeDistribution(orgMetrics.sessions.sessions_created_by_size)}
                  note={SESSION_SIZE_DISCLAIMER}
                />
                <BreakdownRow
                  label="Sessions with Playbook"
                  value={String(orgMetrics.sessions.sessions_created_with_playbook_count)}
                />
                <BreakdownRow
                  label="Active Users"
                  value={formatActiveUsersSummary(
                    orgMetrics.active_users,
                    orgMetrics.peak_dau,
                    orgMetrics.peak_wau,
                    orgMetrics.peak_mau,
                  )}
                />
              </CardContent>
            </Card>
          )}
        </>
      )}
    </section>
  )
}
