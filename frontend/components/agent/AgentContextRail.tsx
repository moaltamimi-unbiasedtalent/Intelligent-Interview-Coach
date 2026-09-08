"use client";

import type { AgentRunResponse } from "@/lib/api/types";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</h3>
      <div className="mt-1 text-sm">{children}</div>
    </div>
  );
}

/**
 * The Precision Coach context rail: real, evolving preparation state derived from
 * the agent run — never raw internal state. Keeps the Coach from feeling like a
 * generic chatbot.
 */
export function AgentContextRail({ run }: { run: AgentRunResponse }) {
  const ctx = run.preparation_context ?? null;
  const role = ctx?.target_role ?? run.resolved_occupation ?? null;
  const strengths = ctx?.candidate_strengths ?? [];
  const gaps = ctx?.candidate_gaps ?? [];
  const priorities = ctx?.priority_competencies ?? [];

  return (
    <Card>
      <CardBody className="space-y-4">
        <h2 className="text-sm font-semibold">Your preparation</h2>

        <Section title="Target role">
          {role ? <span className="font-medium">{role}</span> : <span className="text-muted">Not set yet</span>}
        </Section>

        {strengths.length ? (
          <Section title="Strengths">
            <ul className="flex flex-wrap gap-1.5">
              {strengths.slice(0, 6).map((s, i) => <li key={i}><Badge tone="low">{s}</Badge></li>)}
            </ul>
          </Section>
        ) : null}

        {(priorities.length ? priorities : gaps).length ? (
          <Section title="Priority gaps">
            <ul className="flex flex-wrap gap-1.5">
              {(priorities.length ? priorities : gaps).slice(0, 6).map((g, i) => <li key={i}><Badge tone="high">{g}</Badge></li>)}
            </ul>
          </Section>
        ) : null}

        <Section title="Preparation plan">
          {ctx ? <span className="text-muted">Ready — {role ?? "role"} plan available</span> : <span className="text-muted">Not built yet</span>}
        </Section>

        <Section title="Career evidence">
          {run.retrieval_used ? (
            <span className="text-muted">{run.sources.length} source{run.sources.length === 1 ? "" : "s"} considered</span>
          ) : (
            <span className="text-muted">None yet</span>
          )}
        </Section>

        {run.memory_used ? (
          <Section title="Saved preparation">
            <span className="text-muted">Using {run.memory_count} saved note{run.memory_count === 1 ? "" : "s"}</span>
          </Section>
        ) : null}
      </CardBody>
    </Card>
  );
}
