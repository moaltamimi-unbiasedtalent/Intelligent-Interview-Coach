"use client";

import { useState } from "react";
import type { SpeechRecognitionAdapter } from "@/lib/speech/types";
import { Composer } from "@/components/ui/Composer";

/** Follow-up message composer for an ongoing agent thread. Disabled while a request
 * is in flight or while the run is awaiting a human decision (answer that first).
 *
 * P3: dictation (input only) is available via the shared Composer — recognised speech
 * is appended to the editable field; sending remains an explicit click. */
export function AgentComposer({
  onSend,
  busy,
  disabled,
  disabledHint,
  dictationAdapter,
}: {
  onSend: (message: string) => void;
  busy: boolean;
  disabled?: boolean;
  disabledHint?: string;
  dictationAdapter?: SpeechRecognitionAdapter;
}) {
  const [value, setValue] = useState("");
  const canSend = !busy && !disabled && value.trim().length > 0;

  function submit() {
    if (!canSend) return;
    onSend(value.trim());
    setValue("");
  }

  return (
    <div className="mt-4">
      <Composer
        id="agent-composer"
        label="Message Mo"
        value={value}
        onChange={setValue}
        onSubmit={submit}
        busy={busy}
        disabled={disabled}
        placeholder="Ask a follow-up, or tell Mo what to focus on next…"
        submitLabel="Send"
        busyLabel="Sending…"
        footerNote={disabled && disabledHint ? disabledHint : undefined}
        buttonSize="sm"
        dictationAdapter={dictationAdapter}
      />
    </div>
  );
}
