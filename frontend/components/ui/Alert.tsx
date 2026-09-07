import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Tone = "info" | "warning" | "danger";

const tones: Record<Tone, string> = {
  info: "border-border",
  warning: "border-warning",
  danger: "border-danger",
};

export function Alert({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: Tone;
  title?: string;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={cn(
        "rounded-lg border bg-surface-2 px-4 py-3 text-sm",
        tones[tone],
        className,
      )}
    >
      {title ? <p className="font-semibold text-foreground">{title}</p> : null}
      {children ? <div className="text-muted">{children}</div> : null}
    </div>
  );
}
