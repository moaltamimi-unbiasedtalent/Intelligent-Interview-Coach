"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { InterviewStateResponse } from "@/lib/api/types";
import { AnswerInput } from "@/components/interview/AnswerInput";
import { InterviewProgress } from "@/components/interview/InterviewProgress";
import { Button } from "@/components/ui/Button";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { useCapabilities } from "@/lib/useCapabilities";

/**
 * Practice shell. With `?session=<id>` it shows the real interview session created
 * by the preparation handoff (role/context/first question from the Interview API).
 * Without a session it shows a standalone practice entry. Live is only offered when
 * the backend reports `live_interview_enabled`; no microphone/camera call on load.
 */
export function PracticeClient({ sessionId }: { sessionId?: string }) {
  const { capabilities } = useCapabilities();
  const liveEnabled = capabilities.live_interview_enabled;

  const [state, setState] = useState<InterviewStateResponse | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">(
    sessionId ? "loading" : "idle",
  );
  const [error, setError] = useState<{ message: string; requestId?: string | null } | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    const ctrl = new AbortController();
    setStatus("loading");
    api.interviews
      .get(sessionId, { signal: ctrl.signal })
      .then((s) => {
        setState(s);
        setStatus("idle");
      })
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        const err = e as ApiError;
        setError({ message: err.userMessage ?? "Couldn't load the session.", requestId: err.requestId });
        setStatus("error");
      });
    return () => ctrl.abort();
  }, [sessionId]);

  if (status === "loading") {
    return (
      <section className="mx-auto max-w-2xl">
        <LoadingState label="Preparing your interview" />
      </section>
    );
  }

  if (status === "error" && error) {
    return (
      <section className="mx-auto max-w-2xl">
        <ErrorState message={error.message} requestId={error.requestId} />
      </section>
    );
  }

  const role = state?.target_role ?? "Interview practice";
  const question = state?.current_question;
  // The backend couldn't produce a question (e.g. no model configured in dev).
  const notReady = Boolean(sessionId && state && !question && state.state !== "AWAITING_ANSWER");

  return (
    <section className="mx-auto max-w-2xl animate-enter">
      <p className="text-center text-sm text-muted">{role}</p>

      {sessionId && state ? (
        <div className="my-5">
          <InterviewProgress
            total={state.questions_planned ?? Math.max(state.question_number, 1)}
            current={Math.max(state.question_number, 1)}
          />
        </div>
      ) : null}

      {question ? (
        <h1 className="mx-auto mb-2 mt-6 max-w-[24ch] text-center text-2xl font-semibold md:text-3xl">
          {question.question}
        </h1>
      ) : notReady ? (
        <div className="mt-8 rounded-lg border border-border bg-surface px-6 py-10 text-center">
          <h1 className="text-lg font-semibold">Your session is ready to set up</h1>
          <p className="mx-auto mt-2 max-w-reading text-muted">
            We couldn&rsquo;t generate the first question just now. This usually means the
            interview model isn&rsquo;t configured in this environment. Your preparation is
            saved to the session.
          </p>
        </div>
      ) : (
        <h1 className="mx-auto mb-2 mt-6 max-w-[24ch] text-center text-2xl font-semibold md:text-3xl">
          {sessionId ? "Let’s begin." : "Practise an interview"}
        </h1>
      )}

      {question || !sessionId ? (
        <>
          <div className="mt-6">
            <AnswerInput recordEnabled />
          </div>
          <div className="mt-4 flex items-center justify-between">
            <Button variant="ghost" size="sm">Pause</Button>
            <Button>Submit answer</Button>
          </div>
        </>
      ) : null}

      {liveEnabled ? (
        <p className="mt-6 text-center text-xs text-muted">
          Live conversation practice is available (experimental).
        </p>
      ) : null}
      <p className="mt-6 text-center text-xs text-muted">
        Distraction-free by design. No camera; timing is guidance only.
      </p>
    </section>
  );
}
