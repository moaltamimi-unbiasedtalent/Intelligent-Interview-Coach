"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { ReportResponse } from "@/lib/api/types";
import { Card, CardBody } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";

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
  const [data, setData] = useState<ReportResponse | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<{ message: string; requestId?: string | null } | null>(null);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    api.interviews.report(sessionId)
      .then((r) => { if (alive) { setData(r); setStatus("ready"); } })
      .catch((e) => {
        if (!alive) return;
        const err = e as ApiError;
        setError({ message: err.userMessage ?? "Couldn't load your performance review.", requestId: err.requestId });
        setStatus("error");
      });
    return () => { alive = false; };
  }, [sessionId]);

  if (status === "loading") return <LoadingState label="Creating your performance review" />;
  if (status === "error" && error) return <ErrorState message={error.message} requestId={error.requestId} />;
  if (!data) return null;

  const report = data.report as Report;
  return (
    <div className="space-y-4">
      <Card>
        <CardBody>
          <h1 className="text-lg font-semibold">Performance review</h1>
          {typeof report.overall_readiness_score === "number" ? (
            <p className="mt-1 text-sm text-muted">
              Practice readiness:{" "}
              <span className="text-2xl font-semibold text-foreground">{report.overall_readiness_score}</span>/100
            </p>
          ) : null}
          <p className="mt-1 text-xs text-muted">
            Practice guidance to help you prepare — not an employment decision.
          </p>
          {report.performance_summary ? (
            <p className="mt-3 whitespace-pre-wrap text-sm">{report.performance_summary}</p>
          ) : null}
          {data.save_failed ? (
            <p className="mt-3 text-sm text-danger">
              Your review is ready, but saving it to your history didn&rsquo;t complete. You can retry from History.
            </p>
          ) : null}
        </CardBody>
      </Card>

      <ListCard title="Key strengths" items={report.strongest_competencies} />
      <ListCard title="Priority improvements" items={report.development_priorities} />
      <ListCard title="Recurring answer patterns" items={report.recurring_answer_patterns} />
      <ListCard title="Highest-risk questions" items={report.highest_risk_questions} />
      <ListCard title="Evidence gaps" items={report.evidence_gaps} />
      <ListCard title="Recommended practice actions" items={report.recommended_practice_actions} />
      <ListCard title="Final interview checklist" items={report.final_interview_checklist} />
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
