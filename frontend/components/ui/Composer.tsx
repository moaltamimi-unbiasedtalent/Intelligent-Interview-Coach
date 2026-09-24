"use client";

/**
 * Shared natural-language composer (Capstone P3 reuse audit).
 *
 * Consolidates the duplicated "textarea + submit button + trim/busy" pattern
 * (previously reimplemented in the agent follow-up composer, the interview answer
 * composer and the first-message form) into one controlled primitive, and gives
 * dictation a single home (a trailing DictationControl in the footer).
 *
 * Behaviour preserved from the originals:
 * - Fully controlled (parent owns value); submit is CLICK-ONLY (no Enter-to-send).
 * - Submit is disabled while busy or when the trimmed value is empty.
 * - The exact accessible label / button text are caller-supplied so existing tests
 *   and e2e (which query "Message Mo", "Your answer", "Send", "Submit answer") keep
 *   working unchanged.
 * Dictation is INPUT ONLY: it appends recognised text to the field; it never submits.
 */

import type { SpeechRecognitionAdapter } from "@/lib/speech/types";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";
import { DictationControl } from "@/components/ui/DictationControl";
import { useDictationLanguage } from "@/lib/speech/useDictationLanguage";

export function Composer({
  id,
  value,
  onChange,
  onSubmit,
  busy = false,
  disabled = false,
  label,
  placeholder,
  submitLabel = "Send",
  busyLabel,
  footerNote,
  textareaClassName = "min-h-[80px]",
  buttonSize = "md",
  dictation = true,
  dictationAdapter,
}: {
  id: string;
  value: string;
  onChange: (next: string) => void;
  onSubmit: () => void;
  busy?: boolean;
  disabled?: boolean;
  label: string;
  placeholder?: string;
  submitLabel?: string;
  busyLabel?: string;
  footerNote?: string;
  textareaClassName?: string;
  buttonSize?: "md" | "sm";
  dictation?: boolean;
  /** Injectable speech adapter (tests supply a deterministic fake). */
  dictationAdapter?: SpeechRecognitionAdapter;
}) {
  const [lang, setLang] = useDictationLanguage();
  const empty = value.trim().length === 0;
  const inputDisabled = busy || disabled;

  return (
    <div>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <Textarea
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={inputDisabled}
        placeholder={placeholder}
        aria-label={label}
        className={textareaClassName}
        maxLength={4000}
      />
      <div className="mt-2 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          {dictation ? (
            <DictationControl
              value={value}
              onChange={onChange}
              disabled={inputDisabled}
              adapter={dictationAdapter}
              lang={lang}
              onLangChange={setLang}
            />
          ) : null}
          {footerNote ? <span className="truncate text-xs text-muted">{footerNote}</span> : null}
        </div>
        <Button
          size={buttonSize}
          onClick={onSubmit}
          disabled={busy || disabled || empty}
          aria-busy={busy}
        >
          {busy ? busyLabel ?? "Sending…" : submitLabel}
        </Button>
      </div>
    </div>
  );
}
