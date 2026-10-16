import { cn } from "@/lib/utils";
import type { CapabilityStatus } from "@/lib/plan/capabilities";

const tone: Record<Exclude<CapabilityStatus, "none">, string> = {
  available: "border-success/40 bg-success/10 text-foreground",
  entitlement: "border-accent/40 bg-accent/10 text-foreground",
  planned: "border-border bg-surface-2 text-muted",
  pending: "border-warning/50 bg-warning/10 text-foreground",
  unavailable: "border-danger/40 bg-danger/10 text-foreground",
};

/** A status pill. The status is ALWAYS spelled out in text (never colour alone) and carries a small non-colour marker so it survives greyscale and forced colours. */
export function StatusChip({ status, label }: { status: Exclude<CapabilityStatus, "none">; label: string }) {
  const marker = { available: "●", entitlement: "◐", planned: "○", pending: "◌", unavailable: "▲" }[status];
  return (
    <span data-status={status} className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium leading-5", tone[status])}>
      <span aria-hidden="true">{marker}</span>
      <span>{label}</span>
    </span>
  );
}
