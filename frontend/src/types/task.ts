export type TaskStatus =
  | "RECEIVED"
  | "SESSION_CREATED"
  | "RUNNING"
  | "PR_OPENED"
  | "CI_FAILED"
  | "READY_FOR_REVIEW"
  | "MERGED"
  | "COMPLETED"
  | "FAILED"
  | "ESCALATED"

export type TestCategory =
  | "pre_fix_reproduction"
  | "post_fix_validation"
  | "regression_test"
  | "general_test"
  | "ci_validation"

export interface TestPerformed {
  command: string
  result: "passed" | "failed" | "skipped" | "not_run"
  category?: TestCategory | null
}

export interface StructuredResultPayload {
  tests_performed?: TestPerformed[]
  residual_risks?: string[]
  pr_url?: string | null
  raw?: Record<string, unknown>
}

export interface InsightsClassification {
  category: string | null
  confidence: number | null
  programming_languages: string[]
  tools_and_frameworks: string[]
}

export interface InsightsIssue {
  id: string
  title: string
  issue: string
  impact: string
  label: string
}

export interface InsightsTimelineEvent {
  title: string
  description: string
  color: string
  issue_id: string | null
}

export interface InsightsActionItem {
  action_item: string
  type: string
  issue_id: string | null
}

export interface Task {
  id: number
  github_delivery_id: string
  github_repository: string
  github_issue_number: number
  github_issue_url: string
  issue_title: string
  issue_type: string
  issue_labels: string | null
  task_kind: string
  trigger_source: string | null
  devin_session_id: string | null
  devin_session_url: string | null
  devin_status: string | null
  devin_status_detail: string | null
  devin_origin: string | null
  devin_service_user_id: string | null
  devin_tags: string | null
  status: TaskStatus
  pr_url: string | null
  pr_state: string | null
  retry_count: number
  max_retries: number
  started_at: string | null
  completed_at: string | null
  merged_at: string | null
  failure_reason: string | null
  completion_reason: string | null
  escalation_reason: string | null
  failure_type: string | null
  ci_classification_reason: string | null
  ci_check_name: string | null
  ci_check_url: string | null
  ci_conclusion: string | null
  ci_failure_at: string | null
  ci_repair_attempts: number
  max_ci_repair_attempts: number
  last_ci_check_run_id: number | null
  ci_repair_message_sent_at: string | null
  ci_repair_verified_at: string | null
  ci_passed_at: string | null
  ci_non_code_failure_count: number
  acu_used: number | null
  acu_source: string | null
  acu_verified: boolean
  session_size: string | null
  num_user_messages: number | null
  num_devin_messages: number | null
  insights_status: string | null
  insights_json: string | null
  remediation_outcome: string | null
  root_cause: string | null
  implementation_summary: string | null
  structured_result_json: string | null
  blocker: string | null
  playbook_id: string | null
  created_at: string
  updated_at: string
  mttr_seconds: number | null
}

export interface TaskListResponse {
  items: Task[]
  total: number
}
