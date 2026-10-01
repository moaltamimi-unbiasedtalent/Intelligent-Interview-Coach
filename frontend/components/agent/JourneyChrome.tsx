"use client";

import type { JourneyStageStatus, PreparationJourney } from "@/lib/api/types";
import { useT } from "@/components/i18n/I18nProvider";

/**
 * Candidate journey chrome (P4): UNDERSTAND → PREPARE → PRACTISE.
 *
 * Restrained, Precision-Coach-styled. Stage state comes entirely from the backend
 * journey DTO (real application state) — never fabricated here, never implementation
 * phase numbers or agent internals. State is conveyed with text + icon (not colour
 * alone), and the current stage carries aria-current. All copy is localized (W9.6).
 */

const STAGES: { key: keyof PreparationJourney; labelKey: string; hintKeys: Record<JourneyStageStatus, string> }[] = [
  { key: "understand", labelKey: "prepare.stageUnderstand", hintKeys: { not_started: "prepare.hintUnderstandNotStarted", in_progress: "prepare.hintUnderstandInProgress", complete: "prepare.hintUnderstandComplete" } },
  { key: "prepare", labelKey: "prepare.stagePrepare", hintKeys: { not_started: "prepare.hintPrepareNotStarted", in_progress: "prepare.hintPrepareInProgress", complete: "prepare.hintPrepareComplete" } },
  { key: "practise", labelKey: "prepare.stagePractise", hintKeys: { not_started: "prepare.hintPractiseNotStarted", in_progress: "prepare.hintPractiseInProgress", complete: "prepare.hintPractiseComplete" } },
];

const STATUS_KEY: Record<JourneyStageStatus, string> = {
  not_started: "prepare.statusNotStarted",
  in_progress: "prepare.statusInProgress",
  complete: "prepare.statusComplete",
};

function icon(status: JourneyStageStatus): string {
  return status === "complete" ? "✓" : status === "in_progress" ? "•" : "○";
}

export function JourneyChrome({ journey }: { journey?: PreparationJourney }) {
  const t = useT();
  if (!journey) return null;
  return (
    <nav aria-label={t("prepare.journeyAria")} className="mb-4">
      <ol className="flex items-stretch gap-1 sm:gap-2">
        {STAGES.map((stage, i) => {
          const status = journey[stage.key].status;
          const current = status === "in_progress";
          const label = t(stage.labelKey);
          const hint = t(stage.hintKeys[status]);
          return (
            <li key={stage.key} className="flex min-w-0 flex-1 items-center gap-1 sm:gap-2">
              <div
                aria-current={current ? "step" : undefined}
                className={
                  "min-w-0 flex-1 rounded-lg border px-2.5 py-2 " +
                  (status === "complete"
                    ? "border-accent/40 bg-accent/5"
                    : current
                      ? "border-accent bg-surface"
                      : "border-border bg-surface")
                }
              >
                <div className="flex items-center gap-1.5">
                  <span aria-hidden className="text-sm">{icon(status)}</span>
                  <span className="truncate text-sm font-semibold">{label}</span>
                </div>
                <p className="mt-0.5 hidden truncate text-xs text-muted sm:block">{hint}</p>
                <span className="sr-only">
                  {label}: {t(STATUS_KEY[status])}. {hint}.
                </span>
              </div>
              {i < STAGES.length - 1 ? <span aria-hidden className="shrink-0 text-muted">→</span> : null}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

const CHECKLIST: { key: "requirements_known" | "gaps_known" | "plan_known" | "questions_known"; labelKey: string; stage: "understand" | "prepare" }[] = [
  { key: "requirements_known", labelKey: "prepare.checklistUnderstand", stage: "understand" },
  { key: "gaps_known", labelKey: "prepare.checklistCompare", stage: "prepare" },
  { key: "plan_known", labelKey: "prepare.checklistBuild", stage: "prepare" },
  { key: "questions_known", labelKey: "prepare.checklistQuestions", stage: "prepare" },
];

/**
 * Observable preparation checklist (P4): reflects COMPLETED controlled tools/state —
 * not the model's private plan or reasoning. Shown only once some preparation step has
 * actually produced state (so a "give me questions" one-off is not framed as a
 * four-step flow). A not-yet-done step is "to do", never "failed".
 */
export function PreparationChecklist({ journey }: { journey?: PreparationJourney }) {
  const t = useT();
  if (!journey) return null;
  const done = (c: (typeof CHECKLIST)[number]) =>
    c.stage === "understand" ? journey.understand[c.key as "requirements_known"] : journey.prepare[c.key as "gaps_known"];
  const anyProgress = CHECKLIST.some((c) => done(c));
  if (!anyProgress) return null;

  return (
    <section aria-label={t("prepare.progressAria")} className="mb-4 rounded-lg border border-border bg-surface-2 px-3 py-3">
      <h2 className="text-sm font-semibold">{t("prepare.preparingYou")}</h2>
      <ul className="mt-2 grid gap-1.5">
        {CHECKLIST.map((c) => {
          const complete = done(c);
          return (
            <li key={c.key} className="flex items-center gap-2 text-sm">
              <span aria-hidden>{complete ? "✓" : "○"}</span>
              <span className={complete ? "" : "text-muted"}>{t(c.labelKey)}</span>
              <span className="sr-only">{complete ? t("prepare.statusDone") : t("prepare.statusToDo")}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
