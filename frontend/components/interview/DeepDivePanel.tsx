"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { InterviewAnswerComposer } from "./InterviewAnswerComposer";
import { InterviewEvaluation } from "./InterviewEvaluation";
import type { InterviewController } from "./useInterview";

const MODE_LABELS: Record<string, string> = {
  deepen_reasoning: "Deepen the reasoning",
  challenge_assumptions: "Challenge assumptions",
  explore_evidence: "Explore the evidence",
  explore_tradeoffs: "Explore trade-offs",
  go_technical: "Go technical",
  executive_challenge: "Executive challenge",
};

const labelFor = (mode: string) => MODE_LABELS[mode] ?? mode.replace(/_/g, " ");

/**
 * Deep Dive (branch) surface. Visually distinct but part of the same interview.
 * - Not active: offers "Go deeper" with a backend-owned mode after a main answer.
 * - Active: shows the branch question, a branch composer, branch feedback, and
 *   "Go deeper" (only when allowed) / "Return to interview". Main progress is never
 *   touched here — the backend keeps the main counter fixed during a Deep Dive.
 */
export function DeepDivePanel({ ctrl, modes }: { ctrl: InterviewController; modes: string[] }) {
  const dd = ctrl.state?.deep_dive ?? null;
  const [mode, setMode] = useState<string>(modes[0] ?? "deepen_reasoning");
  const [branchAnswer, setBranchAnswer] = useState("");
  const busy = ctrl.busy;

  // Offer to start a Deep Dive only when the main answer has just been evaluated
  // (state INTERVIEW_IN_PROGRESS, an evaluation exists, no branch active yet).
  const canStart =
    !dd?.active &&
    ctrl.state?.state === "INTERVIEW_IN_PROGRESS" &&
    Boolean(ctrl.state?.last_evaluation);

  if (!dd?.active) {
    if (!canStart) return null;
    return (
      <Card className="border-l-2" >
        <CardBody>
          <h2 className="text-sm font-semibold">Go deeper on this answer</h2>
          <p className="mt-1 text-sm text-muted">
            Optional. Practise a tougher follow-up on the same topic — it won&rsquo;t change
            your main interview progress.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <label htmlFor="dd-mode" className="text-sm text-muted">Style</label>
            <select
              id="dd-mode"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              disabled={Boolean(busy)}
              className="min-h-[40px] rounded border border-border bg-surface px-2 text-sm"
            >
              {modes.map((m) => <option key={m} value={m}>{labelFor(m)}</option>)}
            </select>
            <Button variant="ghost" size="sm" onClick={() => ctrl.startDeepDive(mode)}
                    disabled={Boolean(busy)} aria-busy={busy === "deep_dive"}>
              {busy === "deep_dive" ? "Preparing a deeper follow-up…" : "Go deeper"}
            </Button>
          </div>
        </CardBody>
      </Card>
    );
  }

  const q = dd.current_branch_question;
  const awaiting = ctrl.state?.state === "BRANCH_AWAITING_ANSWER";
  const lastBranchEval = dd.last_branch_evaluation ?? null;

  return (
    <Card className="border-l-2 border-accent bg-surface-2/40">
      <CardBody>
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">
            Deep Dive · level {dd.depth} of {dd.max_depth}
          </h2>
          <span className="text-xs text-muted">{dd.mode ? labelFor(dd.mode) : ""}</span>
        </div>

        {q ? (
          <p className="mt-2 text-base font-medium" role="heading" aria-level={3}>{q.question}</p>
        ) : null}

        {awaiting ? (
          <div className="mt-3">
            <InterviewAnswerComposer
              value={branchAnswer}
              onChange={setBranchAnswer}
              busy={busy === "deep_dive_answer"}
              submitLabel="Submit deep-dive answer"
              placeholder="Answer the deeper follow-up…"
              onSubmit={async () => {
                const ok = await ctrl.deepDiveAnswer(branchAnswer);
                if (ok) setBranchAnswer("");
              }}
            />
          </div>
        ) : null}

        {!awaiting && lastBranchEval ? (
          <div className="mt-3">
            <InterviewEvaluation evaluation={lastBranchEval} heading="Deep-dive feedback" />
          </div>
        ) : null}

        {!awaiting ? (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            {dd.can_go_deeper ? (
              <Button variant="ghost" size="sm" onClick={() => ctrl.deepDiveNext()}
                      disabled={Boolean(busy)} aria-busy={busy === "deep_dive_next"}>
                {busy === "deep_dive_next" ? "Preparing a deeper follow-up…" : "Go deeper again"}
              </Button>
            ) : null}
            <Button size="sm" onClick={() => ctrl.deepDiveReturn()}
                    disabled={Boolean(busy)} aria-busy={busy === "deep_dive_return"}>
              Return to interview
            </Button>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}
