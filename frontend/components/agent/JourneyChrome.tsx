"use client";

import type { JourneyStageStatus, PreparationJourney } from "@/lib/api/types";

/**
 * Candidate journey chrome (P4): UNDERSTAND → PREPARE → PRACTISE.
 *
 * Restrained, Precision-Coach-styled. Stage state comes entirely from the backend
 * journey DTO (real application state) — never fabricated here, never implementation
 * phase numbers or agent internals. State is conveyed with text + icon (not colour
 * alone), and the current stage carries aria-current.
 */

const STAGES: { key: keyof PreparationJourney; label: string; hint: Record<JourneyStageStatus, string> }[] = [
  { key: "understand", label: "Understand", hint: { not_started: "Tell your coach the role", in_progress: "Getting the opportunity clear", complete: "Role understood" } },
  { key: "prepare", label: "Prepare", hint: { not_started: "Preparation not started yet", in_progress: "Building your preparation", complete: "Preparation ready" } },
  { key: "practise", label: "Practise", hint: { not_started: "Ready when you are", in_progress: "Awaiting your go-ahead", complete: "Practice underway" } },
];

function icon(status: JourneyStageStatus): string {
  return status === "complete" ? "✓" : status === "in_progress" ? "•" : "○";
}

export function JourneyChrome({ journey }: { journey?: PreparationJourney }) {
  if (!journey) return null;
  return (
    <nav aria-label="Preparation journey" className="mb-4">
      <ol className="flex items-stretch gap-1 sm:gap-2">
        {STAGES.map((stage, i) => {
          const status = journey[stage.key].status;
          const current = status === "in_progress";
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
                  <span className="truncate text-sm font-semibold">{stage.label}</span>
                </div>
                <p className="mt-0.5 hidden truncate text-xs text-muted sm:block">{stage.hint[status]}</p>
                <span className="sr-only">
                  {stage.label}: {status.replace("_", " ")}. {stage.hint[status]}.
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

const CHECKLIST: { key: "requirements_known" | "gaps_known" | "plan_known" | "questions_known"; label: string; stage: "understand" | "prepare" }[] = [
  { key: "requirements_known", label: "Understand the opportunity", stage: "understand" },
  { key: "gaps_known", label: "Compare your experience", stage: "prepare" },
  { key: "plan_known", label: "Build preparation priorities", stage: "prepare" },
  { key: "questions_known", label: "Create practice questions", stage: "prepare" },
];

/**
 * Observable preparation checklist (P4): reflects COMPLETED controlled tools/state —
 * not the model's private plan or reasoning. Shown only once some preparation step has
 * actually produced state (so a "give me questions" one-off is not framed as a
 * four-step flow). A not-yet-done step is "to do", never "failed".
 */
export function PreparationChecklist({ journey }: { journey?: PreparationJourney }) {
  if (!journey) return null;
  const done = (c: (typeof CHECKLIST)[number]) =>
    c.stage === "understand" ? journey.understand[c.key as "requirements_known"] : journey.prepare[c.key as "gaps_known"];
  const anyProgress = CHECKLIST.some((c) => done(c));
  if (!anyProgress) return null;

  return (
    <section aria-label="Preparation progress" className="mb-4 rounded-lg border border-border bg-surface-2 px-3 py-3">
      <h2 className="text-sm font-semibold">Preparing you</h2>
      <ul className="mt-2 grid gap-1.5">
        {CHECKLIST.map((c) => {
          const complete = done(c);
          return (
            <li key={c.key} className="flex items-center gap-2 text-sm">
              <span aria-hidden>{complete ? "✓" : "○"}</span>
              <span className={complete ? "" : "text-muted"}>{c.label}</span>
              <span className="sr-only">{complete ? "done" : "to do"}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
