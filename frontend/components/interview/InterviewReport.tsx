"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { ReportResponse } from "@/lib/api/types";
import { Card, CardBody } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { FeedbackControl } from "@/components/feedback/FeedbackControl";
import { useT } from "@/components/i18n/I18nProvider";

/** Fields the backend FinalInterviewReport actually provides (no invented metrics). */
interface Report {
  overall_readiness_score?: number;
  performance_summary?: string;
  strongest_competencies?: string[];
  development_priorities?: string[];
  recurring_answer_patterns?: string[];
  highest_risk_questions?: string[];
  evidence_gaps?: string[];
  recommended_practice_actions?: string[];
  final_interview_checklist?: string[];
}

/**
 * Performance Review — the complete FinalInterviewReport rendered as practice
 * guidance. The readiness score is explicitly practice readiness, never a hiring or
 * employment probability.
 */
export function InterviewReport({ sessionId }: { sessionId: string }) {
  const t = useT();
  const [data, setData] = useState<ReportResponse | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<{ message: string; requestId?: string | null } | null>(null);
  const [retrying, setRetrying] = useState(false);
  const ctrlRef = useRef<AbortController | null>(null);

  // Safe re-runnable GET (P10B-W9.2): report retrieval is idempotent; aborts any in-flight load.
  const load = useCallback((isRetry = false) => {
    ctrlRef.current?.abort();
    const ctrl = new AbortController();
    ctrlRef.current = ctrl;
    if (isRetry) setRetrying(true);
    else setStatus("loading");
    api.interviews.report(sessionId, { signal: ctrl.signal })
      .then((r) => {
        if (ctrl.signal.aborted) return;
        setData(r);
        setError(null);
        setStatus("ready");
        setRetrying(false);
      })
      .catch((e) => {
        if (ctrl.signal.aborted || (e instanceof DOMException && e.name === "AbortError")) return;
        const err = e as ApiError;
        setError({ message: err.userMessage ?? t("practice.reportLoadError"), requestId: err.requestId });
        setStatus("error");
        setRetrying(false);
      });
  }, [sessionId, t]);

  useEffect(() => {
    load();
    return () => ctrlRef.current?.abort();
  }, [load]);

  if (status === "loading") return <LoadingState label={t("practice.reportCreating")} />;
  if (status === "error" && error) {
    return <ErrorState message={error.message} requestId={error.requestId} retrying={retrying} onRetry={() => load(true)} />;
  }
  if (!data) return null;

  const report = data.report as Report;
  return (
    <div className="space-y-4">
      <Card>
        <CardBody>
          <h1 className="text-lg font-semibold">{t("practice.reportTitle")}</h1>
          {typeof report.overall_readiness_score === "number" ? (
            <p className="mt-1 text-sm text-muted">
              {t("practice.readinessLabel")}{" "}
              <span className="text-2xl font-semibold text-foreground">{report.overall_readiness_score}</span>/100
            </p>
          ) : null}
          <p className="mt-1 text-xs text-muted">
            {t("practice.reportDisclaimer")}
          </p>
          {report.performance_summary ? (
            <p className="mt-3 whitespace-pre-wrap text-sm">{report.performance_summary}</p>
          ) : null}
          {data.save_failed ? (
            <p className="mt-3 text-sm text-danger">
              {t("practice.reportSaveFailed")}
            </p>
          ) : null}
        </CardBody>
      </Card>

      <ListCard title={t("practice.reportStrengths")} items={report.strongest_competencies} />
      <ListCard title={t("practice.reportImprovements")} items={report.development_priorities} />
      <ListCard title={t("practice.reportPatterns")} items={report.recurring_answer_patterns} />
      <ListCard title={t("practice.reportRiskQuestions")} items={report.highest_risk_questions} />
      <ListCard title={t("practice.reportEvidenceGaps")} items={report.evidence_gaps} />
      <ListCard title={t("practice.reportActions")} items={report.recommended_practice_actions} />
      <ListCard title={t("practice.reportChecklist")} items={report.final_interview_checklist} />

      <Card>
        <CardBody>
          <FeedbackControl surface="final_report" targetId={sessionId} prompt={t("feedback.reportPrompt")} />
        </CardBody>
      </Card>
    </div>
  );
}

function ListCard({ title, items }: { title: string; items?: string[] }) {
  if (!items?.length) return null;
  return (
    <Card>
      <CardBody>
        <h2 className="text-sm font-semibold">{title}</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
          {items.map((it, i) => <li key={i}>{it}</li>)}
        </ul>
      </CardBody>
    </Card>
  );
}
