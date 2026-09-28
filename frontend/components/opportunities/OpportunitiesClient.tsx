"use client";

/**
 * Opportunities list (P10B Wave 6).
 *
 * The candidate's home for the jobs they are preparing for. Each Opportunity groups a role +
 * company + JD and links to Company Intelligence, Prepare, Practice and reports. Owner-scoped;
 * private by default; distinct from a Workspace (collaboration). All copy localized; no emoji,
 * no em dash.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { Opportunity } from "@/lib/api/types";
import { useI18n } from "@/components/i18n/I18nProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { EmptyState, EmptyStateIllustration, ErrorState, LoadingState } from "@/components/ui/States";
import { OpportunityStatusBadge } from "@/components/opportunities/OpportunityStatusBadge";
import { OpportunityCreate } from "@/components/opportunities/OpportunityCreate";

export function OpportunitiesClient() {
  const { t } = useI18n();
  const [items, setItems] = useState<Opportunity[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.opportunities.list(showArchived);
      setItems(res.opportunities);
    } catch (err) {
      setItems([]);
      setError(err instanceof ApiError ? err.message : t("opportunity.errorLoad"));
    }
  }, [showArchived, t]);

  useEffect(() => {
    void load();
  }, [load]);

  if (creating) {
    return (
      <OpportunityCreate
        onCancel={() => setCreating(false)}
        onCreated={() => {
          setCreating(false);
          void load();
        }}
      />
    );
  }

  return (
    <section className="mx-auto max-w-content space-y-6">
      <PageHeader
        title={t("opportunity.listTitle")}
        description={t("opportunity.listSubtitle")}
        actions={<Button onClick={() => setCreating(true)}>{t("opportunity.create")}</Button>}
      />

      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={() => setShowArchived((v) => !v)}
          className="text-sm font-medium text-accent hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2"
        >
          {showArchived ? t("opportunity.hideArchived") : t("opportunity.showArchived")}
        </button>
      </div>

      {items === null ? (
        <LoadingState label={t("opportunity.listTitle")} />
      ) : error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : items.length === 0 ? (
        <EmptyState
          title={t("opportunity.emptyTitle")}
          description={t("opportunity.emptyBody")}
          illustration={
            <EmptyStateIllustration
              src="/images/ask4mo/ask4mo-empty-opportunities-ink.png"
              alt="An open hand-drawn folder ready for role, company and evidence cards."
            />
          }
          action={<Button onClick={() => setCreating(true)}>{t("opportunity.create")}</Button>}
        />
      ) : (
        <ul className="grid gap-3">
          {items.map((o) => (
            <li key={o.id}>
              <Link
                href={`/opportunities/${o.id}`}
                className="block rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2"
              >
                <Card>
                  <CardBody className="flex items-center justify-between gap-3">
                    <span className="min-w-0">
                      <span className="block truncate font-semibold text-foreground">{o.title}</span>
                      <span className="block truncate text-sm text-muted">
                        {[o.company_name, o.company_location].filter(Boolean).join(" · ") || o.target_role}
                      </span>
                    </span>
                    <OpportunityStatusBadge status={o.status} />
                  </CardBody>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
