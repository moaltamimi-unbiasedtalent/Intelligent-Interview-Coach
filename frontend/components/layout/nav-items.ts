/** Candidate-facing primary navigation (deliberately focused). */
export const PRIMARY_NAV = [
  { href: "/prepare", label: "Prepare" },
  { href: "/practice", label: "Practice" },
  { href: "/progress", label: "Progress" },
  { href: "/history", label: "History" },
] as const;

/**
 * Supporting destinations shown under "More" (kept out of the primary candidate path).
 * Settings is intentionally NOT here — it lives under the account control.
 */
export const SECONDARY_NAV = [
  { href: "/sources", label: "Sources", description: "Career evidence" },
  { href: "/review", label: "Review & Diagnostics", description: "Technical inspection" },
] as const;

/** Account-related destination (reached via the avatar/account control, not "More"). */
export const ACCOUNT_NAV = { href: "/settings", label: "Settings" } as const;
