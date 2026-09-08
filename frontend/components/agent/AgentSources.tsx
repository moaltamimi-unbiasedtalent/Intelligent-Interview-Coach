"use client";

import type { AgentSource } from "@/lib/api/types";

/**
 * Candidate-facing career evidence from Agentic RAG. Shows only safe provenance
 * (title, source, geography, year) — never doc/chunk ids, scores or embeddings.
 */
export function AgentSources({ sources }: { sources: AgentSource[] }) {
  if (!sources.length) return null;
  return (
    <details className="mt-2 rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm">
      <summary className="cursor-pointer font-medium">
        Career evidence: {sources.length} source{sources.length === 1 ? "" : "s"}
      </summary>
      <ul className="mt-2 space-y-2">
        {sources.map((s, i) => (
          <li key={i} className="text-muted">
            {s.source_url ? (
              <a href={s.source_url} target="_blank" rel="noopener noreferrer" className="font-medium text-foreground underline">
                {s.title ?? s.source_url}
              </a>
            ) : (
              <span className="font-medium text-foreground">{s.title ?? "Source"}</span>
            )}
            <span className="ml-2 text-xs">
              {[s.evidence_type, s.geography, s.reference_year].filter(Boolean).join(" · ")}
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}
