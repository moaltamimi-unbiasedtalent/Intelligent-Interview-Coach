"use client";

import { useEffect, useMemo, useState } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { isBulkUserPreview, isBulkUserResult } from "@/lib/admin/bulkGuard";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { BulkUserActionName, BulkUserPreview, BulkUserResult } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { Panel, apiMessage, btn, field } from "./ui";

export const BULK_MAX = 100;

const ACTIONS: { code: BulkUserActionName; label: string; permission: string; effect: string }[] = [
  { code: "force-signout", label: "Force sign-out", permission: P.sessionsRevoke, effect: "ends every live session; each person can sign in again" },
  { code: "expire-verification", label: "Expire pending email verification links", permission: P.usersManage, effect: "invalidates outstanding verification links; a new link can be requested at any time" },
];

const REASONS: Record<string, string> = {
  self: "your own account",
  higher_authority: "accounts holding more authority than you",
  last_active_platform_admin: "the last active platform administrator",
  not_found: "ids that do not exist",
  no_live_sessions: "accounts with no live session",
  no_pending_verification: "accounts with no pending verification link",
  apply_error: "accounts the server could not change",
};
const reasonLabel = (code: string) => REASONS[code] ?? code;
const listCounts = (c: Record<string, number>) => Object.entries(c).filter(([, n]) => n > 0).map(([k, n]) => `${n} ${reasonLabel(k)}`);

const MALFORMED = "The server answered with an unexpected response. Preview again to check the current state before doing anything else.";

function newKey(): string {
  const c = typeof crypto !== "undefined" ? crypto : undefined;
  return c && "randomUUID" in c ? `bulk-${c.randomUUID()}` : `bulk-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/**
 * Bulk Admin user actions (03C; OD-BULK-ACTIONS is a provisional recommendation, not an approval). Only two low-harm, reversible actions are offered. The flow is
 * select -> preview (counts only, never who) -> confirm with a mandatory reason -> result with applied, skipped and failed counts. A malformed 200 is the explicit error
 * state, never a silent success. The Idempotency-Key is created with the preview and kept for that preview, so a retry after a network failure replays the first result.
 */
export function UsersBulkPanel({ selected, onClear }: { selected: number[]; onClear: () => void }) {
  const granted = adminPermissions(useAuthOptional()?.account);
  const allowed = useMemo(() => ACTIONS.filter((a) => hasAnyPermission(granted, [a.permission])), [granted]);
  const [action, setAction] = useState<BulkUserActionName | "">("");
  const [preview, setPreview] = useState<BulkUserPreview | null>(null);
  const [result, setResult] = useState<BulkUserResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [key, setKey] = useState("");
  const idsKey = selected.join(",");

  // Any change to the selection or the action invalidates the preview: the server would refuse it as stale anyway.
  useEffect(() => {
    setPreview(null);
    setError(null);
  }, [idsKey, action]);

  if (allowed.length === 0 || selected.length === 0) return null;
  const chosen = ACTIONS.find((a) => a.code === action);

  const runPreview = async () => {
    setError(null);
    setResult(null);
    setPreview(null);
    if (!chosen) return setError("Choose an action first.");
    if (selected.length > BULK_MAX) return setError(`Select at most ${BULK_MAX} accounts.`);
    try {
      const out = await api.admin.bulkUserPreview(chosen.code, selected);
      if (!isBulkUserPreview(out) || out.action !== chosen.code) throw new Error(MALFORMED);
      setPreview(out);
      setKey(newKey());
    } catch (e) {
      setError(apiMessage(e));
    }
  };

  const confirm = async (reason: string) => {
    if (!preview || !chosen) return;
    if (reason.length < 3 || reason.length > 200) throw new Error("The reason must be 3 to 200 characters.");
    const out = await api.admin.bulkUserExecute(chosen.code, { account_ids: selected, preview_revision: preview.preview_revision, reason }, key);
    if (!isBulkUserResult(out) || out.action !== chosen.code) throw new Error(MALFORMED);
    setResult(out);
    setPreview(null);
  };

  return (
    <Panel title="Bulk actions on the selected accounts">
      <p className="text-xs text-muted">
        {`${selected.length} selected (at most ${BULK_MAX}). Only low-harm, reversible actions are offered here. Deactivation, deletion, role and plan changes are never done in bulk. The preview shows counts only, never who.`}
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="grid gap-1 text-xs text-muted">
          Action
          <select className={field} value={action} onChange={(e) => { setAction(e.target.value as BulkUserActionName | ""); setResult(null); }}>
            <option value="">Choose an action</option>
            {allowed.map((a) => <option key={a.code} value={a.code}>{a.label}</option>)}
          </select>
        </label>
        <button type="button" className={btn} disabled={!chosen} onClick={runPreview}>Preview effect</button>
        <button type="button" className={btn} onClick={() => { setPreview(null); setResult(null); setError(null); onClear(); }}>Clear selection</button>
      </div>
      {error ? <p role="alert" className="text-sm">{error}</p> : null}
      {preview && chosen ? (
        <div className="grid gap-2" aria-live="polite">
          <p role="status" className="text-sm">
            {`Preview: ${preview.eligible} of ${preview.unique} accounts would be changed, ${preview.excluded} excluded.`}
          </p>
          {preview.excluded > 0 ? <p className="text-xs text-muted">{`Excluded: ${listCounts(preview.excluded_by_reason).join(", ")}.`}</p> : null}
          <div>
            <button type="button" className={btn} disabled={preview.eligible === 0} onClick={() => setOpen(true)}>
              {`Apply to ${preview.eligible} accounts`}
            </button>
          </div>
        </div>
      ) : null}
      {result ? (
        <div role="status" className="grid gap-1 rounded border border-border px-3 py-2 text-sm" aria-live="polite">
          <p className="font-medium">
            {result.status === "complete" ? "Completed: every account was changed." : result.status === "partial" ? "Partly applied: some accounts were not changed." : "Nothing was changed."}
            {result.replayed ? " (This is the result of the earlier identical request.)" : ""}
          </p>
          <p>{`Applied ${result.applied}, skipped ${result.skipped}, failed ${result.failed}.`}</p>
          {result.skipped > 0 ? <p className="text-xs text-muted">{`Skipped: ${listCounts(result.skipped_by_reason).join(", ")}.`}</p> : null}
          {result.failed > 0 ? <p className="text-xs text-muted">{`Failed: ${listCounts(result.failed_by_reason).join(", ")}. Preview again and retry for those accounts.`}</p> : null}
          <p className="text-xs text-muted">Every account has its own entry in the audit log, plus one entry for the batch.</p>
        </div>
      ) : null}
      <ActionDialog open={open} title={chosen ? `${chosen.label} for ${preview?.eligible ?? 0} accounts?` : "Apply?"} confirmLabel="Apply" askReason reasonRequired
        onClose={() => setOpen(false)} onConfirm={confirm}>
        <p>{chosen && preview ? `This ${chosen.effect}. ${preview.eligible} accounts will change; ${preview.excluded} are excluded by the protection rules.` : ""}</p>
        <p>Accounts are changed one by one: if one cannot be changed the others still are, and the result lists every outcome. If the audit log cannot be written, nothing is applied.</p>
      </ActionDialog>
    </Panel>
  );
}
