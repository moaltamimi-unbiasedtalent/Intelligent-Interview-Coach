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
 * it. When recognition is unsupported the control renders a small accessible fallback note
 * (never silence, P10B Wave 1) so the candidate knows dictation exists; typing stays the
 * guaranteed path.
 */

import { useId, useRef } from "react";
import type { SpeechRecognitionAdapter, DictationErrorKind } from "@/lib/speech/types";
import { appendTranscript, useDictation } from "@/lib/speech/useDictation";
import { useT } from "@/components/i18n/I18nProvider";
import { APP_LOCALES, toSupportedLocale } from "@/lib/i18n/locales";

// Map a runtime dictation error to its i18n key (P10B Wave 1 — localized error copy).
const ERROR_KEY: Record<DictationErrorKind, string> = {
  unsupported: "dictation.unsupported",
  "permission-denied": "dictation.permissionDenied",
  "no-microphone": "dictation.noMicrophone",
  "no-speech": "dictation.noSpeech",
  network: "dictation.network",
  aborted: "",
  error: "dictation.error",
};

export interface DictationLanguage {
  code: string;
}

// Bounded Ask4Mo dictation language set → recognition locale (BCP-47). This is a fixed
// allow-list: the browser engine only ever receives one of these tags, never an
// arbitrary language/provider parameter. Whether a given browser actually supports a
// given tag is BROWSER/ENGINE-DEPENDENT (documented in Help); we do not claim every
// language works in every browser. Dictation is a separate dimension from the interface
// language and never changes it (P3.5 independence).
export const DICTATION_LANGUAGES: DictationLanguage[] = [
  { code: "en-US" },
  { code: "de-DE" },
  { code: "fr-FR" },
  { code: "es-ES" },
  { code: "it-IT" },
  { code: "pt-PT" },
  { code: "nl-NL" },
];

// Display a dictation BCP-47 tag as the language's own native name (endonym), reusing the canonical
// locale registry — identical to how the interface/conversation selectors render their options. This
// keeps the option label consistent and locale-independent (no per-interface translation of language
// names), and carries no hardcoded English. Falls back to the raw tag if unmapped.
export function dictationLanguageName(code: string): string {
  const sub = toSupportedLocale(code);
  return (sub && APP_LOCALES.find((l) => l.code === sub)?.nativeLabel) || code;
}

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
  const t = useT();
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

  // Unsupported → do NOT go silent (P10B Wave 1): typing stays the guaranteed path, but show a
  // small, accessible note so the candidate knows dictation exists and why it's absent here.
  if (!supported) {
    return (
      <p className={className} role="note" data-testid="dictation-unsupported"
         style={{ fontSize: "0.8rem" }}>
        <span className="text-muted">{t("dictation.unsupported")}</span>
      </p>
    );
  }

  const listening = status === "listening";
  const errorText = error && ERROR_KEY[error] ? t(ERROR_KEY[error]) : "";

  return (
    <div className={className}>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => (listening ? stop() : start())}
          disabled={disabled}
          aria-pressed={listening}
          aria-label={listening ? t("dictation.stop") : t("dictation.start")}
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
          {t("dictation.languageLabel")}
        </label>
        <select
          id={langSelectId}
          value={selectedLang}
          onChange={(e) => onLangChange?.(e.target.value)}
          disabled={disabled || listening || !onLangChange}
          className="rounded border border-border bg-surface px-2 py-1 text-xs text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          aria-label={t("dictation.languageLabel")}
        >
          {DICTATION_LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {dictationLanguageName(l.code)}
            </option>
          ))}
        </select>
      </div>

      {/* Status + interim preview for assistive tech and sighted users. Interim text is
          preview only — it is NOT part of the editable field until finalised. */}
      <p role="status" aria-live="polite" className="mt-1 min-h-[1rem] text-xs text-muted">
        {listening ? (interim ? t("dictation.heard", { text: interim }) : t("dictation.listening")) : errorText}
      </p>
    </div>
  );
}
