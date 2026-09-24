"use client";

/**
 * Reusable dictation control (Capstone P3 / E-dictation).
 *
 * A microphone toggle that appends recognised speech into an EXISTING controlled text
 * field. It is INPUT ONLY: it never submits, never persists audio, and never analyses
 * voice/emotion/identity. Recognised final text is appended (typed text is preserved);
 * interim text is shown as a transient preview and never written into the field.
 *
 * Accessibility: native <button> with aria-pressed + aria-label, an aria-live status,
 * a keyboard-operable stop, no colour-only state, and motion only when the user allows
 * it. When recognition is unsupported the control renders nothing, so typing remains
 * the guaranteed path.
 */

import { useId, useRef } from "react";
import type { SpeechRecognitionAdapter, DictationErrorKind } from "@/lib/speech/types";
import { appendTranscript, useDictation } from "@/lib/speech/useDictation";

export interface DictationLanguage {
  code: string;
  label: string;
}

// Bounded Ask4Mo dictation language set → recognition locale (BCP-47). This is a fixed
// allow-list: the browser engine only ever receives one of these tags, never an
// arbitrary language/provider parameter. Whether a given browser actually supports a
// given tag is BROWSER/ENGINE-DEPENDENT (documented in Help); we do not claim every
// language works in every browser. Whole-application UI translation is NOT implied by
// this — application localisation is a separate future phase.
export const DICTATION_LANGUAGES: DictationLanguage[] = [
  { code: "en-US", label: "English" },
  { code: "de-DE", label: "German" },
  { code: "fr-FR", label: "French" },
  { code: "es-ES", label: "Spanish" },
  { code: "it-IT", label: "Italian" },
  { code: "pt-PT", label: "Portuguese" },
  { code: "nl-NL", label: "Dutch" },
];

const ERROR_COPY: Record<DictationErrorKind, string> = {
  unsupported: "Dictation isn’t available in this browser. You can type instead.",
  "permission-denied": "Microphone access was blocked. You can still type.",
  "no-microphone": "No microphone was found. You can still type.",
  "no-speech": "I didn’t catch that — try again, or type.",
  network: "Dictation is temporarily unavailable. You can still type.",
  aborted: "",
  error: "Dictation stopped unexpectedly. You can still type.",
};

export function DictationControl({
  value,
  onChange,
  disabled = false,
  adapter,
  lang,
  onLangChange,
  className,
}: {
  value: string;
  onChange: (next: string) => void;
  disabled?: boolean;
  adapter?: SpeechRecognitionAdapter;
  lang?: string;
  onLangChange?: (code: string) => void;
  className?: string;
}) {
  // Always append to the LATEST field value (avoids stale-closure overwrite).
  const valueRef = useRef(value);
  valueRef.current = value;
  const langSelectId = useId();

  const selectedLang = lang ?? DICTATION_LANGUAGES[0].code;

  const { supported, status, interim, error, start, stop } = useDictation({
    adapter,
    lang: selectedLang,
    onCommitFinal: (chunk) => onChange(appendTranscript(valueRef.current, chunk)),
  });

  // Unsupported → offer nothing; typing is the guaranteed fallback.
  if (!supported) return null;

  const listening = status === "listening";
  const errorText = error ? ERROR_COPY[error] : "";

  return (
    <div className={className}>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => (listening ? stop() : start())}
          disabled={disabled}
          aria-pressed={listening}
          aria-label={listening ? "Stop dictation" : "Start dictation"}
          className={`inline-flex h-9 w-9 items-center justify-center rounded-full border transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2 disabled:opacity-50 ${
            listening
              ? "border-accent bg-accent text-accent-foreground"
              : "border-border bg-surface text-foreground hover:bg-surface-2"
          }`}
        >
          {/* Icon conveys the action; the aria-label and status text carry meaning
              (never colour alone). */}
          <span aria-hidden>{listening ? "■" : "🎤"}</span>
        </button>

        {listening ? (
          <span
            className="inline-flex h-2 w-2 rounded-full bg-accent motion-safe:animate-pulse"
            aria-hidden
          />
        ) : null}

        <label className="sr-only" htmlFor={langSelectId}>
          Dictation language
        </label>
        <select
          id={langSelectId}
          value={selectedLang}
          onChange={(e) => onLangChange?.(e.target.value)}
          disabled={disabled || listening || !onLangChange}
          className="rounded border border-border bg-surface px-2 py-1 text-xs text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          aria-label="Dictation language"
        >
          {DICTATION_LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>
      </div>

      {/* Status + interim preview for assistive tech and sighted users. Interim text is
          preview only — it is NOT part of the editable field until finalised. */}
      <p role="status" aria-live="polite" className="mt-1 min-h-[1rem] text-xs text-muted">
        {listening ? (interim ? `Heard: ${interim}` : "Listening… speak, then review before sending.") : errorText}
      </p>
    </div>
  );
}
