import { Badge } from "@/components/ui/badge"
import { formatCiRepairLine } from "@/lib/ci"
import {
  formatAcuDisplay,
  formatRawDevinState,
  formatTaskSource,
  getRawDevinStateClarification,
  getRawDevinStateSnapshotNote,
} from "@/lib/devin"
import {
  formatActionItemType,
  formatClassificationCategory,
  formatInsightsStatusNote,
  formatMessageBreakdown,
  formatSessionSize,
  getImpactBadgeVariant,
  hasSessionInsights,
  parseSessionInsights,
} from "@/lib/sessionInsights"
import {
  displayValue,
  formatOutcomeLabel,
  formatTestResultLabel,
  getOutcomeBadgeVariant,
  getTestResultBadgeVariant,
  hasOperationalMetadata,
  hasRemediationResult,
  parseRemediationResult,
} from "@/lib/remediationResult"
import type { Task } from "@/types/task"

interface RemediationResultPanelProps {
  task: Task
}

function SectionTitle({ children }: { children: string }) {
  return (
    <h4 className="text-[11px] font-semibold uppercase tracking-wide text-foreground">
      {children}
    </h4>
  )
}

function DetailField({
  label,
  value,
  className,
}: {
  label: string
  value: string | null | undefined
  className?: string
}) {
  return (
    <div className={className}>
      <p className="font-medium text-foreground">{label}</p>
      <p className="mt-0.5 whitespace-pre-wrap text-muted-foreground">{displayValue(value)}</p>
    </div>
  )
}

function RemediationResultSection({ task }: { task: Task }) {
  const result = parseRemediationResult(task)

  if (!hasRemediationResult(task)) {
    return (
      <section className="space-y-2">
        <SectionTitle>Remediation Result</SectionTitle>
        <p className="text-xs text-muted-foreground">No remediation result recorded.</p>
      </section>
    )
  }

  const outcomeLabel = formatOutcomeLabel(result.outcome)

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <SectionTitle>Remediation Result</SectionTitle>
        {outcomeLabel && (
          <Badge variant={getOutcomeBadgeVariant(result.outcome)} className="text-[10px]">
            {outcomeLabel}
          </Badge>
        )}
      </div>

      <div className="grid gap-3 text-xs sm:grid-cols-2">
        <DetailField label="Root Cause" value={result.root_cause} />
        <DetailField label="Implementation Summary" value={result.implementation_summary} />
        <DetailField label="Blocker" value={result.blocker} className="sm:col-span-2" />

        <div className="sm:col-span-2">
          <p className="font-medium text-foreground">Tests Performed</p>
          {result.tests_performed.length > 0 ? (
            <div className="mt-1.5 space-y-1.5">
              {result.tests_performed.map((test, index) => (
                <div
                  key={`${test.command}-${test.result}-${index}`}
                  className="flex items-center justify-between gap-3 rounded-md border border-border/60 bg-background/40 px-2.5 py-1.5"
                >
                  <code className="min-w-0 flex-1 truncate text-[11px] text-muted-foreground">
                    {test.command}
                  </code>
                  <Badge
                    variant={getTestResultBadgeVariant(test.result)}
                    className="shrink-0 text-[10px]"
                  >
                    {formatTestResultLabel(test.result)}
                  </Badge>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-0.5 text-muted-foreground">None</p>
          )}
        </div>

        <div className="sm:col-span-2">
          <p className="font-medium text-foreground">Residual Risks</p>
          {result.residual_risks.length > 0 ? (
            <ul className="mt-0.5 list-disc space-y-0.5 pl-4 text-muted-foreground">
              {result.residual_risks.map((risk) => (
                <li key={risk}>{risk}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-0.5 text-muted-foreground">None</p>
          )}
        </div>
      </div>
    </section>
  )
}

function SessionInsightsSection({ task }: { task: Task }) {
  if (!hasSessionInsights(task)) {
    return null
  }

  const insights = parseSessionInsights(task)
  const statusNote = formatInsightsStatusNote(task.insights_status, insights)

  return (
    <section className="space-y-3 border-t border-border/60 pt-3">
      <SectionTitle>Session Insights</SectionTitle>

      <div className="grid gap-3 text-xs sm:grid-cols-2">
        <DetailField label="Session Size" value={formatSessionSize(task.session_size)} />
        <DetailField
          label="Messages"
          value={formatMessageBreakdown(task.num_user_messages, task.num_devin_messages)}
        />
        <DetailField
          label="Category"
          value={formatClassificationCategory(insights.classification)}
        />
        <DetailField
          label="Languages"
          value={insights.classification?.programming_languages.join(", ")}
        />
        <DetailField
          label="Tools & Frameworks"
          value={insights.classification?.tools_and_frameworks.join(", ")}
          className="sm:col-span-2"
        />
      </div>

      {statusNote && <p className="text-xs text-muted-foreground">{statusNote}</p>}

      {insights.timeline.length > 0 && (
        <div className="text-xs">
          <p className="font-medium text-foreground">Timeline</p>
          <ol className="mt-1.5 space-y-1.5">
            {insights.timeline.map((event, index) => (
              <li
                key={`${event.title}-${index}`}
                className="flex gap-2 rounded-md border border-border/60 bg-background/40 px-2.5 py-1.5"
              >
                <span
                  className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full"
                  style={{ backgroundColor: event.color || "currentColor" }}
                />
                <div className="min-w-0">
                  <p className="font-medium text-foreground">{event.title}</p>
                  <p className="mt-0.5 text-muted-foreground">{event.description}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      {insights.issues.length > 0 && (
        <div className="text-xs">
          <p className="font-medium text-foreground">Issues ({insights.issues.length})</p>
          <div className="mt-1.5 space-y-1.5">
            {insights.issues.map((issue, index) => (
              <div
                key={issue.id || `${issue.label}-${index}`}
                className="rounded-md border border-border/60 bg-background/40 px-2.5 py-1.5"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge
                    variant={getImpactBadgeVariant(issue.impact)}
                    className="text-[10px]"
                  >
                    {issue.impact.toUpperCase()} IMPACT
                  </Badge>
                  <span className="font-medium text-foreground">{issue.title || issue.label}</span>
                  {issue.title && (
                    <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      {issue.label}
                    </span>
                  )}
                </div>
                <p className="mt-1 text-muted-foreground">{issue.issue}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {insights.action_items.length > 0 && (
        <div className="text-xs">
          <p className="font-medium text-foreground">
            Action Items ({insights.action_items.length})
          </p>
          <ul className="mt-1.5 space-y-1.5">
            {insights.action_items.map((item, index) => (
              <li
                key={`${item.action_item}-${index}`}
                className="rounded-md border border-border/60 bg-background/40 px-2.5 py-1.5"
              >
                <Badge variant="info" className="text-[10px]">
                  {formatActionItemType(item.type)}
                </Badge>
                <p className="mt-1 text-muted-foreground">{item.action_item}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function OperationalMetadataSection({ task }: { task: Task }) {
  const rawDevin = formatRawDevinState(task.devin_status, task.devin_status_detail)
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

  if (!hasOperationalMetadata(task) && !rawDevin && !ciLine) {
    return null
  }

  return (
    <section className="space-y-3 border-t border-border/60 pt-3">
      <SectionTitle>Operational Metadata</SectionTitle>
      <div className="grid gap-3 text-xs sm:grid-cols-2">
        <div>
          <p className="font-medium text-foreground">Devin Session</p>
          {task.devin_session_url ? (
            <a
              href={task.devin_session_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-0.5 inline-block font-mono text-blue-400 hover:underline"
            >
              {task.devin_session_id ?? "View session"}
            </a>
          ) : (
            <p className="mt-0.5 font-mono text-muted-foreground">
              {displayValue(task.devin_session_id)}
            </p>
          )}
        </div>

        <DetailField
          label="ACU"
          value={formatAcuDisplay(task.acu_used, task.acu_source, task.acu_verified)}
        />
        <DetailField label="Playbook" value={task.playbook_id} />
        <DetailField label="Tags" value={task.devin_tags} />
        <DetailField
          label="Devin Origin"
          value={task.devin_origin ? formatTaskSource(task.devin_origin) : null}
        />

        {rawDevin && (
          <div className="sm:col-span-2">
            <p className="font-medium text-foreground">Raw Devin State</p>
            {getRawDevinStateSnapshotNote(task.status) && (
              <p className="mt-0.5 text-[11px] text-muted-foreground">
                {getRawDevinStateSnapshotNote(task.status)}
              </p>
            )}
            <p className="mt-0.5 font-mono text-muted-foreground">{rawDevin}</p>
            {getRawDevinStateClarification(task.status, task.devin_status_detail) && (
              <p className="mt-1 text-[11px] text-muted-foreground">
                {getRawDevinStateClarification(task.status, task.devin_status_detail)}
              </p>
            )}
          </div>
        )}

        {ciLine && (
          <div className="sm:col-span-2">
            <p className="font-medium text-foreground">CI</p>
            <p className="mt-0.5 text-muted-foreground">{ciLine}</p>
          </div>
        )}

        {task.failure_reason && (
          <DetailField label="Failure Reason" value={task.failure_reason} />
        )}
        {task.escalation_reason && (
          <DetailField label="Escalation Reason" value={task.escalation_reason} />
        )}
      </div>
    </section>
  )
}

export function RemediationResultPanel({ task }: RemediationResultPanelProps) {
  return (
    <div className="space-y-4">
      <RemediationResultSection task={task} />
      <SessionInsightsSection task={task} />
      <OperationalMetadataSection task={task} />
    </div>
  )
}
