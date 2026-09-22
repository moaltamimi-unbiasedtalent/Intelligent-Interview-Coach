"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { KnowledgeSnapshotResponse, KnowledgeSource } from "@/lib/api/types";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";

/** Candidate-friendly "career evidence" view, backed by /knowledge/*. */
export function SourcesClient() {
  const [sources, setSources] = useState<KnowledgeSource[] | null>(null);
  const [snapshot, setSnapshot] = useState<KnowledgeSnapshotResponse | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<{ message: string; requestId?: string | null } | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    Promise.all([
      api.knowledge.sources({ signal: ctrl.signal }),
      api.knowledge.snapshot({ signal: ctrl.signal }).catch(() => null),
    ])
      .then(([s, snap]) => {
        setSources(s.sources);
        setSnapshot(snap);
        setStatus("ready");
      })
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        const err = e as ApiError;
        setError({ message: err.userMessage ?? "Couldn't load sources.", requestId: err.requestId });
        setStatus("error");
      });
    return () => ctrl.abort();
  }, []);

  return (
    <section>
      <PageHeader
        eyebrow="Trust"
        title="Career evidence"
        description="Your preparation is grounded in curated, public career evidence — not opinions. You can always see where guidance comes from."
      />
      {status === "loading" ? <LoadingState label="Loading sources" /> : null}
      {status === "error" && error ? (
        <ErrorState message={error.message} requestId={error.requestId} />
      ) : null}
      {status === "ready" ? (
        sources && sources.length ? (
          <>
            {snapshot ? (
              <p className="mb-4 text-sm text-muted">
                {snapshot.documents} document(s) · {snapshot.chunks} passage(s) indexed.
              </p>
            ) : null}
            <div className="grid gap-4 sm:grid-cols-2">
              {sources.map((s, i) => {
                const meta = [s.provider, s.country, s.reference_year ? String(s.reference_year) : null]
                  .filter(Boolean)
                  .join(" · ");
                return (
                  <Card key={s.source_id ?? i}>
                    <CardBody>
                      <h2 className="text-base font-semibold">
                        {s.source_url ? (
                          <a
                            href={s.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="underline decoration-dotted underline-offset-4 hover:decoration-solid"
                          >
                            {s.title || s.source_id || "Source"}
                          </a>
                        ) : (
                          s.title || s.source_id || "Source"
                        )}
                      </h2>
                      {s.group ? <p className="mt-1 text-sm text-muted">{s.group}</p> : null}
                      {meta ? <p className="mt-1 text-xs text-muted">{meta}</p> : null}
                      {!s.source_url ? (
                        <p className="mt-1 text-xs text-muted">Governed source · no public record link</p>
                      ) : null}
                    </CardBody>
                  </Card>
                );
              })}
            </div>
          </>
        ) : (
          <EmptyState
            title="No sources are indexed yet"
            description="Career evidence appears here once the knowledge base is populated."
          />
        )
      ) : null}
    </section>
  );
}
