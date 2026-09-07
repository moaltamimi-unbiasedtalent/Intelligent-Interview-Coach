"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";

const SUGGESTIONS = [
  "What should I focus on?",
  "Give me an example",
  "Help me prepare this answer",
];

/**
 * Plain-language input to the coach. Phase 3B scaffold: it does NOT call the career
 * API yet (Phase 3C). It clears on submit and surfaces suggestion chips.
 */
export function CoachComposer() {
  const [value, setValue] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setValue("");
  }

  return (
    <div className="mt-4">
      <form
        onSubmit={submit}
        className="flex items-center gap-2 rounded-lg border border-border bg-surface p-2 pl-3.5 shadow-soft"
      >
        <label htmlFor="coach-input" className="sr-only">
          Ask the coach
        </label>
        <Input
          id="coach-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Ask the coach…  e.g. Why is commercial ownership a gap?"
          className="border-0 bg-transparent px-1 py-1 shadow-none focus-visible:outline-none"
        />
        <Button type="submit" size="sm">
          Ask
        </Button>
      </form>
      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setValue(s)}
            className="min-h-[36px] rounded-full border border-border bg-surface px-3 text-sm text-muted transition-colors hover:text-foreground"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
