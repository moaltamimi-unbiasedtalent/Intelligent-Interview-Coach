"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { writePrepareDraft, type PrepareDraftAction } from "@/lib/prepareDraft";

/**
 * Home is a genuine entry point into Prepare. The goal typed here is transferred
 * ephemerally (never via the URL) and starts the preparation session on /prepare
 * without the candidate re-entering it. The two shortcuts open the matching context
 * field in Prepare. See {@link writePrepareDraft}.
 */
export function HomeEntry() {
  const router = useRouter();
  const [value, setValue] = useState("");
  const canStart = value.trim().length > 0;

  function start(e: React.FormEvent) {
    e.preventDefault();
    const goal = value.trim();
    if (!goal) return; // never navigate / start a blank run (§6)
    writePrepareDraft({ source: "home", action: "start", goal });
    router.push("/prepare");
  }

  // A shortcut carries only its intent; Prepare opens and focuses the right field.
  function shortcut(action: Exclude<PrepareDraftAction, "start">) {
    writePrepareDraft({ source: "home", action });
    router.push("/prepare");
  }

  return (
    <div className="mt-2 max-w-2xl">
      <form
        onSubmit={start}
        className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-2.5 shadow-soft sm:flex-row"
      >
        <label htmlFor="home-entry" className="sr-only">
          What interview are you preparing for?
        </label>
        <Input
          id="home-entry"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="What interview are you preparing for?  e.g. Senior Product Manager at a fintech"
          className="border-0 bg-transparent shadow-none focus-visible:outline-none"
        />
        <Button type="submit" disabled={!canStart}>Ask Mo</Button>
      </form>
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm">
        <button type="button" onClick={() => shortcut("job_description")} className="text-muted hover:text-foreground">
          ＋ Paste a job description
        </button>
        <button type="button" onClick={() => shortcut("candidate_background")} className="text-muted hover:text-foreground">
          ＋ Add your background <span className="text-muted">(optional)</span>
        </button>
      </div>
      <p className="mt-3 text-sm text-muted">
        Your information is used only to personalise your preparation.
      </p>
    </div>
  );
}
