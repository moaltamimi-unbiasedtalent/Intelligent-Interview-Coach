"use client";

import Image from "next/image";
import { useLayoutEffect, useRef } from "react";
import type { ReactNode } from "react";
import { useT } from "@/components/i18n/I18nProvider";
import { Skeleton } from "./Skeleton";

/**
 * P10B Wave 8 B0: transparent ink-and-gouache spot illustration for a true empty state.
 * Intended to be passed to `EmptyState`'s `illustration` prop. Centered, no coloured tile,
 * ~280px on mobile and ~360px on desktop; the source PNGs carry their own alpha transparency.
 */
export function EmptyStateIllustration({ src, alt }: { src: string; alt: string }) {
  return (
    <Image
      src={src}
      alt={alt}
      width={1448}
      height={1086}
      sizes="(max-width: 640px) 280px, 360px"
      className="h-auto w-[280px] max-w-full sm:w-[360px]"
    />
  );
}

export function EmptyState({
  title,
  description,
  action,
  illustration,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  // P10B Wave 8 B0: optional spot illustration shown above the title for true empty states.
  // Backward-compatible - callers that omit it render exactly as before.
  illustration?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-surface px-6 py-14 text-center">
      {illustration ? <div className="mb-5 flex justify-center">{illustration}</div> : null}
      <h2 className="text-lg font-semibold">{title}</h2>
      {description ? (
        <p className="mx-auto mt-2 max-w-reading text-muted">{description}</p>
      ) : null}
      {action ? <div className="mt-5 flex justify-center">{action}</div> : null}
    </div>
  );
}

export function LoadingState({ label }: { label?: string }) {
  const t = useT();
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <span className="sr-only">{label ?? t("states.loading")}</span>
      <Skeleton className="h-6 w-2/5" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-24 w-3/4" />
    </div>
  );
}

/**
 * Recoverable error state (P10B-W9.1 taxonomy + W9.2 in-place recovery + W9.7A visual hierarchy).
 *
 * Three tiers - the size of the card matches the severity of the failure, so a recoverable read error
 * never looks like a catastrophic application crash:
 * - `variant="section"`: one degraded REGION of an otherwise-usable page. Compact inline note.
 * - `variant="page"` (default): the page's primary read could not render, but the app is healthy and the
 *   user can retry. A proportional card (left danger accent, small title, inline Retry) - NOT a
 *   viewport-sized block.
 * - `variant="fatal"`: reserved for a genuinely unrecoverable render/runtime failure (the route error
 *   boundary `app/error.tsx`). The only place that keeps the large centred treatment.
 * - `onRetry` renders a keyboard-accessible Retry control; while `retrying` it is disabled and marked
 *   `aria-busy` so repeated clicks cannot stack concurrent loads. If Retry succeeds while it holds focus,
 *   focus moves to the main region (the focused button is removed, so focus would otherwise drop to <body>).
 * - `requestId` stays available as secondary technical detail inside a COLLAPSED disclosure; no internal
 *   detail is exposed. The error semantics (what is shown, retried, classified) are unchanged.
 * Callers pass an already-localized `message` (e.g. `t(stateKeyForError(err.kind))`).
 */
export function ErrorState({
  message,
  requestId,
  onRetry,
  retrying = false,
  retryLabel,
  retryingLabel,
  variant = "page",
}: {
  message: string;
  requestId?: string | null;
  onRetry?: () => void;
  retrying?: boolean;
  retryLabel?: string;
  retryingLabel?: string;
  variant?: "page" | "section" | "fatal";
}) {
  const t = useT();
  const retryRef = useRef<HTMLButtonElement>(null);
  const activated = useRef(false);
  // When a Retry the user activated succeeds, this card unmounts. While the retry is in flight the button is
  // `disabled`, and browsers then drop focus to <body>, so "does the button still hold focus" is the wrong
  // test. Instead: if Retry was activated and focus is on the button or has fallen to <body> (i.e. the user
  // has not moved it elsewhere), hand focus to the main region. Layout-effect cleanup runs before removal.
  useLayoutEffect(() => {
    const btn = retryRef.current;
    return () => {
      if (!activated.current || typeof document === "undefined") return;
      const active = document.activeElement;
      if (active === btn || active === document.body || active === null) {
        document.getElementById("main")?.focus();
      }
    };
  }, []);
  const retryText = retryLabel ?? t("states.retry");
  const retryingText = retryingLabel ?? t("states.retrying");
  const isSection = variant === "section";
  const isFatal = variant === "fatal";
  const retry = onRetry ? (
    <button
      ref={retryRef}
      type="button"
      onClick={() => {
        activated.current = true;
        onRetry?.();
      }}
      disabled={retrying}
      aria-busy={retrying}
      className={
        (isSection
          ? "mt-2 min-h-[36px] border border-border px-3 hover:bg-surface-2"
          : isFatal
            ? "mt-5 min-h-[40px] border border-border px-4 hover:bg-surface-2"
            : "min-h-[40px] bg-accent px-4 text-accent-foreground hover:brightness-[1.06]") +
        " rounded text-sm font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
      }
    >
      {retrying ? retryingText : retryText}
    </button>
  ) : null;
  const details = requestId ? (
    <details
      className={"max-w-reading text-xs text-muted " + (isFatal ? "mx-auto mt-3 text-left" : "mt-3 text-left")}
    >
      <summary className="cursor-pointer rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2">
        {t("states.technicalDetails")}
      </summary>
      <p className="mt-1 break-all">{t("states.reference")} {requestId}</p>
    </details>
  ) : null;

  if (isSection) {
    // Compact inline error for a single page region. Deliberately NOT a big card.
    return (
      <div role="alert" className="rounded-md border border-border bg-surface px-4 py-3">
        <p className="text-sm text-muted">{message}</p>
        {retry}
        {details}
      </div>
    );
  }

  if (isFatal) {
    return (
      <div role="alert" className="rounded-lg border border-danger bg-surface px-6 py-10 text-center">
        <h2 className="text-lg font-semibold">{t("states.somethingWentWrong")}</h2>
        <p className="mx-auto mt-2 max-w-reading text-muted">{message}</p>
        {retry}
        {details}
      </div>
    );
  }

  // Page-level recoverable failure: proportional, left-aligned, danger accent on the left edge only.
  return (
    <div
      role="alert"
      data-error-variant="page"
      className="rounded-lg border border-border border-l-4 border-l-danger bg-surface px-5 py-4"
    >
      <h2 className="text-base font-semibold text-foreground">{t("states.somethingWentWrong")}</h2>
      <p className="mt-1 max-w-reading text-sm text-muted">{message}</p>
      {retry ? <div className="mt-3">{retry}</div> : null}
      {details}
    </div>
  );
}
