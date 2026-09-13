export type TaskStatus =
  | "RECEIVED"
  | "SESSION_CREATED"
  | "RUNNING"
  | "PR_OPENED"
  | "CI_FAILED"
  | "READY_FOR_REVIEW"
  | "MERGED"
  | "FAILED"
  | "ESCALATED"

export interface Task {
  id: number
  github_delivery_id: string
  github_repository: string
  github_issue_number: number
  github_issue_url: string
  issue_title: string
  issue_type: string
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
  escalation_reason: string | null
  acu_used: number | null
  created_at: string
  updated_at: string
  mttr_seconds: number | null
}

export interface TaskListResponse {
  items: Task[]
  total: number
}
