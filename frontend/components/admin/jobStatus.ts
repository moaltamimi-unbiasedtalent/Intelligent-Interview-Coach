import type { JobRow, JobState } from "@/lib/admin/types";

export const STATE_LABEL: Record<JobState, string> = {
  queued: "Queued", running: "Running", succeeded: "Succeeded", failed: "Failed", cancelled: "Cancelled",
};
export const ERROR_LABEL: Record<string, string> = {
  transient: "Temporary error", timeout: "Timed out", rate_limited: "Rate limited", unavailable: "Service unavailable",
  invalid_payload: "Invalid input", configuration_error: "Configuration problem", unsupported: "Unsupported",
  unknown_job_type: "Unknown job type", lease_expired: "Worker stopped responding", internal_error: "Unexpected error",
};
export const label = (v: string) => v.replace(/_/g, " ");

/** Text first, never colour-only. */
export function stateText(j: Pick<JobRow, "state" | "waiting_for_retry" | "lease">): string {
  if (j.state === "queued" && j.waiting_for_retry) return "Queued (waiting to retry)";
  if (j.state === "running" && j.lease.stale) return "Running (lease expired)";
  return STATE_LABEL[j.state];
}
