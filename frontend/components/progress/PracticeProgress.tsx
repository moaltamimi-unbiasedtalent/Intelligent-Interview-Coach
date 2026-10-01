"use client";

import Link from "next/link";
import type { ProgressResponse } from "@/lib/api/types";
import { useT } from "@/components/i18n/I18nProvider";
import { Card, CardBody } from "@/components/ui/Card";

/**
 * Practice progress derived from the caller's own completed interviews (from /progress).
 * Practice guidance, never a score or hiring signal.
 *
 * P10B-W9.2: this is now a PURE presentational component. The parent (`ProgressClient`) owns the
 * network lifecycle for BOTH page regions (practice + memory) so it can present coherent degraded
 * states (one region can fail/recover without blanking the other, and both failing collapse to a
 * single page-level error). Renders nothing when there is no practice yet — the memory view owns
 * the page-level empty state — and `!interviews_completed` covers 0/undefined/null.
 */
export function PracticeProgress({ data }: { data: ProgressResponse | null }) {
  const t = useT();
  if (!data || !data.interviews_completed) {
    return null;
  }

  const tiles: Array<{ label: string; value: string }> = [
    { label: t("progress.practiceSessions"), value: String(data.interviews_completed) },
    { label: t("progress.answersEvaluated"), value: String(data.answers_evaluated) },
  ];
  if (typeof data.average_practice_score === "number") {
    tiles.push({ label: t("progress.averageScore"), value: `${data.average_practice_score}/100` });
  }
  if (typeof data.average_answer_seconds === "number") {
    tiles.push({ label: t("progress.averageAnswerTime"), value: `${Math.round(data.average_answer_seconds)}s` });
  }

  return (
    <div className="mb-8">
      <h2 className="text-sm font-semibold text-foreground">{t("progress.practiceTitle")}</h2>
      <p className="mb-3 text-xs text-muted">
        {t("progress.practiceSubtitleGuidance")}
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {tiles.map((tile) => (
          <Card key={tile.label}>
            <CardBody>
              <p className="text-2xl font-semibold text-foreground">{tile.value}</p>
              <p className="mt-1 text-xs text-muted">{tile.label}</p>
            </CardBody>
          </Card>
        ))}
      </div>

      {data.most_common_improvement_area ? (
        <p className="mt-3 text-sm text-muted">
          {t("progress.mostCommonFocus")}{" "}
          <span className="font-medium text-foreground">{data.most_common_improvement_area}</span>
        </p>
      ) : null}

      {data.recent_interviews.length ? (
        <div className="mt-4">
          <h3 className="mb-2 text-xs font-semibold text-muted">{t("progress.recentSessions")}</h3>
          <div className="grid gap-2">
            {data.recent_interviews.map((r) => {
              const created = r.created_at ? new Date(r.created_at).toLocaleDateString() : null;
              const meta = [r.target_role, created].filter(Boolean).join(" · ");
              return (
                <Link
                  key={r.id}
                  href={`/history/${r.id}`}
                  className="block rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
                >
                  <Card className="transition-colors hover:bg-surface-2">
                    <CardBody className="py-3">
                      <p className="text-sm font-medium">
                        {r.target_role ? r.target_role : t("progress.interviewNumber", { id: r.id })}
                      </p>
                      {meta ? <p className="mt-0.5 text-xs text-muted">{meta}</p> : null}
                    </CardBody>
                  </Card>
                </Link>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}
