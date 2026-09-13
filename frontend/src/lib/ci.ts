export type FailureType =
  | "CODE_FAILURE"
  | "INFRA_FAILURE"
  | "TRANSIENT_FAILURE"
  | "UNKNOWN"

export function formatCiConclusion(conclusion: string | null): string {
  if (!conclusion) return "UNKNOWN"
  return conclusion.toUpperCase()
}

export function formatCiRepairLine(
  checkName: string | null,
  conclusion: string | null,
  failureType: string | null,
  repairAttempts: number,
  maxRepairAttempts: number,
): string | null {
  if (!checkName) return null
  const parts = [
    checkName,
    formatCiConclusion(conclusion),
    failureType ?? "UNKNOWN",
    `Repair ${repairAttempts}/${maxRepairAttempts}`,
  ]
  return parts.join(" · ")
}
