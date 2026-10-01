"use client";

import type { SpeechRecognitionAdapter } from "@/lib/speech/types";
import { Composer } from "@/components/ui/Composer";
import { useT } from "@/components/i18n/I18nProvider";

/**
 * Controlled typed-answer composer. The parent workflow owns the answer value so it
 * can submit it, clear it only after a successful submission, and preserve it on
 * failure. Submit is disabled while a request is in flight (no duplicate submit).
 *
 * P3 (E-dictation): dictation is available as an INPUT convenience via the shared
 * Composer — recognised speech is appended to the editable answer, and submission is
 * always an explicit click (speech NEVER auto-submits). No audio is recorded or
 * stored; only the text the candidate submits is sent, exactly like typing.
 */
export function InterviewAnswerComposer({
  value,
  onChange,
  onSubmit,
  busy,
  label,
  submitLabel,
  placeholder,
  dictationAdapter,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  busy: boolean;
  label?: string;
  submitLabel?: string;
  placeholder?: string;
  dictationAdapter?: SpeechRecognitionAdapter;
}) {
  const t = useT();
  return (
    <Composer
      id="answer"
      label={label ?? t("practice.answerLabel")}
      value={value}
      onChange={onChange}
      onSubmit={onSubmit}
      busy={busy}
      placeholder={placeholder ?? t("practice.answerPlaceholder")}
      submitLabel={submitLabel ?? t("practice.submitAnswer")}
      busyLabel={t("practice.reviewingAnswer")}
      textareaClassName="min-h-[150px]"
      dictationAdapter={dictationAdapter}
    />
  );
}
