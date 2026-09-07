import type { ReactNode } from "react";
import { Skeleton } from "./Skeleton";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-surface px-6 py-14 text-center">
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
