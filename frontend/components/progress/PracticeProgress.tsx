"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { ProgressResponse } from "@/lib/api/types";
import { Card, CardBody } from "@/components/ui/Card";

/**
 * Practice progress derived from the caller's own completed interviews (from
 * /progress). Practice guidance, never a score or hiring signal. Renders nothing
 * when the user has no practice yet — the surrounding memory view carries the
 * empty state — and a bounded, non-blocking note on error.
 */
export function PracticeProgress() {
  const [data, setData] = useState<ProgressResponse | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const ctrl = new AbortController();
    api.progress
      .get({ signal: ctrl.signal })
      .then((r) => {
        setData(r);
        setStatus("ready");
      })
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        void (e as ApiError);
        setStatus("error");
      });
    return () => ctrl.abort();
  }, []);

  if (status === "error") {
    return <p className="mb-6 text-sm text-muted">Couldn&rsquo;t load practice progress.</p>;
  }
  if (status !== "ready" || !data || !data.interviews_completed) {
    // No practice yet (or still loading, or a malformed/empty response): stay quiet;
    // the memory view owns the page. `!interviews_completed` covers 0/undefined/null.
    return null;
  }

  const tiles: Array<{ label: string; value: string }> = [
    { label: "Practice sessions", value: String(data.interviews_completed) },
    { label: "Answers evaluated", value: String(data.answers_evaluated) },
  ];
  if (typeof data.average_practice_score === "number") {
    tiles.push({ label: "Average practice score", value: `${data.average_practice_score}/100` });
  }
  if (typeof data.average_answer_seconds === "number") {
    tiles.push({ label: "Average answer time", value: `${Math.round(data.average_answer_seconds)}s` });
  }

  return (
    <div className="mb-8">
      <h2 className="text-sm font-semibold text-foreground">Practice progress</h2>
      <p className="mb-3 text-xs text-muted">
        From your completed practice interviews — guidance to help you prepare, not a score.
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {tiles.map((t) => (
          <Card key={t.label}>
            <CardBody>
              <p className="text-2xl font-semibold text-foreground">{t.value}</p>
              <p className="mt-1 text-xs text-muted">{t.label}</p>
            </CardBody>
          </Card>
        ))}
      </div>

      {data.most_common_improvement_area ? (
        <p className="mt-3 text-sm text-muted">
          Most common focus area:{" "}
          <span className="font-medium text-foreground">{data.most_common_improvement_area}</span>
        </p>
      ) : null}

      {data.recent_interviews.length ? (
        <div className="mt-4">
          <h3 className="mb-2 text-xs font-semibold text-muted">Recent sessions</h3>
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
                        {r.target_role ? r.target_role : `Interview #${r.id}`}
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
