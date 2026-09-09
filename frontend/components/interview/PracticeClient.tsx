"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { api } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { InterviewProgress } from "./InterviewProgress";
import { InterviewAnswerComposer } from "./InterviewAnswerComposer";
import { InterviewEvaluation } from "./InterviewEvaluation";
import { InterviewReport } from "./InterviewReport";
import { InterviewSessionSetup } from "./InterviewSessionSetup";
import { DeepDivePanel } from "./DeepDivePanel";
import { useInterview } from "./useInterview";

/**
 * Interview Practice — the full candidate lifecycle over the durable backend. With
 * `?session=<id>` it drives question → answer → feedback → (optional Deep Dive) →
 * next → complete → report, and restores that state on refresh. Without a session it
 * offers standalone setup. The backend is the only authority for transitions/scoring.
 */
export function PracticeClient({ sessionId }: { sessionId?: string }) {
  const router = useRouter();
  // Prefer the live client-side URL param so a create → replace transition switches
  // to the session view immediately (no server round-trip); fall back to the SSR prop.
  const params = useSearchParams();
  const activeSession = params?.get("session") ?? sessionId;
  // Only true on the Agent Coach → Practice handoff path (never for standalone setup),
  // so provenance is shown honestly and never fabricated (§22/§23).
  const fromCoach = params?.get("from") === "coach";

  if (!activeSession) {
    return (
      <section className="mx-auto max-w-2xl animate-enter">
        <InterviewSessionSetup onCreated={(id) => router.replace(`/practice?session=${encodeURIComponent(id)}`)} />
      </section>
    );
  }
  return <ActiveInterview key={activeSession} sessionId={activeSession} router={router} fromCoach={fromCoach} />;
}

function ActiveInterview({ sessionId, router, fromCoach }: { sessionId: string; router: ReturnType<typeof useRouter>; fromCoach?: boolean }) {
  const ctrl = useInterview(sessionId);
  const [answer, setAnswer] = useState("");
  const [modes, setModes] = useState<string[]>([]);
  const [confirmingEnd, setConfirmingEnd] = useState(false);
  const evalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    api.interviews.options().then((o) => { if (alive) setModes(o.deep_dive_modes ?? []); }).catch(() => {});
    return () => { alive = false; };
  }, []);

  const state = ctrl.state;

  if (ctrl.busy === "loading" && !state) {
    return <Section><LoadingState label="Preparing your interview" /></Section>;
  }
  if (ctrl.loadError && !state) {
    return <Section><ErrorState message={ctrl.loadError.message} requestId={ctrl.loadError.requestId} /></Section>;
  }
  if (!state) return <Section><LoadingState label="Preparing your interview" /></Section>;

  const s = state.state;
  const role = state.target_role ?? "Interview practice";
  const planned = state.questions_planned ?? Math.max(state.question_number, 1);

  // Terminal: report.
  if (s === "REPORT_READY") {
    return <Section><InterviewReport sessionId={sessionId} /></Section>;
  }

  // Recoverable error.
  if (s === "ERROR") {
    return (
      <Section>
        <Card><CardBody>
          <h1 className="text-lg font-semibold">Something interrupted your interview</h1>
          <p className="mt-2 text-sm text-muted" role="alert">
            {state.error ?? "A temporary problem occurred."}
          </p>
          <p className="mt-1 text-sm text-muted">Your interview is saved. You can pick up where you left off.</p>
          <div className="mt-4 flex gap-2">
            {state.error_recoverable ? (
              <Button onClick={() => ctrl.recover()} disabled={Boolean(ctrl.busy)} aria-busy={ctrl.busy === "recover"}>
                {ctrl.busy === "recover" ? "Resuming…" : "Resume interview"}
              </Button>
            ) : null}
            <Button variant="ghost" onClick={() => router.push("/history")}>Leave for now</Button>
          </div>
        </CardBody></Card>
      </Section>
    );
  }

  const q = state.current_question;
  const branchActive = Boolean(state.deep_dive?.active);

  return (
    <Section>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-muted">{role}</p>
          {fromCoach ? (
            <p className="text-xs text-muted" data-testid="coach-provenance">
              Prepared in your Coach session
            </p>
          ) : null}
        </div>
        <Button variant="ghost" size="sm" onClick={() => router.push("/history")}
                title="Your interview is saved; come back any time">
          Pause
        </Button>
      </div>

      <div className="my-4">
        <InterviewProgress total={planned} current={Math.max(state.question_number, 1)} />
      </div>

      {ctrl.conflict ? (
        <p className="mb-3 rounded border border-border bg-surface-2 px-3 py-2 text-sm text-muted" role="status">
          This session changed in another tab. We reloaded the latest version.
        </p>
      ) : null}
      {ctrl.actionError ? (
        <p className="mb-3 text-sm text-danger" role="alert">{ctrl.actionError}</p>
      ) : null}

      {/* Main question awaiting an answer. */}
      {s === "AWAITING_ANSWER" && q ? (
        <>
          <h1 className="mb-4 mt-2 text-xl font-semibold md:text-2xl" role="heading" aria-level={1}>
            {q.question}
          </h1>
          <InterviewAnswerComposer
            value={answer}
            onChange={setAnswer}
            busy={ctrl.busy === "submit"}
            onSubmit={async () => { const ok = await ctrl.submitAnswer(answer); if (ok) setAnswer(""); }}
          />
        </>
      ) : null}

      {/* After a main evaluation (and not inside a branch): feedback + actions. */}
      {s === "INTERVIEW_IN_PROGRESS" && !branchActive && state.last_evaluation ? (
        <div ref={evalRef} tabIndex={-1} className="space-y-4">
          <InterviewEvaluation evaluation={state.last_evaluation} />
          <DeepDivePanel ctrl={ctrl} modes={modes} />
          <MainActions ctrl={ctrl} confirmingEnd={confirmingEnd} setConfirmingEnd={setConfirmingEnd} />
        </div>
      ) : null}

      {/* Deep Dive active (branch question / branch feedback / go deeper / return). */}
      {branchActive ? <DeepDivePanel ctrl={ctrl} modes={modes} /> : null}

      {/* Interview complete → generate the report. */}
      {s === "INTERVIEW_COMPLETE" ? (
        <Card><CardBody>
          <h1 className="text-lg font-semibold">Interview complete</h1>
          <p className="mt-1 text-sm text-muted">Generate your performance review to see how you did.</p>
          <div className="mt-4">
            <Button onClick={() => ctrl.generateReport()} disabled={Boolean(ctrl.busy)} aria-busy={ctrl.busy === "report"}>
              {ctrl.busy === "report" ? "Creating your performance review…" : "Generate performance review"}
            </Button>
          </div>
        </CardBody></Card>
      ) : null}

      <p className="mt-6 text-center text-xs text-muted">
        Distraction-free by design. No camera; timing is guidance only.
      </p>
    </Section>
  );
}

function MainActions({ ctrl, confirmingEnd, setConfirmingEnd }: {
  ctrl: ReturnType<typeof useInterview>;
  confirmingEnd: boolean;
  setConfirmingEnd: (v: boolean) => void;
}) {
  const busy = Boolean(ctrl.busy);
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <Button onClick={() => ctrl.nextQuestion()} disabled={busy} aria-busy={ctrl.busy === "next"}>
        {ctrl.busy === "next" ? "Preparing your next question…" : "Next question"}
      </Button>
      {confirmingEnd ? (
        <span className="flex items-center gap-2 text-sm">
          <span className="text-muted">End the interview now?</span>
          <Button variant="ghost" size="sm" onClick={() => { setConfirmingEnd(false); void ctrl.complete(); }}
                  disabled={busy}>Yes, end</Button>
          <Button variant="ghost" size="sm" onClick={() => setConfirmingEnd(false)} disabled={busy}>Keep going</Button>
        </span>
      ) : (
        <Button variant="ghost" size="sm" onClick={() => setConfirmingEnd(true)} disabled={busy}>End interview</Button>
      )}
    </div>
  );
}

function Section({ children }: { children: React.ReactNode }) {
  return <section className="mx-auto max-w-2xl animate-enter">{children}</section>;
}
