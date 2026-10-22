import type { AdminInvitationPage } from "./types";

const STATES = new Set(["pending", "redeemed", "expired", "revoked"]);

/**
 * Runtime check of the Admin invitation listing (04E). A successful HTTP response that does not have the documented shape (a proxy answering `{}`, a contract drift) must
 * surface as the explicit Admin error state, never as a crash and never as a silently empty list.
 */
export function isAdminInvitationPage(value: unknown): value is AdminInvitationPage {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  if (!Array.isArray(v.items) || typeof v.total !== "number") return false;
  if (!v.counts || typeof v.counts !== "object" || Array.isArray(v.counts)) return false;
  if (!Object.values(v.counts as Record<string, unknown>).every((n) => typeof n === "number")) return false;
  return v.items.every((row) => {
    if (!row || typeof row !== "object") return false;
    const r = row as Record<string, unknown>;
    return typeof r.id === "number" && typeof r.state === "string" && STATES.has(r.state);
  });
}
