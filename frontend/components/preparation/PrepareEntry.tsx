"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useCapabilities } from "@/lib/useCapabilities";
import { useI18n, useT } from "@/components/i18n/I18nProvider";
import { LoadingState } from "@/components/ui/States";
import { PrepareWorkspace } from "@/components/preparation/PrepareWorkspace";
import { AgentPrepareWorkspace } from "@/components/agent/AgentPrepareWorkspace";
import { clearPrepareDraft, readPrepareDraft } from "@/lib/prepareDraft";

/**
 * Deployment-controlled cutover (Phase 9): when the backend advertises
 * `agent_coach_enabled`, /prepare uses the LangGraph-powered Agent Coach; otherwise
 * it stays on the proven deterministic Career flow (safe rollback). This is NOT a
 * user-facing "agent/legacy" toggle.
 *
 * A transient Home → Prepare draft (if any) is read ONCE here and handed to whichever
 * experience is active — Home never needs to know which one that is. The draft value
 * lives in component state from this point, so it is cleared from storage promptly
 * (§10) while remaining available for the active workspace to consume (§11).
 */
export function PrepareEntry() {
  const t = useT();
  const { capabilities, loading } = useCapabilities();
  const [initialDraft] = useState(() => readPrepareDraft());

  // The value is captured above; remove it from storage so it can't leak into a
  // later visit. The active workspace still receives it via props.
  useEffect(() => {
    clearPrepareDraft();
  }, []);

  if (loading) return <LoadingState label={t("prepare.loadingWorkspace")} />;
  return (
    <div className="space-y-4">
      {capabilities.company_research_enabled ? <CompanyResearchLink /> : null}
      {capabilities.agent_coach_enabled ? (
        <AgentPrepareWorkspace initialDraft={initialDraft} />
      ) : (
        <PrepareWorkspace initialDraft={initialDraft} />
      )}
    </div>
  );
}

/** Discoverable entry point (P10B Wave 5): a restrained link to the Company Intelligence
 * experience from the top of Prepare (fixes the founder's "couldn't find company research"). */
function CompanyResearchLink() {
  const { t } = useI18n();
  return (
    <Link
      href="/company"
      className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3 hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2"
    >
      <span>
        <span className="block text-sm font-semibold text-foreground">{t("company.title")}</span>
        <span className="block text-sm text-muted">{t("company.subtitle")}</span>
      </span>
      <span aria-hidden className="shrink-0 text-accent">&rarr;</span>
    </Link>
  );
}
