"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { KnowledgeSnapshotResponse, KnowledgeSource } from "@/lib/api/types";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { ButtonLink } from "@/components/ui/Button";
import { useT } from "@/components/i18n/I18nProvider";

/** Candidate-friendly "career evidence" view, backed by /knowledge/*. In-place recoverable (W9.2). */
export function SourcesClient() {
  const t = useT();
  const [sources, setSources] = useState<KnowledgeSource[] | null>(null);
  const [snapshot, setSnapshot] = useState<KnowledgeSnapshotResponse | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<{ message: string; requestId?: string | null } | null>(null);
  const [retrying, setRetrying] = useState(false);
  const ctrlRef = useRef<AbortController | null>(null);

  const load = useCallback((isRetry = false) => {
    ctrlRef.current?.abort();
    const ctrl = new AbortController();
    ctrlRef.current = ctrl;
    if (isRetry) setRetrying(true);
    else setStatus("loading");
    Promise.all([
      api.knowledge.sources({ signal: ctrl.signal }),
      api.knowledge.snapshot({ signal: ctrl.signal }).catch(() => null),
    ])
      .then(([s, snap]) => {
        if (ctrl.signal.aborted) return;
        setSources(s.sources);
        setSnapshot(snap);
        setError(null);
        setStatus("ready");
        setRetrying(false);
      })
      .catch((e) => {
        if (ctrl.signal.aborted || (e instanceof DOMException && e.name === "AbortError")) return;
        const err = e as ApiError;
        setError({ message: err.userMessage ?? t("prepare.couldntLoadSources"), requestId: err.requestId });
        setStatus("error");
        setRetrying(false);
      });
  }, [t]);

  useEffect(() => {
    load();
    return () => ctrlRef.current?.abort();
  }, [load]);

  return (
    <section data-tour="sources">
      <PageHeader
        eyebrow={t("prepare.trust")}
        title={t("prepare.careerEvidence")}
        description={t("prepare.sourcesDescription")}
      />
      <p className="-mt-2 mb-4 text-sm">
        <a href="/help#sources" className="font-medium text-accent underline">{t("prepare.howAsk4MoUsesEvidence")}</a>
      </p>
      {status === "loading" ? <LoadingState label={t("prepare.loadingSources")} /> : null}
      {status === "error" && error ? (
        <ErrorState message={error.message} requestId={error.requestId} retrying={retrying} onRetry={() => load(true)} />
      ) : null}
      {status === "ready" ? (
        sources && sources.length ? (
          <>
            {snapshot ? (
              <p className="mb-4 text-sm text-muted">
                {t("prepare.snapshotIndexed", { documents: snapshot.documents, chunks: snapshot.chunks })}
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
                            {s.title || s.source_id || t("prepare.sourceFallback")}
                          </a>
                        ) : (
                          s.title || s.source_id || t("prepare.sourceFallback")
                        )}
                      </h2>
                      {s.group ? <p className="mt-1 text-sm text-muted">{s.group}</p> : null}
                      {meta ? <p className="mt-1 text-xs text-muted">{meta}</p> : null}
                      {!s.source_url ? (
                        <p className="mt-1 text-xs text-muted">{t("prepare.governedSource")}</p>
                      ) : null}
                    </CardBody>
                  </Card>
                );
              })}
            </div>
          </>
        ) : (
          <EmptyState
            title={t("prepare.indexNotReadyTitle")}
            description={t("prepare.indexNotReadyDesc")}
            action={<ButtonLink href="/help#sources">{t("prepare.howSourcesWork")}</ButtonLink>}
          />
        )
      ) : null}
    </section>
  );
}
