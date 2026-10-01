"use client";

/**
 * Authenticated-home Opportunity entry (P10B-W9.4, Pilot PF-10).
 *
 * The primary job-centric action on Home: it explains the Opportunity concept in plain candidate
 * language ("keep everything for one job in one place") and offers one obvious action. It is placed
 * BEFORE the general Prepare composer so the job-context mental model is discoverable without a
 * moderator — but it does NOT force Opportunity creation (Prepare stays available below).
 *
 * Adaptive from EXISTING owner-scoped data (no new backend): a best-effort read of the existing
 * Opportunities list decides first-use vs returning emphasis. On loading/error it safely defaults to
 * the "create" action. The loading placeholder is bounded: it shows only while auth or the list request is
 * genuinely pending (and gives up after LOADING_CAP_MS), never after the request settles or auth fails
 * (P10B-W9.7A: a failed `/auth/me` used to leave an unlabeled blank rectangle forever). It reuses the EXISTING creation flow via `/opportunities?create=1` (which opens
 * the existing inline create form) — no second creation implementation. `data-tour="opportunity-entry"`
 * is a stable target for the future Tutorial v2 (W9.5); no tutorial behaviour is added here.
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { useT } from "@/components/i18n/I18nProvider";
import { Card, CardBody } from "@/components/ui/Card";
import { ButtonLink } from "@/components/ui/Button";

// Upper bound for the loading placeholder; after it, the safe default action is shown.
const LOADING_CAP_MS = 4000;

export function OpportunityEntry() {
  const status = useAuthOptional()?.status ?? "unauthenticated";
  const t = useT();
  // null = not yet resolved; number = count of (active) opportunities the candidate owns.
  const [count, setCount] = useState<number | null>(null);
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    if (status !== "authenticated") {
      setCount(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await api.opportunities.list();
        if (!cancelled) setCount(res.opportunities?.length ?? 0);
      } catch {
        // Best-effort only: never break Home. Default to the create action.
        if (!cancelled) setCount(0);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [status]);

  // Pending = auth still resolving, or authenticated and the list has not settled. Any other state
  // (auth failed/unknown/unauthenticated, list failed, or the cap elapsed) renders the safe default.
  const pending = !gaveUp && (status === "loading" || (status === "authenticated" && count === null));

  useEffect(() => {
    if (!pending) return;
    const id = window.setTimeout(() => setGaveUp(true), LOADING_CAP_MS);
    return () => window.clearTimeout(id);
  }, [pending]);

  const hasOpportunities = (count ?? 0) > 0;

  return (
    <Card data-tour="opportunity-entry">
      <CardBody className="space-y-3">
        <div className="space-y-1">
          <h2 className="text-lg font-bold text-foreground">{t("home.opportunityTitle")}</h2>
          <p className="max-w-reading text-sm text-muted">{t("home.opportunityBody")}</p>
        </div>
        {/* Actions render once resolved, so a returning user never sees a brief wrong CTA. While pending
            a labelled, bounded placeholder is shown (never an unlabeled blank control). */}
        {pending ? (
          <div role="status" aria-live="polite" data-testid="opportunity-entry-loading">
            <span className="sr-only">{t("states.loading")}</span>
            <div aria-hidden="true" className="h-10 w-48 animate-pulse rounded bg-surface-2" />
          </div>
        ) : hasOpportunities ? (
          <div className="flex flex-wrap items-center gap-3">
            <ButtonLink href="/opportunities">{t("home.opportunityView")}</ButtonLink>
            <ButtonLink href="/opportunities?create=1" variant="ghost">
              {t("home.opportunityCreateAnother")}
            </ButtonLink>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <ButtonLink href="/opportunities?create=1">{t("home.opportunityCreate")}</ButtonLink>
            <ButtonLink href="/opportunities" variant="ghost">
              {t("home.opportunityView")}
            </ButtonLink>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
