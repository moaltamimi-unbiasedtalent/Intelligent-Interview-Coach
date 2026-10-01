"use client";

import { Badge } from "@/components/ui/Badge";
import { useT } from "@/components/i18n/I18nProvider";

export interface RoleContextData {
  role: string;
  seniority?: string;
  geography?: string;
  company?: string;
  readiness?: number | null;
}

/** Role strip + readiness ring. Values are demo/empty until Phase 3C wiring. */
export function RoleContext({ data }: { data: RoleContextData }) {
  const t = useT();
  return (
    <div className="flex flex-wrap items-center gap-3">
      <h2 className="text-xl font-semibold">{data.role}</h2>
      {data.seniority ? <Badge>{data.seniority}</Badge> : null}
      {data.geography ? <Badge>{data.geography}</Badge> : null}
      {data.company ? <Badge>{data.company}</Badge> : null}
      {typeof data.readiness === "number" ? (
        <span className="ml-auto flex items-center gap-2">
          <span className="text-sm text-muted">{t("prepare.readiness")}</span>
          <ReadinessRing value={data.readiness} />
        </span>
      ) : null}
    </div>
  );
}

function ReadinessRing({ value }: { value: number }) {
  const t = useT();
  return (
    <span
      className="relative grid h-11 w-11 place-items-center rounded-full"
      style={{
        background: `conic-gradient(var(--accent) ${value}%, var(--surface-2) 0)`,
      }}
      role="img"
      aria-label={t("prepare.readinessAria", { value })}
    >
      <span className="absolute grid h-8 w-8 place-items-center rounded-full bg-surface text-xs font-bold tabular-nums">
        {value}
      </span>
    </span>
  );
}
