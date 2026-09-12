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
  total_acu: number
  average_acu_per_task: number
  failed_tasks: number
  escalated_tasks: number
}
