"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { ApiError, stateKeyForError } from "@/lib/api/errors";
import { useT } from "@/components/i18n/I18nProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { ButtonLink } from "@/components/ui/Button";
import { EmptyState, EmptyStateIllustration, ErrorState, LoadingState } from "@/components/ui/States";

/** User-scoped interview history from /history/interviews. In-place recoverable (P10B-W9.2). */
export function HistoryClient() {
  const t = useT();
  const [rows, setRows] = useState<Array<Record<string, unknown>> | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<ApiError | null>(null);
  const [retrying, setRetrying] = useState(false);
  const ctrlRef = useRef<AbortController | null>(null);

  // Safe re-runnable GET: aborts any in-flight load (latest wins; a stale response can never
  // overwrite a newer success), and never replays a write.
  const load = useCallback((isRetry = false) => {
    ctrlRef.current?.abort();
    const ctrl = new AbortController();
    ctrlRef.current = ctrl;
    if (isRetry) setRetrying(true);
    else setStatus("loading");
    api.history
      .list({ signal: ctrl.signal })
      .then((r) => {
        if (ctrl.signal.aborted) return;
        setRows(r.interviews);
        setError(null);
        setStatus("ready");
        setRetrying(false);
      })
      .catch((e) => {
        if (ctrl.signal.aborted || (e instanceof DOMException && e.name === "AbortError")) return;
        setError(e as ApiError);
        setStatus("error");
        setRetrying(false);
      });
  }, []);

  useEffect(() => {
    load();
    return () => ctrlRef.current?.abort();
  }, [load]);

  return (
    <section data-tour="history">
      <PageHeader eyebrow={t("history.eyebrow")} title={t("history.title")} description={t("history.description")} />
      <p className="-mt-2 mb-4 text-sm">
        <a href="/help#history" className="font-medium text-accent underline">{t("history.whatAppears")}</a>
      </p>
      {status === "loading" ? <LoadingState label={t("history.loading")} /> : null}
      {status === "error" && error ? (
        <ErrorState
          message={t(stateKeyForError(error.kind))}
          requestId={error.requestId}
          retrying={retrying}
          onRetry={() => load(true)}
        />
      ) : null}
      {status === "ready" ? (
        rows && rows.length ? (
          <div className="grid gap-3">
            {rows.map((row, i) => {
              const id = row.id as number | undefined;
              const role = (row.target_role as string | undefined) ?? null;
              const questions = row.questions as number | undefined;
              const created = row.created_at
                ? new Date(String(row.created_at)).toLocaleDateString()
                : null;
              const meta = [
                role,
                typeof questions === "number" ? t("history.questionCount", { n: questions }) : null,
                created,
              ]
                .filter(Boolean)
                .join(" · ");
              const body = (
                <CardBody>
                  <p className="font-medium">
                    {role ? role : t("history.interviewNumber", { n: String(id ?? i + 1) })}
                  </p>
                  {meta ? <p className="mt-1 text-sm text-muted">{meta}</p> : null}
                </CardBody>
              );
              return id != null ? (
                <Link
                  key={id}
                  href={`/history/${id}`}
                  className="block rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
                >
                  <Card className="transition-colors hover:bg-surface-2">{body}</Card>
                </Link>
              ) : (
                <Card key={i}>{body}</Card>
              );
            })}
          </div>
        ) : (
          <EmptyState
            title={t("history.emptyTitle")}
            description={t("history.emptyDescription")}
            illustration={
              <EmptyStateIllustration
                src="/images/ask4mo/ask4mo-empty-history-ink.png"
                alt={t("history.emptyAlt")}
              />
            }
            action={
              <div className="flex flex-wrap gap-2">
                <ButtonLink href="/practice">{t("history.startPractice")}</ButtonLink>
                <ButtonLink href="/help#history" variant="ghost">{t("history.learnAbout")}</ButtonLink>
              </div>
            }
          />
        )
      ) : null}
    </section>
  );
}
