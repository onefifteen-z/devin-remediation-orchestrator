export interface ThroughputPoint {
  date: string
  count: number
  by_source?: Record<string, number>
}

export interface OrgUsageMetrics {
  sessions_count: number
  searches_count: number
  prs_created_count: number
  prs_merged_count: number
}

export interface OrgPrMetrics {
  prs_created_count: number
  prs_opened_count: number
  prs_merged_count: number
  prs_closed_count: number
  prs_taken_over_count: number
  prs_taken_over_opened_count: number
  prs_taken_over_merged_count: number
  prs_taken_over_closed_count: number
}

export interface OrgSessionMetrics {
  sessions_created_count: number
  sessions_created_by_size: Record<string, number>
  sessions_created_by_origin: Record<string, number>
  sessions_created_with_playbook_count: number
  sessions_created_with_search_count: number
  sessions_with_merged_prs_count: number
  sessions_with_merged_prs_by_size: Record<string, number>
  avg_acus_per_session: number
}

export interface DevinOrgMetrics {
  window_start: number
  window_end: number
  usage: OrgUsageMetrics
  pull_requests: OrgPrMetrics
  sessions: OrgSessionMetrics
  active_users: number
  peak_dau: number
  peak_wau: number
  peak_mau: number
}

export interface Metrics {
  total_tasks: number
  active_tasks: number
  success_rate: number
  merge_rate: number
  median_mttr_seconds: number | null
  throughput_7d: number
  throughput_by_day: ThroughputPoint[]
  ci_recovery_rate: number
  tasks_with_ci_failures: number
  code_ci_failures: number
  transient_ci_failures: number
  infra_ci_failures: number
  unknown_ci_failures: number
  ci_repair_attempts: number
  ci_repair_successes: number
  total_acu: number
  average_acu_per_task: number
  verified_total_acu: number
  average_verified_acu_per_task: number
  consumption_api_available: boolean | null
  devin_org_total_acus: number | null
  devin_org_metrics: DevinOrgMetrics | null
  org_metrics_window_days: number
  tasks_with_prs: number
  failed_tasks: number
  escalated_tasks: number
}
