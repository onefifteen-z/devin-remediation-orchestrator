import type { Metrics } from "@/types/metrics"
import type { ScanResult } from "@/types/scan"
import type { Task, TaskListResponse } from "@/types/task"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init)
  if (!response.ok) {
    let detail = `API request failed: ${response.status}`
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // ignore JSON parse errors
    }
    throw new ApiError(detail, response.status)
  }
  return response.json() as Promise<T>
}

export async function fetchHealth(): Promise<{ status: string }> {
  return request("/health")
}

export async function fetchMetrics(): Promise<Metrics> {
  return request("/api/metrics")
}

export async function fetchTasks(): Promise<TaskListResponse> {
  return request("/api/tasks")
}

export async function fetchTask(taskId: number): Promise<Task> {
  return request(`/api/tasks/${taskId}`)
}

export async function scanGitHubIssues(): Promise<ScanResult> {
  return request("/api/scan/github", { method: "POST" })
}

export { API_BASE_URL, ApiError }
