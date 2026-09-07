import type { ReactNode } from "react";
import { Button } from "@/components/ui/Button";

/**
 * A human-in-the-loop coaching moment (role confirm / memory consent / handoff).
 * A design shell for Phase 3B — the actual approvals arrive with the agent (later).
 */
export function HumanApprovalCard({
  title,
  description,
  confirmLabel,
  dismissLabel,
  children,
}: {
  title: string;
  description?: string;
  confirmLabel: string;
  dismissLabel?: string;
  children?: ReactNode;
}) {
  return (
    <div
      className="rounded-lg border border-dashed border-accent p-4"
      style={{ background: "color-mix(in srgb, var(--accent) 6%, var(--surface))" }}
    >
      <p className="font-semibold">{title}</p>
      {description ? <p className="mt-1 text-sm text-muted">{description}</p> : null}
      {children ? <div className="mt-3">{children}</div> : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm">{confirmLabel}</Button>
        {dismissLabel ? (
          <Button size="sm" variant="ghost">
            {dismissLabel}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
