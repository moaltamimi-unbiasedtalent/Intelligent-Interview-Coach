"use client";

import { AnswerInput } from "@/components/interview/AnswerInput";
import { InterviewProgress } from "@/components/interview/InterviewProgress";
import { Button } from "@/components/ui/Button";
import { useCapabilities } from "@/lib/useCapabilities";

/**
 * Distraction-free practice shell. Type/Record are the offered modes. Live is only
 * mentioned when the backend capability `live_interview_enabled` is true — it is
 * never hardcoded on, and no microphone/camera call is made on load.
 */
export function PracticeClient() {
  const { capabilities } = useCapabilities();
  const liveEnabled = capabilities.live_interview_enabled;

  return (
    <section className="mx-auto max-w-2xl animate-enter">
      <p className="text-center text-sm text-muted">
        Senior Product Manager · Behavioural · Northwind (demo)
      </p>
      <div className="my-5">
        <InterviewProgress total={5} current={2} />
      </div>
      <h1 className="mx-auto mb-2 mt-6 max-w-[22ch] text-center text-2xl font-semibold md:text-3xl">
        Tell me about a time you aligned executives behind a roadmap.
      </h1>
      <div className="mt-6">
        <AnswerInput recordEnabled />
      </div>
      <div className="mt-4 flex items-center justify-between">
        <Button variant="ghost" size="sm">
          Pause
        </Button>
        <Button>Submit answer</Button>
      </div>
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
