"use client";

import { useEffect, useState } from "react";
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
            {rows.map((row, i) => (
              <Card key={(row.id as number) ?? i}>
                <CardBody>
                  <p className="font-medium">Interview #{String(row.id ?? i + 1)}</p>
                </CardBody>
              </Card>
            ))}
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
