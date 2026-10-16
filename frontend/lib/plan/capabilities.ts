// The owner-approved Basic/Premium target matrix (W12.4D-P1-A, final decisions) as PRESENTATION DATA ONLY. It never decides access: every real decision is made by the
// backend (entitlements, history window, model-profile policy). Each cell carries its own TRUTHFUL status so a planned or inactive item can never read as live.
//
//   available    - works for the candidate today
//   entitlement  - the rule exists in the product but is not active; it applies once plans are active (rollout gates are off)
//   planned      - not built yet
//   pending      - waiting for commercial activation (allowances or prices that are not approved)
//   unavailable  - an operational outage (never used for a plan restriction)
//   none         - not part of this plan (no status chip)
export type CapabilityStatus = "available" | "entitlement" | "planned" | "pending" | "unavailable" | "none";

export interface CapabilityCell {
  textKey: string;
  status: CapabilityStatus;
}
export interface Capability {
  id: number;
  basic: CapabilityCell;
  premium: CapabilityCell;
}

const c = (textKey: string, status: CapabilityStatus): CapabilityCell => ({ textKey, status });
const P = "planUx.cell_";

export const CAPABILITIES: readonly Capability[] = [
  { id: 1, basic: c(P + "practiceBasic", "available"), premium: c(P + "practicePremium", "pending") },
  { id: 2, basic: c(P + "included", "available"), premium: c(P + "included", "available") },
  { id: 3, basic: c(P + "included", "available"), premium: c(P + "included", "available") },
  { id: 4, basic: c(P + "included", "available"), premium: c(P + "included", "available") },
  { id: 5, basic: c(P + "included", "available"), premium: c(P + "included", "available") },
  { id: 6, basic: c(P + "historyBasic", "entitlement"), premium: c(P + "historyPremium", "entitlement") },
  { id: 7, basic: c(P + "progressBasic", "entitlement"), premium: c(P + "progressPremium", "planned") },
  { id: 8, basic: c(P + "researchBasic", "available"), premium: c(P + "researchPremium", "pending") },
  { id: 9, basic: c(P + "notIncluded", "none"), premium: c(P + "included", "planned") },
  { id: 10, basic: c(P + "notIncluded", "none"), premium: c(P + "packPremium", "planned") },
  { id: 11, basic: c(P + "modelBasic", "entitlement"), premium: c(P + "modelPremium", "entitlement") },
  { id: 12, basic: c(P + "savedBoth", "available"), premium: c(P + "savedBoth", "available") },
  { id: 13, basic: c(P + "voiceBasic", "none"), premium: c(P + "voicePremium", "planned") },
] as const;

export const STATUS_ORDER: readonly Exclude<CapabilityStatus, "none">[] = ["available", "entitlement", "planned", "pending", "unavailable"];
export const statusKey = (s: Exclude<CapabilityStatus, "none">) => `planUx.status_${s}`;
export const capabilityLabelKey = (id: number) => `planUx.cap_${id}`;
