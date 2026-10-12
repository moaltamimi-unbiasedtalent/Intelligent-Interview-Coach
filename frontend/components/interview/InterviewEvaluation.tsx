"use client";

import type { EvaluationOut } from "@/lib/api/types";
import { Card, CardBody } from "@/components/ui/Card";
import { useT } from "@/components/i18n/I18nProvider";

const DIMENSIONS = [
  ["relevance", "Relevance"],
  ["structure", "Structure"],
  ["evidence", "Evidence"],
  ["role_knowledge", "RoleKnowledge"],
  ["problem_solving", "ProblemSolving"],
  ["communication", "Communication"],
  ["credibility", "Credibility"],
] as const;

/**
 * Candidate-safe answer feedback. Practice guidance only — never a hiring decision.
 * Renders exactly the fields the backend provides (no invented metrics). P2-03: the 0-100 overall_score carries a visible
 * "Interview Answer Score" label and scope (THIS answer, not the full-interview Practice Readiness), and the seven EXISTING rubric
 * dimensions (each 1-10) are shown with short descriptions. The overall score is model-produced and is NOT presented as an average,
 * sum or formula of the dimensions; no score bands are invented. The panel
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
        <h2 className="text-sm font-semibold">{heading ?? t("practice.answerFeedbackHeading")}</h2>

        <section className="mt-3 rounded-lg border border-border bg-surface-2 p-4" data-testid="answer-score">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">{t("practice.answerScoreLabel")}</p>
          {/* The accessible name lives on the group (aria-label), so "72 out of 100" is announced once and no duplicate text node is added to the page. */}
          <p role="group" aria-label={t("practice.evalScoreAria", { score: evaluation.overall_score })} className="mt-1 flex items-baseline gap-1.5" data-testid="answer-score-value">
            <span className="text-3xl font-bold text-foreground" aria-hidden="true">{evaluation.overall_score}</span>
            <span className="text-base text-muted" aria-hidden="true">/ 100</span>
          </p>
          <p className="mt-2 text-sm text-foreground">{t("practice.answerScoreScope")}</p>
          <p className="mt-1 text-xs text-muted">{t("practice.evalDisclaimer")}</p>
        </section>

        <div className="mt-4" data-testid="rubric-scores">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{t("practice.rubricTitle")}</h3>
          <dl className="mt-2 grid gap-x-6 gap-y-3 sm:grid-cols-2">
            {DIMENSIONS.map(([field, key]) => {
              const label = t(`practice.dim${key}`);
              const value = evaluation[field];
              return (
                <div key={field} data-dimension={field} className="grid grid-cols-[1fr_auto] items-baseline gap-x-3">
                  <dt className="text-sm font-medium text-foreground">{label}</dt>
                  <dd className="m-0 text-sm font-semibold tabular-nums text-foreground">
                    <span aria-hidden="true">{value} / 10</span>
                    <span className="sr-only">{t("practice.dimAria", { dimension: label, score: value })}</span>
                  </dd>
                  <dd className="col-span-2 m-0 mt-0.5 text-xs text-muted">{t(`practice.dim${key}Desc`)}</dd>
                </div>
              );
            })}
          </dl>
          <p className="mt-2 text-xs text-muted">{t("practice.rubricNote")}</p>
        </div>
        <p className="mt-3 text-sm text-foreground" data-testid="next-step-cue">{t("practice.nextStepCue")}</p>

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
