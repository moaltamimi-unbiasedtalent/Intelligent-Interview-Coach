"use client";

import { useRef, useState } from "react";
import type { ReactNode } from "react";
import { ConfirmDialogBase } from "@/components/ui/ConfirmDialogBase";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { apiMessage, field } from "./ui";

/**
 * Password confirmation ("step-up") for high-risk Admin actions. This is password RE-AUTHENTICATION of the current session, not MFA.
 * The password lives only in this form's state while the dialog is open; it is cleared on every close and never stored, logged or sent anywhere
 * except the confirmation request. The server owns the elevation (a short window bound to this session); the browser holds no token.
 */
export function useStepUp(): { run: <T>(action: () => Promise<T>) => Promise<T>; dialog: ReactNode } {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const waiter = useRef<{ resolve: () => void; reject: (e: unknown) => void } | null>(null);

  const close = () => {
    setPassword("");
    setError(null);
    setOpen(false);
    waiter.current?.reject(new Error("Password confirmation was cancelled."));
    waiter.current = null;
  };

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.admin.stepUp(password);
      setPassword("");
      setOpen(false);
      waiter.current?.resolve();
      waiter.current = null;
    } catch (e) {
      setError(e instanceof ApiError && e.code === "step_up_unavailable"
        ? "Password confirmation is not available for this account or session. OIDC re-authentication is not validated."
        : apiMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const run = async <T,>(action: () => Promise<T>): Promise<T> => {
    try {
      return await action();
    } catch (e) {
      if (!(e instanceof ApiError) || e.code !== "step_up_required") throw e;
    }
    await new Promise<void>((resolve, reject) => {
      waiter.current = { resolve, reject };
      setOpen(true);
    });
    return action();
  };

  const dialog = (
    <ConfirmDialogBase open={open} title="Confirm your password to continue" confirmLabel="Confirm" cancelLabel="Cancel" busyLabel="Checking..." busy={busy}
      error={error} onConfirm={confirm} onCancel={close} testId="step-up-dialog">
      <p className="text-sm">This action needs a recent password confirmation. It lasts a few minutes for this session only.</p>
      <label className="grid gap-1 text-xs text-muted">
        Current password
        <input type="password" autoComplete="current-password" className={field} value={password} onChange={(e) => setPassword(e.target.value)} />
      </label>
    </ConfirmDialogBase>
  );
  return { run, dialog };
}
