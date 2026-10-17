"use client";

import { useCallback, useEffect, useState } from "react";
import { useI18n } from "@/components/i18n/I18nProvider";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { PackAvailability, PackDetail, PackSummary } from "@/lib/api/types";
import { PreparationPackView } from "@/components/opportunities/PreparationPackView";

/**
 * Preparation Pack area of the Opportunity page (W12.4D-P5-A). It shows what the SERVER reports: saved Packs are always listed, readable and downloadable
 * (never plan-gated), and a Generate button exists ONLY when the server says generation is available. While generation is disabled or not entitled it says so
 * in plain words with no button, no purchase link and no price. The component grants nothing and holds no plan rule.
 */
export function PreparationPackSection({ opportunityId }: { opportunityId: number }) {
  const { t, formatDate } = useI18n();
  const [packs, setPacks] = useState<PackSummary[] | null>(null);
  const [availability, setAvailability] = useState<PackAvailability["generation"] | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<PackDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setFailed(false);
    try {
      const [list, av] = await Promise.all([api.preparationPacks.list(opportunityId), api.preparationPacks.availability(opportunityId)]);
      if (!list || !Array.isArray(list.packs)) throw new Error("bad");
      setPacks(list.packs);
      setAvailability(av && typeof av.generation === "string" ? av.generation : null);
    } catch {
      setFailed(true);
    }
  }, [opportunityId]);
  useEffect(() => { void load(); }, [load]);

  const generate = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const key = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : String(Date.now());
      await api.preparationPacks.generate(opportunityId, key);
    } catch (err) {
      setMessage(err instanceof ApiError && err.status === 403 ? t("packUx.unavailableNow") : t("packUx.generateError"));
    } finally {
      setBusy(false);
      await load();
    }
  };

  const view = async (id: number) => {
    try {
      setOpen(await api.preparationPacks.get(id));
    } catch {
      setMessage(t("packUx.loadError"));
    }
  };

  const remove = async (id: number) => {
    if (!window.confirm(t("packUx.deleteConfirm"))) return;
    try {
      await api.preparationPacks.remove(id);
      if (open?.id === id) setOpen(null);
    } finally {
      await load();
    }
  };

  const failLabel = (code: string | null) => {
    const k = `packUx.fail_${code ?? "other"}`;
    const v = t(k);
    return v === k ? t("packUx.fail_other") : v;
  };

  return (
    <Card>
      <CardBody className="space-y-3" data-testid="pack-section">
        <section aria-labelledby="pack-title" className="space-y-3">
          <h2 id="pack-title" className="text-lg font-semibold text-foreground">{t("packUx.title")}</h2>
          <p className="text-sm text-muted">{t("packUx.intro")}</p>
          <p className="text-xs text-muted" data-testid="pack-disclaimer">{t("packUx.disclaimer")}</p>
          {failed ? (
            <p role="alert" className="text-sm text-muted">{t("packUx.loadError")} <button type="button" className="font-medium text-accent hover:underline" onClick={() => void load()}>{t("states.retry")}</button></p>
          ) : null}
          {availability ? (
            <div className="space-y-2" data-testid="pack-availability" data-generation={availability}>
              <p className="text-sm text-foreground">{t(`packUx.avail_${availability}`)}</p>
              {availability === "available" ? (
                <>
                  <p className="text-xs text-muted">{t("packUx.generateHint")}</p>
                  <Button onClick={() => void generate()} disabled={busy} aria-busy={busy}>{busy ? t("packUx.generating") : t("packUx.generate")}</Button>
                </>
              ) : null}
            </div>
          ) : null}
          {message ? <p role="status" className="text-sm text-muted">{message}</p> : null}
          {packs !== null ? (
            <div>
              <h3 className="text-sm font-semibold text-foreground">{t("packUx.savedTitle")}</h3>
              {packs.length === 0 ? <p className="mt-1 text-sm text-muted" data-testid="pack-empty">{t("packUx.noPacks")}</p> : (
                <ul className="mt-2 space-y-2" data-testid="pack-list">
                  {packs.map((p) => (
                    <li key={p.id} className="rounded-lg border border-border bg-surface p-3 text-sm" data-pack-id={p.id} data-status={p.status}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-medium text-foreground">{t("packUx.revision", { n: p.revision })} · {t(`packUx.st_${p.status}`)}
                          {p.created_at ? <span className="ml-2 text-xs font-normal text-muted">{formatDate(p.created_at, { dateStyle: "medium" })}</span> : null}</p>
                        <div className="flex flex-wrap gap-2">
                          {p.status === "completed" || p.status === "insufficient_evidence" ? (
                            <>
                              <Button variant="ghost" onClick={() => void view(p.id)}>{t("packUx.open")}</Button>
                              <a href={api.preparationPacks.downloadUrl(p.id, "md")} download className="inline-flex min-h-[44px] items-center text-sm font-medium text-accent hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">{t("packUx.downloadMd")}</a>
                              <a href={api.preparationPacks.downloadUrl(p.id, "json")} download className="inline-flex min-h-[44px] items-center text-sm font-medium text-accent hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">{t("packUx.downloadJson")}</a>
                            </>
                          ) : null}
                          <Button variant="ghost" onClick={() => void remove(p.id)}>{t("packUx.delete")}</Button>
                        </div>
                      </div>
                      {p.status === "failed" ? <p className="mt-1 text-xs text-muted">{failLabel(p.failure_category)} {t("packUx.failedNote")}</p> : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : null}
          {open && open.content ? (
            <div className="space-y-2" data-testid="pack-open">
              <div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-foreground">{t("packUx.revision", { n: open.revision })}</h3>
                <Button variant="ghost" onClick={() => setOpen(null)}>{t("packUx.close")}</Button></div>
              <PreparationPackView content={open.content} />
            </div>
          ) : null}
        </section>
      </CardBody>
    </Card>
  );
}
