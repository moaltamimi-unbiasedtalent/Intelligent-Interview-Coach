/** Candidate-facing primary navigation (deliberately focused). `labelKey` is the i18n
 * key; `label` is the English fallback used only if the catalogue is unavailable. */
export const PRIMARY_NAV = [
  { href: "/opportunities", label: "Opportunities", labelKey: "nav.opportunities" },
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
  { href: "/company", label: "Company research", labelKey: "nav.company", description: "Research an employer" },
  { href: "/documents", label: "Documents", labelKey: "documents.title", description: "Your private evidence" },
  { href: "/workspaces", label: "Workspaces", labelKey: "workspaces.nav", description: "Teams & explicit sharing" },
  { href: "/sources", label: "Sources", labelKey: "nav.sources", description: "Career evidence" },
  { href: "/help", label: "Help", labelKey: "nav.help", description: "How Ask4Mo works" },
] as const;

/**
 * INTERNAL platform-admin-only destinations (P10B-W9.3). Shown in "More" ONLY to a
 * server-authoritative PLATFORM_ADMIN — never to anonymous or ordinary candidates. Review &
 * Diagnostics (RAG + evaluation engineering surfaces) and Admin operations live here.
 * Hiding these is UX defense-in-depth; each destination's backend is independently authorized.
 * Note: the candidate's OWN Agent Inspector (`/review/agent`) is reached via the Coach's
 * "View run details" link and stays owner-scoped/candidate-accessible — it is deliberately NOT
 * gated here.
 */
export const INTERNAL_NAV = [
  // `anyOf`: visible when the server-resolved admin permissions include ANY of these (W10.1; UX only).
  { href: "/review", label: "Review & Diagnostics", labelKey: "nav.review", description: "Technical inspection",
    anyOf: ["platform.ai.read", "platform.knowledge.read"] },
  // Admin uses an English label by design (internal operations surface, §14) — no labelKey.
  { href: "/admin", label: "Admin", description: "Platform operations", anyOf: ["platform.overview.read"] },
] as const;

/** Account-related destination (reached via the avatar/account control, not "More"). */
export const ACCOUNT_NAV = { href: "/settings", label: "Settings", labelKey: "settings.title" } as const;
