"use client";

import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";

/**
 * Controlled typed-answer composer. The parent workflow owns the answer value so it
 * can submit it, clear it only after a successful submission, and preserve it on
 * failure. Submit is disabled while a request is in flight (no duplicate submit).
 *
 * Record mode is intentionally NOT offered here: there is no production server-side
 * transcription path in this release, so no candidate-facing control claims it (see
 * docs/sprint4_interview_parity.md). No microphone or camera is ever accessed.
 */
export function InterviewAnswerComposer({
  value,
  onChange,
  onSubmit,
  busy,
  label = "Your answer",
  submitLabel = "Submit answer",
  placeholder = "Take a breath. Structure it as situation → action → result…",
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  busy: boolean;
  label?: string;
  submitLabel?: string;
  placeholder?: string;
}) {
  const empty = value.trim().length === 0;
  return (
    <div>
      <label htmlFor="answer" className="sr-only">{label}</label>
      <Textarea
        id="answer"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={busy}
        placeholder={placeholder}
        aria-label={label}
      />
      <div className="mt-3 flex items-center justify-end">
        <Button onClick={onSubmit} disabled={busy || empty} aria-busy={busy}>
          {busy ? "Reviewing your answer…" : submitLabel}
        </Button>
      </div>
    </div>
  );
}
