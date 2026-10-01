"use client";

import type { EvaluationOut } from "@/lib/api/types";
import { Card, CardBody } from "@/components/ui/Card";
import { useT } from "@/components/i18n/I18nProvider";

/**
 * Candidate-safe answer feedback. Practice guidance only — never a hiring decision.
 * Renders exactly the fields the backend provides (no invented metrics). The panel
 * stays visible after evaluation so the candidate can read it before choosing to go
 * deeper or move on. Only the Ask4Mo-owned chrome (headings, section titles,
 * disclaimer) is localized; the evaluation text itself follows the conversation language.
 */
export function InterviewEvaluation({ evaluation, heading }: {
  evaluation: EvaluationOut;
  heading?: string;
}) {
  const t = useT();
  return (
    <Card>
      <CardBody>
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-sm font-semibold">{heading ?? t("practice.answerFeedbackHeading")}</h2>
          <span className="text-sm text-muted" aria-label={t("practice.evalScoreAria", { score: evaluation.overall_score })}>
            <span className="text-lg font-semibold text-foreground">{evaluation.overall_score}</span>/100
          </span>
        </div>
        <p className="mt-0.5 text-xs text-muted">{t("practice.evalDisclaimer")}</p>

        <Section title={t("practice.evalWhatWorked")} items={evaluation.strengths} />
        <Section title={t("practice.evalWhatImprove")} items={evaluation.improvement_areas} />
        {evaluation.missing_evidence.length ? (
          <Section title={t("practice.evalMissingEvidence")} items={evaluation.missing_evidence} />
        ) : null}

        {evaluation.stronger_answer_structure ? (
          <Block title={t("practice.evalStrongerStructure")} body={evaluation.stronger_answer_structure} />
        ) : null}
        {evaluation.follow_up_question ? (
          <Block title={t("practice.evalFollowUp")} body={evaluation.follow_up_question} />
        ) : null}
      </CardBody>
    </Card>
  );
}

function Section({ title, items }: { title: string; items: string[] }) {
  if (!items?.length) return null;
  return (
    <div className="mt-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</h3>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
        {items.map((it, i) => <li key={i}>{it}</li>)}
      </ul>
    </div>
  );
}

function Block({ title, body }: { title: string; body: string }) {
  return (
    <div className="mt-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</h3>
      <p className="mt-1 whitespace-pre-wrap text-sm">{body}</p>
    </div>
  );
}
