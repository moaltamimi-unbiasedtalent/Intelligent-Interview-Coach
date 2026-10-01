"use client";

import type { AgentRunResponse } from "@/lib/api/types";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { useT } from "@/components/i18n/I18nProvider";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</h3>
      <div className="mt-1 text-sm">{children}</div>
    </div>
  );
}

/**
 * The Precision Coach context rail: real, evolving preparation state derived from
 * the agent run — never raw internal state. Keeps Mo feeling like a real coach with
 * evolving context, not a generic Q&A box.
 */
export function AgentContextRail({ run }: { run: AgentRunResponse }) {
  const t = useT();
  const ctx = run.preparation_context ?? null;
  const role = ctx?.target_role ?? run.resolved_occupation ?? null;
  const strengths = ctx?.candidate_strengths ?? [];
  const gaps = ctx?.candidate_gaps ?? [];
  const priorities = ctx?.priority_competencies ?? [];

  return (
    <Card>
      <CardBody className="space-y-4">
        <h2 className="text-sm font-semibold">{t("prepare.yourPreparation")}</h2>

        <Section title={t("prepare.targetRole")}>
          {role ? <span className="font-medium">{role}</span> : <span className="text-muted">{t("prepare.notSetYet")}</span>}
        </Section>

        {strengths.length ? (
          <Section title={t("prepare.strengths")}>
            <ul className="flex flex-wrap gap-1.5">
              {strengths.slice(0, 6).map((s, i) => <li key={i}><Badge tone="low">{s}</Badge></li>)}
            </ul>
          </Section>
        ) : null}

        {(priorities.length ? priorities : gaps).length ? (
          <Section title={t("prepare.priorityGaps")}>
            <ul className="flex flex-wrap gap-1.5">
              {(priorities.length ? priorities : gaps).slice(0, 6).map((g, i) => <li key={i}><Badge tone="high">{g}</Badge></li>)}
            </ul>
          </Section>
        ) : null}

        <Section title={t("prepare.preparationPlan")}>
          {ctx ? <span className="text-muted">{t("prepare.planReadyWith", { role: role ?? t("prepare.roleWord") })}</span> : <span className="text-muted">{t("prepare.notBuiltYet")}</span>}
        </Section>

        <Section title={t("prepare.careerEvidence")}>
          {run.retrieval_used ? (
            <span className="text-muted">{t(run.sources.length === 1 ? "prepare.sourcesConsidered_one" : "prepare.sourcesConsidered_other", { count: run.sources.length })}</span>
          ) : (
            <span className="text-muted">{t("prepare.noneYet")}</span>
          )}
        </Section>

        {run.memory_used ? (
          <Section title={t("prepare.savedPreparation")}>
            <span className="text-muted">{t(run.memory_count === 1 ? "prepare.savedNotes_one" : "prepare.savedNotes_other", { count: run.memory_count })}</span>
          </Section>
        ) : null}
      </CardBody>
    </Card>
  );
}
