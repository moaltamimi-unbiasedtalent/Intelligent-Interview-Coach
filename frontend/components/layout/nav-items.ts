/** Candidate-facing primary navigation (locked in Phase 3A IA). */
export const PRIMARY_NAV = [
  { href: "/prepare", label: "Prepare" },
  { href: "/practice", label: "Practice" },
  { href: "/progress", label: "Progress" },
  { href: "/history", label: "History" },
] as const;

/** Supporting / secondary destinations (kept out of the primary candidate path). */
export const SECONDARY_NAV = [
  { href: "/sources", label: "Sources" },
  { href: "/review", label: "Review & Diagnostics" },
  { href: "/settings", label: "Settings" },
] as const;
