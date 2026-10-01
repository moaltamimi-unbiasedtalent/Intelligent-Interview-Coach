"use client";

import { Card, CardBody } from "@/components/ui/Card";
import { useT } from "@/components/i18n/I18nProvider";

/** Fields the backend FinalInterviewReport provides (no invented metrics). */
export interface Report {
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
 * Presentational Performance Review — renders a report object already in hand.
 * The readiness score is explicitly practice readiness, never a hiring probability.
 * Shared by the live practice report and the History detail view.
 */
export function ReportView({ report }: { report: Report }) {
  const t = useT();
  return (
    <div className="space-y-4">
      <Card>
        <CardBody>
          <h1 className="text-lg font-semibold">{t("practice.reportTitle")}</h1>
          {typeof report.overall_readiness_score === "number" ? (
            <p className="mt-1 text-sm text-muted">
              {t("practice.readinessLabel")}{" "}
              <span className="text-2xl font-semibold text-foreground">
                {report.overall_readiness_score}
              </span>
              /100
            </p>
          ) : null}
          <p className="mt-1 text-xs text-muted">
            {t("practice.reportDisclaimer")}
          </p>
          {report.performance_summary ? (
            <p className="mt-3 whitespace-pre-wrap text-sm">{report.performance_summary}</p>
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
          {items.map((it, i) => (
            <li key={i}>{it}</li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}
