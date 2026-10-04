"use client";

import { useState } from "react";
import type { ReactNode } from "react";
import { ConfirmDialogBase } from "@/components/ui/ConfirmDialogBase";
import { apiMessage, field } from "./ui";

/**
 * Accessible confirmation for a governed admin write. Cancel is the focused default (ConfirmDialog),
 * the optional reason is audited, a failure is shown inside the dialog and the write is never auto-retried.
 */
export function ActionDialog({
  open, title, confirmLabel, children, onConfirm, onClose, askReason = true, reasonRequired = false, testId,
}: {
  open: boolean;
  title: string;
  confirmLabel: string;
  children: ReactNode;
  onConfirm: (reason: string) => Promise<void>;
  onClose: () => void;
  askReason?: boolean;
  /** The reason is mandatory (a governed change that the server also requires a reason for). */
  reasonRequired?: boolean;
  testId?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const close = () => {
    setError(null);
    setReason("");
    onClose();
  };
  const confirm = async () => {
    if (reasonRequired && !reason.trim()) {
      setError("A reason is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onConfirm(reason.trim());
      setReason("");
      onClose();
    } catch (e) {
      setError(apiMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <ConfirmDialogBase open={open} title={title} confirmLabel={confirmLabel} cancelLabel="Cancel" busyLabel="Working..." busy={busy}
      error={error} onConfirm={confirm} onCancel={close} testId={testId}>
      {children}
      {askReason ? (
        <label className="grid gap-1 text-xs text-muted">
          {reasonRequired ? "Reason (required, recorded in the audit log)" : "Reason (optional, recorded in the audit log)"}
          <input className={field} value={reason} maxLength={200} onChange={(e) => setReason(e.target.value)} />
        </label>
      ) : null}
    </ConfirmDialogBase>
  );
}
