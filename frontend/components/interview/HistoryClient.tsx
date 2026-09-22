"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { ButtonLink } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";

/** User-scoped interview history from /history/interviews. */
export function HistoryClient() {
  const [rows, setRows] = useState<Array<Record<string, unknown>> | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<{ message: string; requestId?: string | null } | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    api.history
      .list({ signal: ctrl.signal })
      .then((r) => {
        setRows(r.interviews);
        setStatus("ready");
      })
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        const err = e as ApiError;
        setError({ message: err.userMessage ?? "Couldn't load history.", requestId: err.requestId });
        setStatus("error");
      });
    return () => ctrl.abort();
  }, []);

  return (
    <section>
      <PageHeader eyebrow="Your sessions" title="History" description="Completed interview sessions and their reports." />
      {status === "loading" ? <LoadingState label="Loading history" /> : null}
      {status === "error" && error ? <ErrorState message={error.message} requestId={error.requestId} /> : null}
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
                typeof questions === "number" ? `${questions} question(s)` : null,
                created,
              ]
                .filter(Boolean)
                .join(" · ");
              const body = (
                <CardBody>
                  <p className="font-medium">
                    {role ? role : `Interview #${String(id ?? i + 1)}`}
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
            title="Completed interview sessions will appear here"
            description="Finish a practice interview to see its report."
            action={<ButtonLink href="/practice">Practise an interview</ButtonLink>}
          />
        )
      ) : null}
    </section>
  );
}
