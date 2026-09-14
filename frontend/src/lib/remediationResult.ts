import { getCiSummaryState } from "@/lib/ci"
import type { Task } from "@/types/task"
import type { TestCategory, TestPerformed } from "@/types/task"

export type RemediationOutcome = "success" | "failed" | "blocked"

export type OutcomeBadgeVariant = "success" | "destructive" | "warning"

export type TestResultBadgeVariant = "success" | "destructive" | "warning" | "default"

export interface ParsedRemediationResult {
  outcome: RemediationOutcome | null
  root_cause: string | null
  implementation_summary: string | null
  blocker: string | null
  tests_performed: TestPerformed[]
  residual_risks: string[]
}

export interface TestDisplayRow {
  key: string
  label: string
  command: string | null
  statusText: string
  variant: TestResultBadgeVariant
}

const CATEGORY_LABELS: Record<TestCategory, string> = {
  pre_fix_reproduction: "Pre-fix reproduction",
  post_fix_validation: "Post-fix validation",
  regression_test: "Regression test",
  general_test: "General test",
  ci_validation: "GitHub CI",
}

export function formatOutcomeLabel(outcome: string | null | undefined): string | null {
  if (!outcome) return null
  switch (outcome.toLowerCase()) {
    case "success":
      return "SUCCESS"
    case "failed":
      return "FAILED"
    case "blocked":
      return "BLOCKED"
    default:
      return outcome.toUpperCase()
  }
}

export function getOutcomeBadgeVariant(
  outcome: string | null | undefined,
): OutcomeBadgeVariant {
  switch (outcome?.toLowerCase()) {
    case "success":
      return "success"
    case "failed":
      return "destructive"
    case "blocked":
      return "warning"
    default:
      return "warning"
  }
}

export function getTestResultBadgeVariant(result: string): TestResultBadgeVariant {
  switch (result.toLowerCase()) {
    case "passed":
      return "success"
    case "failed":
      return "destructive"
    case "skipped":
      return "warning"
    default:
      return "default"
  }
}

export function formatTestResultLabel(result: string): string {
  return result.replaceAll("_", " ").toUpperCase()
}

function truncateCommand(command: string, maxLength = 48): string {
  if (command.length <= maxLength) return command
  return `${command.slice(0, maxLength - 1)}…`
}

function formatTestStatusText(test: TestPerformed): { statusText: string; variant: TestResultBadgeVariant } {
  const result = test.result.toLowerCase()
  const category = test.category

  if (category === "pre_fix_reproduction" && result === "failed") {
    return { statusText: "Expected failure", variant: "success" }
  }

  switch (result) {
    case "passed":
      return { statusText: "Passed", variant: "success" }
    case "failed":
      return { statusText: "Failed", variant: "destructive" }
    case "skipped":
      return { statusText: "Skipped", variant: "warning" }
    case "not_run":
      return { statusText: "Not run", variant: "default" }
    default:
      return { statusText: formatTestResultLabel(test.result), variant: "default" }
  }
}

export function formatTestDisplay(test: TestPerformed, index: number): TestDisplayRow {
  const { statusText, variant } = formatTestStatusText(test)
  const label =
    test.category && test.category in CATEGORY_LABELS
      ? CATEGORY_LABELS[test.category]
      : truncateCommand(test.command)

  return {
    key: `${test.command}-${test.result}-${index}`,
    label,
    command: test.category ? test.command : null,
    statusText,
    variant,
  }
}

function formatCiValidationRow(task: Task): TestDisplayRow {
  const ciState = getCiSummaryState(task)
  switch (ciState) {
    case "running":
      return {
        key: "ci-validation",
        label: CATEGORY_LABELS.ci_validation,
        command: null,
        statusText: "Waiting",
        variant: "default",
      }
    case "passed":
      return {
        key: "ci-validation",
        label: CATEGORY_LABELS.ci_validation,
        command: null,
        statusText: "Passed",
        variant: "success",
      }
    case "failed":
      return {
        key: "ci-validation",
        label: CATEGORY_LABELS.ci_validation,
        command: null,
        statusText: "Failed",
        variant: "destructive",
      }
    default:
      return {
        key: "ci-validation",
        label: CATEGORY_LABELS.ci_validation,
        command: null,
        statusText: "Not run",
        variant: "default",
      }
  }
}

export function buildTestsPerformedRows(task: Task): TestDisplayRow[] {
  const result = parseRemediationResult(task)
  const rows = result.tests_performed.map((test, index) => formatTestDisplay(test, index))

  if (task.pr_url || task.ci_failure_at || task.status === "MERGED") {
    rows.push(formatCiValidationRow(task))
  }

  return rows
}

export function parseRemediationResult(task: Task): ParsedRemediationResult {
  const structured = parseStructuredResultPayload(task.structured_result_json)

  return {
    outcome: normalizeOutcome(task.remediation_outcome ?? structured.outcome),
    root_cause: task.root_cause ?? structured.root_cause,
    implementation_summary: task.implementation_summary ?? structured.implementation_summary,
    blocker: task.blocker ?? structured.blocker,
    tests_performed: structured.tests_performed,
    residual_risks: structured.residual_risks,
  }
}

function normalizeOutcome(value: string | null | undefined): RemediationOutcome | null {
  if (!value) return null
  const normalized = value.toLowerCase()
  if (normalized === "success" || normalized === "failed" || normalized === "blocked") {
    return normalized
  }
  return null
}

function parseStructuredResultPayload(
  structuredResultJson: string | null | undefined,
): {
  outcome: string | null
  root_cause: string | null
  implementation_summary: string | null
  blocker: string | null
  tests_performed: TestPerformed[]
  residual_risks: string[]
} {
  if (!structuredResultJson) {
    return {
      outcome: null,
      root_cause: null,
      implementation_summary: null,
      blocker: null,
      tests_performed: [],
      residual_risks: [],
    }
  }

  try {
    const parsed = JSON.parse(structuredResultJson) as {
      outcome?: string
      root_cause?: string
      implementation_summary?: string
      blocker?: string
      tests_performed?: TestPerformed[]
      residual_risks?: string[]
    }

    return {
      outcome: parsed.outcome ?? null,
      root_cause: parsed.root_cause ?? null,
      implementation_summary: parsed.implementation_summary ?? null,
      blocker: parsed.blocker ?? null,
      tests_performed: parsed.tests_performed ?? [],
      residual_risks: parsed.residual_risks ?? [],
    }
  } catch {
    return {
      outcome: null,
      root_cause: null,
      implementation_summary: null,
      blocker: null,
      tests_performed: [],
      residual_risks: [],
    }
  }
}

export function hasRemediationResult(task: Task): boolean {
  const result = parseRemediationResult(task)
  return Boolean(
    result.outcome ||
      result.root_cause ||
      result.implementation_summary ||
      result.blocker ||
      result.tests_performed.length > 0 ||
      result.residual_risks.length > 0,
  )
}

export function hasOperationalMetadata(task: Task): boolean {
  return Boolean(
    task.devin_session_id ||
      task.devin_session_url ||
      task.playbook_id ||
      task.devin_tags ||
      task.devin_origin ||
      task.devin_status ||
      task.failure_reason ||
      task.escalation_reason,
  )
}

export function displayValue(value: string | null | undefined): string {
  return value?.trim() ? value : "None"
}

export function getRemediationResultTitle(task: Task): string {
  return task.status === "MERGED" ? "Remediation Result" : "Devin Result"
}
