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

export function ErrorState({
  message,
  requestId,
  onRetry,
}: {
  message: string;
  requestId?: string | null;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="rounded-lg border border-danger bg-surface px-6 py-10 text-center">
      <h2 className="text-lg font-semibold">Something went wrong</h2>
      <p className="mx-auto mt-2 max-w-reading text-muted">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 min-h-[40px] rounded border border-border px-4 text-sm font-semibold hover:bg-surface-2"
        >
          Try again
        </button>
      ) : null}
      {requestId ? (
        <details className="mx-auto mt-4 max-w-reading text-left text-xs text-muted">
          <summary className="cursor-pointer">Technical details</summary>
          <p className="mt-1">Reference: {requestId}</p>
        </details>
      ) : null}
    </div>
  );
}
