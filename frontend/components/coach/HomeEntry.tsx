"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";

/**
 * Home entry scaffold: a single question that leads into Prepare. Phase 3B does
 * NOT call the preparation API (Phase 3C) — Start navigates to /prepare.
 */
export function HomeEntry() {
  const router = useRouter();
  const [value, setValue] = useState("");

  function start(e: React.FormEvent) {
    e.preventDefault();
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
        <Button type="submit">Start</Button>
      </form>
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm">
        <button type="button" onClick={() => router.push("/prepare")} className="text-muted hover:text-foreground">
          ＋ Paste a job description
        </button>
        <button type="button" onClick={() => router.push("/prepare")} className="text-muted hover:text-foreground">
          ＋ Add your CV <span className="text-muted">(optional)</span>
        </button>
      </div>
      <p className="mt-3 text-sm text-muted">
        Your information is used only to personalise your preparation.
      </p>
    </div>
  );
}
