export type FailureType =
  | "CODE_FAILURE"
  | "INFRA_FAILURE"
  | "TRANSIENT_FAILURE"
  | "UNKNOWN"

export function formatCiConclusion(conclusion: string | null): string {
  if (!conclusion) return "UNKNOWN"
  return conclusion.toUpperCase()
}

export function formatCiRepairStatus(
  failureType: string | null,
  repairAttempts: number,
  maxRepairAttempts: number,
  repairMessageSentAt: string | null,
  repairVerifiedAt: string | null,
): string {
  if (failureType && failureType !== "CODE_FAILURE") {
    return "No Devin repair"
  }
  if (repairVerifiedAt) {
    return `Repair verified (${repairAttempts}/${maxRepairAttempts})`
  }
  if (repairMessageSentAt) {
    return `Repair attempted (${repairAttempts}/${maxRepairAttempts})`
  }
  if (repairAttempts > 0) {
    return `Repair ${repairAttempts}/${maxRepairAttempts}`
  }
  return `Repair 0/${maxRepairAttempts}`
}

export function formatCiRepairLine(
  checkName: string | null,
  conclusion: string | null,
  failureType: string | null,
  repairAttempts: number,
  maxRepairAttempts: number,
  repairMessageSentAt: string | null = null,
  repairVerifiedAt: string | null = null,
  classificationReason: string | null = null,
): string | null {
  if (!checkName) return null
  const parts = [
    checkName,
    formatCiConclusion(conclusion),
    failureType ?? "UNKNOWN",
    formatCiRepairStatus(
      failureType,
      repairAttempts,
      maxRepairAttempts,
      repairMessageSentAt,
      repairVerifiedAt,
    ),
  ]
  if (classificationReason) {
    parts.push(classificationReason)
  }
  return parts.join(" · ")
}
