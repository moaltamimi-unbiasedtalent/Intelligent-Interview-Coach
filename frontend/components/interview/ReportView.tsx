import { Card, CardBody } from "@/components/ui/Card";

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
  return (
    <div className="space-y-4">
      <Card>
        <CardBody>
          <h1 className="text-lg font-semibold">Performance review</h1>
          {typeof report.overall_readiness_score === "number" ? (
            <p className="mt-1 text-sm text-muted">
              Practice readiness:{" "}
              <span className="text-2xl font-semibold text-foreground">
                {report.overall_readiness_score}
              </span>
              /100
            </p>
          ) : null}
          <p className="mt-1 text-xs text-muted">
            Practice guidance to help you prepare — not an employment decision.
          </p>
          {report.performance_summary ? (
            <p className="mt-3 whitespace-pre-wrap text-sm">{report.performance_summary}</p>
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
          {items.map((it, i) => (
            <li key={i}>{it}</li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}
