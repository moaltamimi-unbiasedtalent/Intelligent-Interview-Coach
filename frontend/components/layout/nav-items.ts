/** Candidate-facing primary navigation (deliberately focused). `labelKey` is the i18n
 * key; `label` is the English fallback used only if the catalogue is unavailable. */
export const PRIMARY_NAV = [
  { href: "/prepare", label: "Prepare", labelKey: "nav.prepare" },
  { href: "/practice", label: "Practice", labelKey: "nav.practice" },
  { href: "/progress", label: "Progress", labelKey: "nav.progress" },
  { href: "/history", label: "History", labelKey: "nav.history" },
] as const;

/**
 * Supporting destinations shown under "More" (kept out of the primary candidate path).
 * Settings is intentionally NOT here — it lives under the account control.
 */
export const SECONDARY_NAV = [
  { href: "/sources", label: "Sources", labelKey: "nav.sources", description: "Career evidence" },
  { href: "/help", label: "Help", labelKey: "nav.help", description: "How Ask4Mo works" },
  { href: "/review", label: "Review & Diagnostics", labelKey: "nav.review", description: "Technical inspection" },
] as const;

/** Account-related destination (reached via the avatar/account control, not "More"). */
export const ACCOUNT_NAV = { href: "/settings", label: "Settings", labelKey: "settings.title" } as const;
