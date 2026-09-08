"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";

const labelize = (id: string) => id.charAt(0).toUpperCase() + id.slice(1).replace(/_/g, " ");

/**
 * Standalone interview setup — start Practice WITHOUT an Agent Coach handoff. Uses the
 * backend-owned taxonomies (career levels) so the client never maintains its own list.
 * On create, the parent updates the URL with the new session id and the interview
 * begins.
 */
export function InterviewSessionSetup({ onCreated }: { onCreated: (sessionId: string) => void }) {
  const [role, setRole] = useState("");
  const [industry, setIndustry] = useState("");
  const [careerLevels, setCareerLevels] = useState<string[]>([]);
  const [careerLevel, setCareerLevel] = useState("");
  const [count, setCount] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.interviews.options()
      .then((o) => {
        if (!alive) return;
        setCareerLevels(o.career_levels);
        setCareerLevel((prev) => prev || o.career_levels[0] || "");
      })
      .catch(() => { /* options are non-critical; the form still submits with defaults */ });
    return () => { alive = false; };
  }, []);

  const canSubmit = role.trim() && industry.trim() && careerLevel && !busy;

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      const state = await api.interviews.create({
        configuration: {
          target_role: role.trim(),
          industry_or_sector: industry.trim(),
          career_level: careerLevel,
          number_of_questions: count,
        },
      });
      onCreated(state.session_id);
    } catch (e) {
      const err = e as ApiError;
      setError(err.userMessage ?? "Couldn't start the interview. Please check the details and try again.");
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardBody>
        <h1 className="text-lg font-semibold">Practise an interview</h1>
        <p className="mt-1 text-sm text-muted">
          Set up a practice interview. You don&rsquo;t need to come from the coach.
        </p>

        <div className="mt-4 grid gap-3">
          <Labeled label="Target role">
            <Input value={role} onChange={(e) => setRole(e.target.value)}
                   placeholder="e.g. Senior Product Manager" disabled={busy} />
          </Labeled>
          <Labeled label="Industry or sector">
            <Input value={industry} onChange={(e) => setIndustry(e.target.value)}
                   placeholder="e.g. fintech" disabled={busy} />
          </Labeled>
          <Labeled label="Career level">
            <select
              value={careerLevel}
              onChange={(e) => setCareerLevel(e.target.value)}
              disabled={busy || careerLevels.length === 0}
              className="min-h-[44px] rounded border border-border bg-surface px-2 text-sm"
              aria-label="Career level"
            >
              {careerLevels.length === 0 ? <option value="">Loading…</option> : null}
              {careerLevels.map((lvl) => <option key={lvl} value={lvl}>{labelize(lvl)}</option>)}
            </select>
          </Labeled>
          <Labeled label="Number of questions">
            <Input type="number" min={1} max={20} value={count}
                   onChange={(e) => setCount(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
                   disabled={busy} />
          </Labeled>
        </div>

        {error ? <p className="mt-3 text-sm text-danger" role="alert">{error}</p> : null}

        <div className="mt-4 flex justify-end">
          <Button onClick={submit} disabled={!canSubmit} aria-busy={busy}>
            {busy ? "Preparing your interview…" : "Start interview"}
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="grid gap-1">
      <span className="text-sm font-medium">{label}</span>
      {children}
    </label>
  );
}
