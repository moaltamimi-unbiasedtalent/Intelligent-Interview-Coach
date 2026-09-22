"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { KnowledgeDiagnosticsResponse } from "@/lib/api/types";
import { Card, CardBody } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";

/**
 * Read-only Knowledge / RAG diagnostics. Separates the KNOWLEDGE RUNTIME (governed
 * structured/vector counts + build provenance) from OFFLINE RETRIEVAL EVALUATION
 * (deterministic retrieval-quality metrics). Shows only counts, versions, rates and
 * known gaps from committed evidence artifacts — never embeddings, raw retrieval
 * contents, prompts or secrets, and never a live/paid run.
 */
export function RagDiagnosticsClient() {
  const [data, setData] = useState<KnowledgeDiagnosticsResponse | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<{ message: string; requestId?: string | null } | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    api.knowledge
      .diagnostics({ signal: ctrl.signal })
      .then((r) => {
        setData(r);
        setStatus("ready");
      })
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        const err = e as ApiError;
        setError({ message: err.userMessage ?? "Couldn't load knowledge diagnostics.", requestId: err.requestId });
        setStatus("error");
      });
    return () => ctrl.abort();
  }, []);

  if (status === "loading") return <LoadingState label="Loading knowledge diagnostics" />;
  if (status === "error" && error) return <ErrorState message={error.message} requestId={error.requestId} />;
  if (!data) return null;

  const rt = data.runtime;
  const ev = data.retrieval_evaluation;
  const n = (v?: number | null) => (typeof v === "number" ? v.toLocaleString() : "—");
  const pct = (v?: number | null) => (typeof v === "number" ? `${Math.round(v * 100)}%` : "—");

  const counts: Array<{ label: string; value: string }> = [
    { label: "Occupations", value: n(rt.occupations) },
    { label: "Aliases", value: n(rt.aliases) },
    { label: "Skills", value: n(rt.skills) },
    { label: "Tasks", value: n(rt.tasks) },
    { label: "Knowledge areas", value: n(rt.knowledge_areas) },
    { label: "Work activities", value: n(rt.work_activities) },
    { label: "Compensation rows", value: n(rt.compensation) },
    { label: "Labour-market rows", value: n(rt.labour_market) },
    { label: "Competencies", value: n(rt.competencies) },
    { label: "Credentials", value: n(rt.credentials) },
    { label: "Governed sources", value: n(rt.sources) },
  ];

  const quality: Array<{ label: string; value: string }> = [
    { label: "Retrieval cases", value: ev.cases != null ? `${ev.passed}/${ev.cases}` : "—" },
    { label: "Pass rate", value: pct(ev.pass_rate) },
    { label: "Evidence coverage", value: pct(ev.evidence_coverage_rate) },
    { label: "Citation completeness", value: pct(ev.citation_completeness_rate) },
    { label: "Geography correctness", value: pct(ev.geography_correctness_rate) },
    { label: "Unknown-role safety", value: pct(ev.unknown_role_safety_rate) },
    { label: "Unsupported-geography safety", value: pct(ev.unsupported_geography_safety_rate) },
    { label: "No fabricated citations", value: pct(ev.no_fabricated_citation_rate) },
  ];

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-sm font-semibold text-foreground">Knowledge runtime</h2>
        <p className="mb-3 text-xs text-muted">
          Governed structured + vector knowledge the retrieval layer serves.
          {rt.runtime_pipeline_version ? ` Pipeline ${rt.runtime_pipeline_version}.` : ""}
          {rt.built_at ? ` Built ${new Date(rt.built_at).toLocaleDateString()}.` : ""}
        </p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {counts.map((c) => (
            <Card key={c.label}>
              <CardBody>
                <p className="text-xl font-semibold text-foreground">{c.value}</p>
                <p className="mt-1 text-xs text-muted">{c.label}</p>
              </CardBody>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold text-foreground">Offline retrieval evaluation</h2>
        <p className="mb-3 text-xs text-muted">
          Deterministic retrieval-quality metrics on a fixed case set — offline, never a live or paid run.
        </p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {quality.map((q) => (
            <Card key={q.label}>
              <CardBody>
                <p className="text-xl font-semibold text-foreground">{q.value}</p>
                <p className="mt-1 text-xs text-muted">{q.label}</p>
              </CardBody>
            </Card>
          ))}
        </div>
      </section>

      {data.known_gaps.length ? (
        <section>
          <h2 className="text-sm font-semibold text-foreground">Known coverage gaps</h2>
          <p className="mb-2 text-xs text-muted">Honest, documented limitations — not failures.</p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
            {data.known_gaps.map((g, i) => (
              <li key={i}>{g}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <p className="text-xs text-muted">
        Counts and metrics come from committed evidence artifacts. No embeddings, raw retrieval
        contents, prompts or secrets are exposed.
      </p>
    </div>
  );
}
