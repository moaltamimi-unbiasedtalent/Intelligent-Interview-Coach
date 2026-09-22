"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { EvaluationRunResponse } from "@/lib/api/types";
import { Card, CardBody } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";

/**
 * Read-only view of the latest stored (offline) RAGAS evaluation run. This shows an
 * already-computed evidence artifact — it NEVER triggers a paid evaluation. It is
 * OFFLINE engineering evaluation, deliberately separate from live product diagnostics.
 */
export function EvaluationClient() {
  const [data, setData] = useState<EvaluationRunResponse | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<{ message: string; requestId?: string | null } | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    api.evaluation
      .latest({ signal: ctrl.signal })
      .then((r) => {
        setData(r);
        setStatus("ready");
      })
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        const err = e as ApiError;
        setError({ message: err.userMessage ?? "Couldn't load evaluation results.", requestId: err.requestId });
        setStatus("error");
      });
    return () => ctrl.abort();
  }, []);

  if (status === "loading") return <LoadingState label="Loading evaluation" />;
  if (status === "error" && error) return <ErrorState message={error.message} requestId={error.requestId} />;

  if (!data || !data.available) {
    return (
      <EmptyState
        title="No stored evaluation run yet"
        description="Deterministic retrieval evaluation and the optional RAGAS generation-quality layer run through the repository scripts; a completed RAGAS run appears here read-only. Paid evaluation never runs from this page."
      />
    );
  }

  const metrics = data.metrics ?? {};
  const cfg = (data.run_config ?? {}) as Record<string, unknown>;
  const str = (k: string) => (cfg[k] != null ? String(cfg[k]) : null);
  const configRows: Array<[string, string | null]> = [
    ["Run", str("timestamp")],
    ["Status", str("status")],
    ["Cases", str("case_count")],
    ["Referenced cases", str("referenced_case_count")],
    ["Score coverage", cfg.score_coverage != null ? `${Math.round(Number(cfg.score_coverage) * 100)}%` : null],
    ["RAGAS version", str("ragas_version")],
    ["Evaluator model", str("evaluator_model")],
    ["Git commit", str("git_commit")],
  ];

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted">
        Latest stored RAGAS run (read-only artifact). This page never triggers a paid evaluation.
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Object.entries(metrics).map(([name, value]) => (
          <Card key={name}>
            <CardBody>
              <p className="text-2xl font-semibold text-foreground">
                {typeof value === "number" ? value.toFixed(3) : String(value)}
              </p>
              <p className="mt-1 text-xs text-muted">{name.replace(/_/g, " ")}</p>
            </CardBody>
          </Card>
        ))}
      </div>

      <Card>
        <CardBody>
          <h2 className="mb-2 text-sm font-semibold">Run configuration</h2>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
            {configRows
              .filter(([, v]) => v != null)
              .map(([label, v]) => (
                <div key={label} className="flex justify-between gap-4">
                  <dt className="text-muted">{label}</dt>
                  <dd className="font-medium text-foreground">{v}</dd>
                </div>
              ))}
          </dl>
        </CardBody>
      </Card>

      <p className="text-xs text-muted">
        These are offline generation-quality metrics on public benchmark data — not live candidate
        analytics and not a hiring signal.
      </p>
    </div>
  );
}
