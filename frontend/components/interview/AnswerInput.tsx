"use client";

import { useState } from "react";
import { Textarea } from "@/components/ui/Field";
import { cn } from "@/lib/utils";

type Mode = "type" | "record";

/**
 * Type / Record answer surface. Phase 3B is a visual shell: Record is shown as an
 * available mode but makes NO microphone/camera call. Live is not offered here.
 */
export function AnswerInput({ recordEnabled = true }: { recordEnabled?: boolean }) {
  const [mode, setMode] = useState<Mode>("type");

  return (
    <div>
      <div
        role="group"
        aria-label="Answer method"
        className="mx-auto mb-4 flex w-max gap-1 rounded-full bg-surface-2 p-1"
      >
        {(["type", "record"] as Mode[]).map((m) => (
          <button
            key={m}
            type="button"
            aria-pressed={mode === m}
            disabled={m === "record" && !recordEnabled}
            onClick={() => setMode(m)}
            className={cn(
              "min-h-[40px] rounded-full px-5 text-sm font-semibold capitalize transition-colors disabled:opacity-50",
              mode === m ? "bg-surface text-foreground shadow-soft" : "text-muted",
            )}
          >
            {m}
          </button>
        ))}
      </div>

      {mode === "type" ? (
        <>
          <label htmlFor="answer" className="sr-only">
            Your answer
          </label>
          <Textarea
            id="answer"
            placeholder="Take a breath. Structure it as situation → action → result…"
          />
        </>
      ) : (
        <div className="rounded-lg border border-dashed border-border bg-surface px-6 py-10 text-center text-sm text-muted">
          Recording is available in practice. Your microphone is only used when you
          start recording — never on page load. (Demo shell.)
        </div>
      )}
    </div>
  );
}
