"use client";

import { useCallback, useEffect, useState } from "react";
import { useT } from "@/components/i18n/I18nProvider";
import { Card, CardBody } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { StatusChip } from "@/components/plan/StatusChip";
import { api } from "@/lib/api/client";
import type { ModelProfilesResponse } from "@/lib/api/types";

/**
 * AI model-profile presentation (W12.4D-P3) over the backend catalogue (GET /model-profiles). Read-only information: it NEVER renders a selector, shows no provider
 * model id, no price and no comparative quality claim. While the server reports `selector_active: false` it says model selection is not available yet and that
 * Practice keeps its current profile; when it is active it shows only what the SERVER authorized. The client holds no profile-to-plan rule.
 */
export function ModelProfilePanel() {
  const t = useT();
  const [data, setData] = useState<ModelProfilesResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const load = useCallback(() => {
    setFailed(false);
    api.modelProfiles.get().then((r) => (r && Array.isArray(r.profiles) ? setData(r) : setFailed(true))).catch(() => setFailed(true));
  }, []);
  useEffect(load, [load]);
  if (failed) return <ErrorState variant="section" message={t("planUx.models_loadError")} onRetry={load} />;
  if (!data) return <LoadingState label={t("planUx.models_title")} />;
  const names: Record<string, string> = { fast: "planUx.models_fast", balanced: "planUx.models_balanced", advanced: "planUx.models_advanced" };
  const desc: Record<string, string> = { fast: "planUx.models_descFast", balanced: "planUx.models_descBalanced", advanced: "planUx.models_descAdvanced" };
  return (
    <Card>
      <CardBody className="space-y-3" data-testid="model-profiles" data-selector-active={data.selector_active ? "true" : "false"}>
        <h2 className="text-base font-semibold text-foreground">{t("planUx.models_title")}</h2>
        <p className="text-sm text-muted">{data.selector_active ? t("planUx.models_leadActive") : t("planUx.models_leadInactive")}</p>
        <ul className="grid gap-2" aria-label={t("planUx.models_groupLabel")}>
          {data.profiles.filter((p) => names[p.id]).map((p) => (
            <li key={p.id} className="rounded-lg border border-border bg-surface p-3" data-profile={p.id} data-authorized={p.authorized ? "true" : "false"}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-foreground">{t(names[p.id])}</p>
                {data.selector_active ? (
                  <span className="flex flex-wrap gap-1.5">
                    <StatusChip status={p.authorized ? "available" : "entitlement"} label={t(p.authorized ? "planUx.models_available" : "planUx.models_notAvailable")} />
                    {p.authorized && data.default === p.id ? <StatusChip status="planned" label={t("planUx.models_isDefault")} /> : null}
                  </span>
                ) : null}
              </div>
              <p className="mt-1 text-sm text-muted">{t(desc[p.id])}</p>
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted">{t("planUx.models_noClaims")}</p>
      </CardBody>
    </Card>
  );
}
