"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { PreparationContextInput } from "@/lib/api/types";
import { Button } from "@/components/ui/Button";

export interface PrepState {
  targetRole?: string;
  seniority?: string;
  requiredSkills?: string[];
  jobDescription?: string;
  strengths?: string[];
  gaps?: string[];
  priorities?: string[];
  industry?: string;
}

/**
 * Real Career → Interview handoff. Builds a PreparationContext from what the user
 * has gathered and creates an interview session via FastAPI, then navigates to
 * /practice?session=<id>. No extra LLM call is made here — the backend owns the
 * session; role precedence is preserved (target role is required and never faked).
 */
export function StartPracticeButton({ prep }: { prep: PrepState }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; requestId?: string | null } | null>(null);

  const ready = Boolean(prep.targetRole && prep.targetRole.trim());

  async function start() {
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    const preparation_context: PreparationContextInput = {
      target_role: prep.targetRole!.trim(),
      industry: prep.industry,
      job_description: prep.jobDescription,
      seniority: prep.seniority,
      required_skills: prep.requiredSkills ?? [],
      candidate_strengths: prep.strengths ?? [],
      candidate_gaps: prep.gaps ?? [],
      priority_competencies: prep.priorities ?? [],
    };
    try {
      const session = await api.interviews.create({
        preparation_context,
        // Sensible defaults; the domain still owns validation.
        industry_or_sector: prep.industry || "General",
        career_level: "senior",
      });
      router.push(`/practice?session=${encodeURIComponent(session.session_id)}`);
    } catch (e) {
      const err = e as ApiError;
      setError({ message: err.userMessage ?? "Couldn't start practice.", requestId: err.requestId });
      setBusy(false);
    }
  }

  return (
    <div>
      <Button onClick={start} disabled={!ready || busy} className="w-full">
        {busy ? "Starting…" : "Start interview practice →"}
      </Button>
      {!ready ? (
        <p className="mt-2 text-xs text-muted">
          Add or confirm a target role (analyze a job description) to practise.
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-2 text-xs text-danger">
          {error.message}
          {error.requestId ? <span className="block text-muted">Reference: {error.requestId}</span> : null}
        </p>
      ) : null}
    </div>
  );
}
