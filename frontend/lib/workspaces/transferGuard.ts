import { ApiError } from "../api/errors";
import type { OwnershipTransfer, OwnershipTransferList, OwnershipTransferPreview, OwnershipTransferState, StepUpStateLike } from "../api/types";

/**
 * Runtime checks of the ownership-transfer responses (04B completion). A successful HTTP response that does not have the documented shape (a proxy answering `{}`,
 * a contract drift) must surface as the explicit error state, never as a crash and never as a silently empty "no transfer" success: a wrongly empty answer would hide
 * a pending transfer from its recipient or its proposer.
 */

const FORMER_ROLES = new Set(["workspace_admin", "workspace_member"]);
const VIEWER_ROLES = new Set(["proposer", "recipient"]);
const STATES = new Set(["pending", "accepted", "declined", "cancelled", "expired"]);

function rec(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

export function isTransfer(value: unknown): value is OwnershipTransfer {
  const v = rec(value);
  if (!v) return false;
  return (
    typeof v.id === "number" &&
    typeof v.workspace_id === "number" &&
    typeof v.status === "string" && STATES.has(v.status) &&
    typeof v.viewer_role === "string" && VIEWER_ROLES.has(v.viewer_role) &&
    typeof v.former_owner_role === "string" && FORMER_ROLES.has(v.former_owner_role) &&
    typeof v.counterpart_label === "string" &&
    (v.expires_at === null || typeof v.expires_at === "string") &&
    (v.workspace_name === undefined || typeof v.workspace_name === "string") &&
    (v.email_delivery === undefined || v.email_delivery === "submitted" || v.email_delivery === "not_submitted")
  );
}

export function isTransferState(value: unknown): value is OwnershipTransferState {
  const v = rec(value);
  return !!v && "transfer" in v && (v.transfer === null || isTransfer(v.transfer));
}

export function isTransferList(value: unknown): value is OwnershipTransferList {
  const v = rec(value);
  return !!v && Array.isArray(v.transfers) && v.transfers.every(isTransfer);
}

export function isTransferPreview(value: unknown): value is OwnershipTransferPreview {
  return isTransfer(value) && typeof (value as unknown as Record<string, unknown>).workspace_name === "string";
}

export function isStatusOf(value: unknown, status: string): boolean {
  const v = rec(value);
  return !!v && v.status === status;
}

export function isStepUpStateLike(value: unknown): value is StepUpStateLike {
  const v = rec(value);
  return !!v && typeof v.elevated === "boolean" && typeof v.window_seconds === "number";
}

/** The workspace returned after an accepted transfer: only what the page needs to link to it. */
export function isWorkspaceRef(value: unknown): value is { id: number; name: string; owner_user_id: number } {
  const v = rec(value);
  return !!v && typeof v.id === "number" && typeof v.name === "string" && typeof v.owner_user_id === "number";
}

export function malformedResponse(): ApiError {
  return new ApiError({ kind: "unknown", status: null, code: "malformed_response", message: "The service answered in an unexpected format." });
}

export function checked<T>(value: unknown, ok: (v: unknown) => v is T): T {
  if (!ok(value)) throw malformedResponse();
  return value;
}
