"use client";

import type { AgentSource } from "@/lib/api/types";
import { useT } from "@/components/i18n/I18nProvider";

/**
 * Candidate-facing career evidence from Agentic RAG. Shows only safe provenance
 * (title, source, geography, year) — never doc/chunk ids, scores or embeddings.
 */
export function AgentSources({ sources }: { sources: AgentSource[] }) {
  const t = useT();
  if (!sources.length) return null;
  return (
    <details className="mt-2 rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm">
      <summary className="cursor-pointer font-medium">
        {sources.length === 1
          ? t("prepare.evidenceSourcesOne")
          : t("prepare.evidenceSourcesOther", { n: sources.length })}
      </summary>
      <p className="mt-1 text-xs text-muted">{t("trustUx.sourcesHint")}</p>
      <ol className="mt-2 space-y-2">
        {sources.map((s, i) => (
          <li key={i} className="text-muted">
            <span className="mr-1 font-mono text-xs" aria-hidden="true">[{i + 1}]</span>
            {s.source_url ? (
              <a href={s.source_url} target="_blank" rel="noopener noreferrer" className="font-medium text-foreground underline">
                {s.title ?? s.source_url}
              </a>
            ) : (
              <span className="font-medium text-foreground">{s.title ?? t("prepare.sourceUntitled")}</span>
            )}
            <span className="ml-2 text-xs">
              {[s.evidence_type, s.geography, s.reference_year].filter(Boolean).join(" · ")}
            </span>
          </li>
        ))}
      </ol>
    </details>
  );
}
