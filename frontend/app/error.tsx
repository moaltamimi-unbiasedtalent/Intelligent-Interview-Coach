"use client";

import { useEffect } from "react";
import { useT } from "@/components/i18n/I18nProvider";
import { ErrorState } from "@/components/ui/States";

/**
 * Route error boundary (P10B-W9.7A). Reached only for an unexpected render/runtime failure that no
 * in-page recovery handled - the one genuinely "fatal" tier, so it keeps the large `fatal` treatment
 * (every ordinary recoverable read error uses the proportional `page`/`section` tiers instead). It is
 * localized (previously Next's default English screen), exposes only Next's opaque `digest` as the
 * support reference (never the message or stack), and `reset()` re-renders the segment in place.
 */
export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useT();
  useEffect(() => {
    // Keep the raw error out of the UI; surface to the console for developers only.
    console.error(error);
  }, [error]);
  return (
    <div className="mx-auto max-w-content px-5 py-12">
      <ErrorState variant="fatal" message={t("states.serverError")} requestId={error.digest ?? null} onRetry={reset} />
    </div>
  );
}
