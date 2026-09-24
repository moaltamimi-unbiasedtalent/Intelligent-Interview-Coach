"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { InterviewDetail } from "@/lib/api/types";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { ButtonLink } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { ReportView, type Report } from "@/components/interview/ReportView";
import { useT } from "@/components/i18n/I18nProvider";

/** A single completed interview from /history/interviews/{id} — user-scoped. */
export function HistoryDetailClient({ reportId }: { reportId: string }) {
  const t = useT();
  const [interview, setInterview] = useState<InterviewDetail | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "notfound" | "error">("loading");
  const [error, setError] = useState<{ message: string; requestId?: string | null } | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    api.history
      .get(reportId, { signal: ctrl.signal })
      .then((r) => {
        setInterview(r.interview);
        setStatus("ready");
      })
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        const err = e as ApiError;
        // A foreign or unknown id returns 404 → safe not-found (never another user's data).
        if (err.status === 404) {
          setStatus("notfound");
          return;
        }
        setError({ message: err.userMessage ?? "Couldn't load this session.", requestId: err.requestId });
        setStatus("error");
      });
    return () => ctrl.abort();
  }, [reportId]);

  const role = (interview?.configuration?.target_role as string | undefined) ?? null;
  const created = interview?.created_at ? new Date(interview.created_at).toLocaleString() : null;
  const report = (interview?.report?.report ?? null) as Report | null;

  return (
    <section>
      <PageHeader
        eyebrow="Your sessions"
        title={role ? `Interview — ${role}` : `Interview #${reportId}`}
        description={created ? `Completed ${created}` : "Completed interview session"}
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <ButtonLink href="/history" variant="ghost">← Back to history</ButtonLink>
        {status === "ready" && report ? (
          <span className="flex items-center gap-2 text-sm">
            <span className="text-muted">{t("documents.exportReport")}:</span>
            <a href={api.reports.exportMarkdownUrl(Number(reportId))} className="text-accent hover:underline">
              {t("documents.exportMarkdown")}
            </a>
            <a href={api.reports.exportJsonUrl(Number(reportId))} className="text-accent hover:underline">
              {t("documents.exportJson")}
            </a>
          </span>
        ) : null}
      </div>

      {status === "loading" ? <LoadingState label="Loading session" /> : null}
      {status === "error" && error ? <ErrorState message={error.message} requestId={error.requestId} /> : null}
      {status === "notfound" ? (
        <EmptyState
          title="Session not found"
          description="This session doesn't exist or isn't yours."
          action={<ButtonLink href="/history">Back to history</ButtonLink>}
        />
      ) : null}
      {status === "ready" ? (
        report ? (
          <ReportView report={report} />
        ) : (
          <Card>
            <CardBody>
              <p className="text-sm text-muted">
                This session was completed but has no saved performance review.
              </p>
            </CardBody>
          </Card>
        )
      ) : null}
    </section>
  );
}
