import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Tone = "neutral" | "high" | "medium" | "low";

const tones: Record<Tone, string> = {
  neutral: "text-muted",
  high: "text-danger",
  medium: "text-warning",
  low: "text-success",
};

/** Status/severity chip. Always accompanied by text — never colour alone. */
export function Badge({
  tone = "neutral",
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-2 px-2.5 py-0.5 text-xs font-semibold",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
