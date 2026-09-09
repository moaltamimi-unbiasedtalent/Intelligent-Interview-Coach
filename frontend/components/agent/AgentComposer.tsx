"use client";

import { useState } from "react";
import { Textarea } from "@/components/ui/Field";
import { Button } from "@/components/ui/Button";

/** Follow-up message composer for an ongoing agent thread. Disabled while a request
 * is in flight or while the run is awaiting a human decision (answer that first). */
export function AgentComposer({
  onSend,
  busy,
  disabled,
  disabledHint,
}: {
  onSend: (message: string) => void;
  busy: boolean;
  disabled?: boolean;
  disabledHint?: string;
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
      <label htmlFor="agent-composer" className="sr-only">Message Mo</label>
      <Textarea
        id="agent-composer"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Ask a follow-up, or tell Mo what to focus on next…"
        disabled={busy || disabled}
        className="min-h-[80px]"
        maxLength={4000}
      />
      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-muted">{disabled && disabledHint ? disabledHint : ""}</span>
        <Button size="sm" onClick={submit} disabled={!canSend}>
          {busy ? "Sending…" : "Send"}
        </Button>
      </div>
    </div>
  );
}
