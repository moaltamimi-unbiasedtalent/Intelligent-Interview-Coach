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
import { FeedbackControl } from "@/components/feedback/FeedbackControl";
import { VoicePlaybackControl } from "@/components/ui/VoicePlaybackControl";
import { RealtimeVoiceControl } from "@/components/ui/RealtimeVoiceControl";
import { useT } from "@/components/i18n/I18nProvider";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { useCapabilities } from "@/lib/useCapabilities";
import { isSpeechOutputLocale, toSpeechLocale } from "@/lib/speech/ttsLocales";

/**
 * Interview Practice — the full candidate lifecycle over the durable backend. With
 * `?session=<id>` it drives question → answer → feedback → (optional Deep Dive) →
 * next → complete → report, and restores that state on refresh. Without a session it
 * offers standalone setup. The backend is the only authority for transitions/scoring.
 */
export function PracticeClient({ sessionId, opportunityId }: { sessionId?: string; opportunityId?: string }) {
  const router = useRouter();
  const params = useSearchParams();
  // A just-created session id, held in state so the setup → interview transition is
  // immediate and deterministic — it does not wait on useSearchParams() re-rendering
  // after router.replace (which otherwise left the setup form stuck on "Preparing your
  // interview…" until a manual reload). The URL is still updated for refresh-safety.
  const [createdSession, setCreatedSession] = useState<string | undefined>(undefined);
  // Prefer the just-created id, then the live client-side URL param, then the SSR prop.
  const activeSession = createdSession ?? params?.get("session") ?? sessionId;
  // Only true on the Agent Coach → Practice handoff path (never for standalone setup),
  // so provenance is shown honestly and never fabricated (§22/§23).
  const fromCoach = params?.get("from") === "coach";

  if (!activeSession) {
    const oppId = opportunityId ?? params?.get("opportunity") ?? undefined;
    return (
      <section className="mx-auto max-w-2xl animate-enter">
        <InterviewSessionSetup
          opportunityId={oppId && /^\d+$/.test(oppId) ? Number(oppId) : null}
          onCreated={(id) => {
            setCreatedSession(id);  // immediate transition
            router.replace(`/practice?session=${encodeURIComponent(id)}`);  // refresh-safe URL
          }}
        />
      </section>
    );
  }
  return <ActiveInterview key={activeSession} sessionId={activeSession} router={router} fromCoach={fromCoach} />;
}

function ActiveInterview({ sessionId, router, fromCoach }: { sessionId: string; router: ReturnType<typeof useRouter>; fromCoach?: boolean }) {
  const ctrl = useInterview(sessionId);
  const [answer, setAnswer] = useState("");
  const t = useT();
  // Question playback follows the candidate's conversation language (§11); never the UI
  // locale and never career geography (§12). Falls back to en-US.
  const conversationLanguage = useAuthOptional()?.account?.conversation_language;
  const questionSpeechLang = toSpeechLocale(conversationLanguage);
  // Speech (playback + live voice) exists only for the seven speech languages; Russian is an
  // interface/conversation language without speech support, so those controls are not offered.
  const speechSupported = isSpeechOutputLocale(conversationLanguage);
  // Realtime voice (P7.5) is a DEPLOYMENT capability; when off, only turn-based voice shows.
  const { capabilities } = useCapabilities();
  const realtimeEnabled = capabilities.realtime_voice_enabled && speechSupported;
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
    return <Section><LoadingState label={t("practice.preparingInterview")} /></Section>;
  }
  if (ctrl.loadError && !state) {
    // P10B-W9.2: the session LOAD is a safe idempotent GET; recover in place via ctrl.reload()
    // (no browser reload, no re-login) rather than stranding the candidate on a dead error.
    return (
      <Section>
        <ErrorState
          message={ctrl.loadError.message}
          requestId={ctrl.loadError.requestId}
          retrying={ctrl.busy === "loading"}
          onRetry={() => void ctrl.reload()}
        />
      </Section>
    );
  }
  if (!state) return <Section><LoadingState label={t("practice.preparingInterview")} /></Section>;

  const s = state.state;
  const role = state.target_role ?? t("practice.interviewPracticeTitle");
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
          <h1 className="text-lg font-semibold">{t("practice.interruptedTitle")}</h1>
          <p className="mt-2 text-sm text-muted" role="alert">
            {state.error ?? t("practice.temporaryProblem")}
          </p>
          <p className="mt-1 text-sm text-muted">{t("practice.savedResume")}</p>
          <div className="mt-4 flex gap-2">
            {state.error_recoverable ? (
              <Button onClick={() => ctrl.recover()} disabled={Boolean(ctrl.busy)} aria-busy={ctrl.busy === "recover"}>
                {ctrl.busy === "recover" ? t("practice.resuming") : t("practice.resumeInterview")}
              </Button>
            ) : null}
            <Button variant="ghost" onClick={() => router.push("/history")}>{t("practice.leaveForNow")}</Button>
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
              {t("practice.preparedWithMo")}
            </p>
          ) : null}
        </div>
        <Button variant="ghost" size="sm" onClick={() => router.push("/history")}
                title={t("practice.pauseTitle")}>
          {t("practice.pause")}
        </Button>
      </div>

      <div className="my-4">
        <InterviewProgress total={planned} current={Math.max(state.question_number, 1)} />
      </div>

      {ctrl.conflict ? (
        <p className="mb-3 rounded border border-border bg-surface-2 px-3 py-2 text-sm text-muted" role="status">
          {t("practice.sessionChangedReload")}
        </p>
      ) : null}
      {ctrl.actionError ? (
        <p className="mb-3 text-sm text-danger" role="alert">{ctrl.actionError}</p>
      ) : null}

      {/* Main question awaiting an answer. */}
      {s === "AWAITING_ANSWER" && q ? (
        <>
          <h1 className="mb-2 mt-2 text-xl font-semibold md:text-2xl" role="heading" aria-level={1}>
            {q.question}
          </h1>
          {/* Optional playback of the VISIBLE question (§8). Never auto-plays; the answer
              composer below reuses the P3 dictation control for "Speak answer". */}
          {speechSupported ? (
            <div className="mb-4">
              <VoicePlaybackControl text={q.question} lang={questionSpeechLang} label={t("voice.listenQuestion")} />
            </div>
          ) : null}
          <InterviewAnswerComposer
            value={answer}
            onChange={setAnswer}
            busy={ctrl.busy === "submit"}
            onSubmit={async () => { const ok = await ctrl.submitAnswer(answer); if (ok) setAnswer(""); }}
          />
          {/* Optional realtime voice (Capstone P7.5, C1). Explicitly started by the candidate.
              The final spoken answer commits through the SAME durable answer service — the
              Practice state machine stays authoritative; commit is once per turn. When
              realtime is off/unsupported this is absent and turn-based voice + typing remain. */}
          {realtimeEnabled ? (
            <details className="mt-4 rounded-md border p-3" data-testid="realtime-practice">
              <summary className="cursor-pointer text-sm font-medium">
                {t("voice.realtimeStart")}
              </summary>
              <div className="mt-3">
                <RealtimeVoiceControl
                  surface="practice"
                  interviewSessionId={sessionId}
                  locale={conversationLanguage ?? undefined}
                  onCommit={async (text) => {
                    const ok = await ctrl.submitAnswer(text);
                    if (ok) setAnswer("");
                  }}
                />
              </div>
            </details>
          ) : null}
        </>
      ) : null}

      {/* After a main evaluation (and not inside a branch): feedback + actions. */}
      {s === "INTERVIEW_IN_PROGRESS" && !branchActive && state.last_evaluation ? (
        <div ref={evalRef} tabIndex={-1} className="space-y-4">
          <InterviewEvaluation evaluation={state.last_evaluation} />
          <FeedbackControl surface="interview_evaluation"
            targetId={`${sessionId}:${state.question_number}`}
            prompt={t("feedback.evalPrompt")} />
          <DeepDivePanel ctrl={ctrl} modes={modes} />
          <MainActions ctrl={ctrl} confirmingEnd={confirmingEnd} setConfirmingEnd={setConfirmingEnd} />
        </div>
      ) : null}

      {/* Deep Dive active (branch question / branch feedback / go deeper / return). */}
      {branchActive ? <DeepDivePanel ctrl={ctrl} modes={modes} /> : null}

      {/* Interview complete → generate the report. */}
      {s === "INTERVIEW_COMPLETE" ? (
        <Card><CardBody>
          <h1 className="text-lg font-semibold">{t("practice.interviewComplete")}</h1>
          <p className="mt-1 text-sm text-muted">{t("practice.generatePrompt")}</p>
          <div className="mt-4">
            <Button onClick={() => ctrl.generateReport()} disabled={Boolean(ctrl.busy)} aria-busy={ctrl.busy === "report"}>
              {ctrl.busy === "report" ? t("practice.generatingReportBusy") : t("practice.generateReport")}
            </Button>
          </div>
        </CardBody></Card>
      ) : null}

      <p className="mt-6 text-center text-xs text-muted">
        {t("practice.distractionFree")}
      </p>
    </Section>
  );
}

function MainActions({ ctrl, confirmingEnd, setConfirmingEnd }: {
  ctrl: ReturnType<typeof useInterview>;
  confirmingEnd: boolean;
  setConfirmingEnd: (v: boolean) => void;
}) {
  const t = useT();
  const busy = Boolean(ctrl.busy);
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <Button onClick={() => ctrl.nextQuestion()} disabled={busy} aria-busy={ctrl.busy === "next"}>
        {ctrl.busy === "next" ? t("practice.preparingNext") : t("practice.nextQuestion")}
      </Button>
      {confirmingEnd ? (
        <span className="flex items-center gap-2 text-sm">
          <span className="text-muted">{t("practice.endConfirm")}</span>
          <Button variant="ghost" size="sm" onClick={() => { setConfirmingEnd(false); void ctrl.complete(); }}
                  disabled={busy}>{t("practice.endYes")}</Button>
          <Button variant="ghost" size="sm" onClick={() => setConfirmingEnd(false)} disabled={busy}>{t("practice.keepGoing")}</Button>
        </span>
      ) : (
        <Button variant="ghost" size="sm" onClick={() => setConfirmingEnd(true)} disabled={busy}>{t("practice.endInterview")}</Button>
      )}
    </div>
  );
}

function Section({ children }: { children: React.ReactNode }) {
  return <section className="mx-auto max-w-2xl animate-enter">{children}</section>;
}
