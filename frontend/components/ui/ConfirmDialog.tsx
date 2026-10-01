"use client";

import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";
import { useT } from "@/components/i18n/I18nProvider";

/**
 * Accessible confirmation dialog for destructive or access-changing actions (P10B-W9.8).
 *
 * - `role="alertdialog"` + `aria-modal`, labelled by its title and described by its body.
 * - Initial focus lands on **Cancel** (the safe default), never on the destructive button.
 * - Focus is trapped inside while open; Escape and the backdrop cancel (unless an action is running).
 * - Focus returns to the element that opened it. Background scrolling is locked while open.
 * - While `busy` both buttons are disabled so a destructive write cannot be fired twice; a failed action
 *   shows `error` inside the dialog (role="alert") and leaves it open. Writes are never auto-retried.
 * Destructive intent is conveyed by text + the danger-bordered confirm button, not by colour alone.
 */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  cancelLabel,
  busy = false,
  error,
  onConfirm,
  onCancel,
  testId,
}: {
  open: boolean;
  title: string;
  children?: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  busy?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
  testId?: string;
}) {
  const t = useT();
  const titleId = useId();
  const descId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const opener = useRef<Element | null>(null);
  const busyRef = useRef(busy);
  busyRef.current = busy;

  useEffect(() => {
    if (!open) return;
    opener.current = document.activeElement;
    cancelRef.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
      if (opener.current instanceof HTMLElement) opener.current.focus();
    };
  }, [open]);

  if (!open) return null;

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      if (!busyRef.current) onCancel();
      return;
    }
    if (e.key !== "Tab") return;
    const focusable = panelRef.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
    );
    if (!focusable || focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-3 sm:items-center"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !busy) onCancel();
      }}
    >
      <div
        ref={panelRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        data-testid={testId}
        onKeyDown={onKeyDown}
        className="max-h-[90vh] w-full max-w-[480px] overflow-y-auto rounded-lg border border-border bg-surface p-5 shadow-lg"
      >
        <h2 id={titleId} className="text-lg font-semibold text-foreground">
          {title}
        </h2>
        <div id={descId} className="mt-3 space-y-3 text-sm text-muted [overflow-wrap:anywhere]">
          {children}
        </div>
        {error ? (
          <p role="alert" className="mt-3 rounded border border-danger px-3 py-2 text-sm text-foreground">
            {error}
          </p>
        ) : null}
        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            ref={cancelRef}
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="min-h-[44px] rounded border border-border px-4 text-sm font-semibold text-foreground hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2 disabled:opacity-50"
          >
            {cancelLabel ?? t("common.cancel")}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            aria-busy={busy}
            className="min-h-[44px] rounded border-2 border-danger bg-surface px-4 text-sm font-semibold text-foreground hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2 disabled:opacity-50"
          >
            {busy ? t("dataPrivacy.working") : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
