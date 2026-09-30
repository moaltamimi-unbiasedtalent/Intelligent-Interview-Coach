import Image from "next/image";
import type { ReactNode } from "react";
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

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <span className="sr-only">{label}</span>
      <Skeleton className="h-6 w-2/5" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-24 w-3/4" />
    </div>
  );
}

/**
 * Recoverable error state (P10B-W9.1 taxonomy + W9.2 in-place recovery).
 *
 * - `variant="page"` (default): the full-width catastrophic card (unchanged visual system).
 * - `variant="section"`: a compact, non-catastrophic inline error for one degraded region of
 *   an otherwise-usable page (so a single failed read never blanks the whole page).
 * - `onRetry` renders a keyboard-accessible Retry control; while `retrying` it is disabled and
 *   marked `aria-busy` so repeated clicks cannot stack concurrent loads.
 * - `requestId` stays available as secondary technical detail; no internal detail is exposed.
 * Callers pass an already-localized `message` (e.g. `t(stateKeyForError(err.kind))`).
 */
export function ErrorState({
  message,
  requestId,
  onRetry,
  retrying = false,
  retryLabel = "Try again",
  retryingLabel = "Retrying…",
  variant = "page",
}: {
  message: string;
  requestId?: string | null;
  onRetry?: () => void;
  retrying?: boolean;
  retryLabel?: string;
  retryingLabel?: string;
  variant?: "page" | "section";
}) {
  const isSection = variant === "section";
  const retry = onRetry ? (
    <button
      type="button"
      onClick={onRetry}
      disabled={retrying}
      aria-busy={retrying}
      className={
        (isSection ? "mt-2 min-h-[36px] px-3" : "mt-5 min-h-[40px] px-4") +
        " rounded border border-border text-sm font-semibold hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-60"
      }
    >
      {retrying ? retryingLabel : retryLabel}
    </button>
  ) : null;
  const details = requestId ? (
    <details
      className={
        "mt-3 max-w-reading text-xs text-muted" + (isSection ? " text-left" : " mx-auto text-left")
      }
    >
      <summary className="cursor-pointer">Technical details</summary>
      <p className="mt-1">Reference: {requestId}</p>
    </details>
  ) : null;

  if (isSection) {
    // Compact inline error for a single page region. Deliberately NOT a giant catastrophic card.
    return (
      <div role="alert" className="rounded-md border border-border bg-surface px-4 py-3">
        <p className="text-sm text-muted">{message}</p>
        {retry}
        {details}
      </div>
    );
  }

  return (
    <div role="alert" className="rounded-lg border border-danger bg-surface px-6 py-10 text-center">
      <h2 className="text-lg font-semibold">Something went wrong</h2>
      <p className="mx-auto mt-2 max-w-reading text-muted">{message}</p>
      {retry}
      {details}
    </div>
  );
}
