import type { BulkUserPreview, BulkUserResult } from "./types";

const ACTIONS = new Set(["force-signout", "expire-verification"]);
const STATUSES = new Set(["complete", "partial", "none_applied"]);

const num = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v) && v >= 0;
const counts = (v: unknown): v is Record<string, number> =>
  !!v && typeof v === "object" && !Array.isArray(v) && Object.values(v as Record<string, unknown>).every(num);

/**
 * Runtime checks of the 03C bulk responses. A successful HTTP response without the documented shape (a proxy answering `{}`, contract drift) must surface as the explicit
 * Admin error state, never as a crash, never as a silent "0 applied" success.
 */
export function isBulkUserPreview(value: unknown): value is BulkUserPreview {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.action === "string" && ACTIONS.has(v.action) &&
    num(v.requested) && num(v.unique) && num(v.eligible) && num(v.excluded) && num(v.max_batch) &&
    counts(v.excluded_by_reason) &&
    typeof v.preview_revision === "string" && /^[0-9a-f]{8,32}$/.test(v.preview_revision) &&
    v.eligible + v.excluded === v.unique
  );
}

export function isBulkUserResult(value: unknown): value is BulkUserResult {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.action === "string" && ACTIONS.has(v.action) &&
    typeof v.batch_id === "string" && v.batch_id.length > 0 &&
    typeof v.status === "string" && STATUSES.has(v.status) &&
    num(v.requested) && num(v.unique) && num(v.applied) && num(v.skipped) && num(v.failed) &&
    counts(v.skipped_by_reason) && counts(v.failed_by_reason) &&
    typeof v.replayed === "boolean" &&
    v.applied + v.skipped + v.failed === v.unique
  );
}
