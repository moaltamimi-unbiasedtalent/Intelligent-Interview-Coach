export const STATE_LABEL: Record<string, string> = {
  draft: "Draft", validated: "Validated", evaluated: "Evaluated (passed)", evaluation_failed: "Evaluation failed", approved: "Approved",
  rejected: "Rejected", retired: "Retired",
};
export const KIND_LABEL: Record<string, string> = { activate: "Activated", rollback: "Rolled back", revert_to_code: "Reverted to code defaults" };
export const SOURCE_LABEL: Record<string, string> = {
  governed_configuration: "Governed configuration", environment_override: "Environment override", code_default: "Code default",
};
export const TUNABLE_LABEL: Record<string, string> = { max_output_tokens: "Max output tokens", timeout_s: "Timeout (seconds)", max_retries: "Max retries" };
export const label = (v: string) => v.replace(/_/g, " ");
export const shortHash = (h: string | null | undefined) => (h ? h.slice(0, 12) : "none");
