import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** One turn in the preparation conversation. Presentational only in Phase 3B. */
export function CoachMessage({
  from,
  children,
}: {
  from: "coach" | "you";
  children: ReactNode;
}) {
  const isCoach = from === "coach";
  return (
    <div className="grid gap-1.5">
      <span className="text-xs font-semibold text-muted">{isCoach ? "Coach" : "You"}</span>
      <div
        className={cn(
          "rounded-lg px-4 py-3.5",
          isCoach
            ? "border border-border bg-surface shadow-soft"
            : "justify-self-end bg-surface-2",
        )}
        style={isCoach ? { borderLeft: "3px solid var(--accent)" } : undefined}
      >
        {children}
      </div>
    </div>
  );
}

/** Safe, observable activity label — never chain-of-thought. */
export function CoachActivity({ label }: { label: string }) {
  return (
    <p className="flex items-center gap-2.5 py-0.5 text-sm text-muted" aria-live="polite">
      <span className="h-2 w-2 animate-pulse rounded-full bg-accent" aria-hidden="true" />
      {label}
    </p>
  );
}
