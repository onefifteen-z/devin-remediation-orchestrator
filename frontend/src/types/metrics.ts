export interface ThroughputPoint {
  date: string
  count: number
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
  tasks_with_prs: number
  failed_tasks: number
  escalated_tasks: number
}
