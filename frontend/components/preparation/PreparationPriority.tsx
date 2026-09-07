import { Badge } from "@/components/ui/Badge";

export type Severity = "high" | "medium" | "low";

const SEVERITY_LABEL: Record<Severity, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};
const SEVERITY_MARK: Record<Severity, string> = {
  high: "▲",
  medium: "▲",
  low: "▲",
};

export interface Priority {
  title: string;
  severity: Severity;
  note?: string;
}

/** A gap/priority row. Severity is shown with an icon + label, never colour alone. */
export function PreparationPriority({ priority }: { priority: Priority }) {
  const tone = priority.severity;
  return (
    <div className="flex items-start gap-3 border-t border-border py-3 first:border-t-0">
      <span
        aria-hidden="true"
        className={
          tone === "high"
            ? "mt-0.5 text-danger"
            : tone === "medium"
              ? "mt-0.5 text-warning"
              : "mt-0.5 text-success"
        }
      >
        {SEVERITY_MARK[tone]}
      </span>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{priority.title}</span>
          <Badge tone={tone}>{SEVERITY_LABEL[tone]}</Badge>
        </div>
        {priority.note ? (
          <p className="mt-0.5 text-sm text-muted">{priority.note}</p>
        ) : null}
      </div>
    </div>
  );
}
