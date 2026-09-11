"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { AgentEvent, AgentRunResponse } from "@/lib/api/types";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Field";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { toolLabel } from "./labels";
import { UsageDetails } from "./usage";

/** Safe, owner-scoped Agent Inspector: observable execution only — never
 * chain-of-thought, prompts, raw messages or checkpoint state. */
export function AgentInspector() {
  const params = useSearchParams();
  const urlRun = params.get("run") ?? "";
  const [runId, setRunId] = useState(urlRun);
  const [run, setRun] = useState<AgentRunResponse | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">(urlRun ? "loading" : "idle");
  const [error, setError] = useState<{ message: string; requestId?: string | null } | null>(null);

  const load = useCallback((id: string, signal?: AbortSignal) => {
    if (!id.trim()) return;
    setStatus("loading");
    setError(null);
    api.agent
      .getRun(id.trim(), { signal })
      .then((r) => { setRun(r); setStatus("ready"); })
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        const err = e as ApiError;
        setError({
          message: err.status === 404 ? "That run was not found." : err.userMessage ?? "Couldn't load the run.",
          requestId: err.requestId,
        });
        setStatus("error");
      });
  }, []);

  useEffect(() => {
    if (!urlRun) return;
    const ctrl = new AbortController();
    load(urlRun, ctrl.signal);
    return () => ctrl.abort();
  }, [urlRun, load]);

  return (
    <section>
      <PageHeader
        eyebrow="Review & Diagnostics"
        title="Agent Inspector"
        description="See what Mo's Agent did — tools, retrieval, memory, HITL and usage — without exposing chain-of-thought, prompts or secrets."
      />

      <form
        className="mb-6 flex gap-2"
        onSubmit={(e) => { e.preventDefault(); load(runId); }}
      >
        <label htmlFor="run-id" className="sr-only">Run ID</label>
        <Input id="run-id" value={runId} onChange={(e) => setRunId(e.target.value)} placeholder="Enter a run ID" className="max-w-xs" />
        <Button size="sm" type="submit" disabled={!runId.trim()}>Inspect</Button>
      </form>

      {status === "idle" ? (
        <EmptyState title="Enter a run ID to inspect" description="Open a run from the Coach's “View run details”, or paste a run ID above." />
      ) : null}
      {status === "loading" ? <LoadingState label="Loading run" /> : null}
      {status === "error" && error ? <ErrorState message={error.message} requestId={error.requestId} /> : null}
      {status === "ready" && run ? <InspectorView run={run} /> : null}
    </section>
  );
}

function InspectorView({ run }: { run: AgentRunResponse }) {
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-6">
        <RunSummary run={run} />
        <AgentTimeline events={run.events} />
      </div>
      <aside className="space-y-6">
        <ToolExecutionList run={run} />
        <RetrievalSummary run={run} />
        <HumanDecisionSummary run={run} />
        <RunWarnings run={run} />
      </aside>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 text-sm">
      <span className="text-muted">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}

function RunSummary({ run }: { run: AgentRunResponse }) {
  return (
    <Card>
      <CardBody className="space-y-2">
        <h2 className="text-sm font-semibold">Run summary</h2>
        <Row label="Run ID" value={<code className="text-xs">{run.run_id}</code>} />
        <Row label="Status" value={<StatusBadge status={run.status} />} />
        <Row label="Steps (turn / total)" value={`${run.turn_step_count} / ${run.step_count}`} />
        <Row label="Tools used" value={run.tools_used.length} />
        <Row label="Retrieval used" value={run.retrieval_used ? "Yes" : "No"} />
        <Row label="Sources" value={run.sources.length} />
        {run.resolved_occupation ? <Row label="Resolved occupation" value={run.resolved_occupation} /> : null}
        {run.resolved_geography ? <Row label="Resolved geography" value={run.resolved_geography} /> : null}
        <Row label="Memory used" value={run.memory_used ? `Yes (${run.memory_count})` : "No"} />
        {run.journey ? (
          <>
            <Row label="Journey · Understand" value={(run.journey.understand?.status ?? "—").replace(/_/g, " ")} />
            <Row label="Journey · Prepare" value={(run.journey.prepare?.status ?? "—").replace(/_/g, " ")} />
            <Row label="Journey · Practise" value={(run.journey.practise?.status ?? "—").replace(/_/g, " ")} />
          </>
        ) : null}
        <Row label="Handoff prepared" value={run.handoff_summary ? "Yes" : "No"} />
        <Row label="Handoff approved" value={run.handoff_approved ? "Yes" : "No"} />
        <div className="border-t border-border pt-2">
          <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted">Usage &amp; performance</h3>
          <UsageDetails run={run} />
        </div>
      </CardBody>
    </Card>
  );
}

function StatusBadge({ status }: { status: string }) {
  const tone = status === "failed" ? "high" : status === "awaiting_human_input" ? "medium" : "low";
  return <Badge tone={tone}>{status.replace(/_/g, " ")}</Badge>;
}

const EVENT_LABEL: Record<string, string> = {
  run_started: "Run started",
  memory_loaded: "Saved preparation reviewed",
  request_understood: "Request understood",
  tool_requested: "Tool requested",
  tool_started: "Tool started",
  tool_completed: "Tool completed",
  tool_failed: "Tool failed",
  tool_rejected: "Tool rejected",
  human_input_required: "Human confirmation requested",
  human_input_resumed: "Human decision applied",
  human_input_rejected: "Human declined",
  memory_saved: "Memory saved",
  memory_save_failed: "Memory save failed",
  handoff_approved: "Practice handoff approved",
  step_limit_reached: "Step limit reached",
  run_completed: "Run completed",
  run_failed: "Run failed",
};

function AgentTimeline({ events }: { events: AgentEvent[] }) {
  if (!events.length) return null;
  return (
    <Card>
      <CardBody>
        <h2 className="mb-3 text-sm font-semibold">Execution timeline</h2>
        <ol className="space-y-2">
          {events.map((e, i) => {
            const label = EVENT_LABEL[e.event_type] ?? e.event_type.replace(/_/g, " ");
            const detail = e.tool_name ? toolLabel(e.tool_name) : e.message ?? null;
            return (
              <li key={i} className="flex items-start gap-3 text-sm">
                <span aria-hidden className="mt-1 inline-block h-2 w-2 shrink-0 rounded-full bg-accent" />
                <span>
                  <span className="font-medium">{label}</span>
                  {detail ? <span className="text-muted"> — {detail}</span> : null}
                  {typeof e.source_count === "number" && e.source_count > 0 ? (
                    <span className="text-muted"> ({e.source_count} source{e.source_count === 1 ? "" : "s"})</span>
                  ) : null}
                  {typeof e.duration_ms === "number" ? <span className="text-muted"> · {e.duration_ms}ms</span> : null}
                </span>
              </li>
            );
          })}
        </ol>
      </CardBody>
    </Card>
  );
}

function ToolExecutionList({ run }: { run: AgentRunResponse }) {
  if (!run.tool_calls.length) return null;
  return (
    <Card>
      <CardBody>
        <h2 className="mb-2 text-sm font-semibold">Tool calls</h2>
        <ul className="space-y-1.5 text-sm">
          {run.tool_calls.map((t, i) => (
            <li key={i} className="flex items-center justify-between gap-2">
              <span>{toolLabel(t.tool)}</span>
              <span className="flex items-center gap-1.5">
                {t.status === "error" && t.category ? (
                  <span className="text-xs text-muted">{t.category.replace(/_/g, " ")}</span>
                ) : null}
                <Badge tone={t.status === "ok" ? "low" : t.status === "rejected" ? "high" : "medium"}>{t.status}</Badge>
              </span>
            </li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}

function RetrievalSummary({ run }: { run: AgentRunResponse }) {
  if (!run.retrieval_used && !run.sources.length) return null;
  return (
    <Card>
      <CardBody>
        <h2 className="mb-2 text-sm font-semibold">Retrieval</h2>
        <Row label="Sources" value={run.sources.length} />
        <ul className="mt-2 space-y-1 text-sm text-muted">
          {run.sources.map((s, i) => (
            <li key={i}>{s.title ?? s.source_url ?? "Source"}{s.reference_year ? ` · ${s.reference_year}` : ""}</li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}

function HumanDecisionSummary({ run }: { run: AgentRunResponse }) {
  const requested = run.events.filter((e) => e.event_type === "human_input_required").length;
  // An applied approval surfaces as its outcome event: role-confirm emits
  // `human_input_resumed`, while approved memory/handoff emit their domain success events
  // (`memory_saved` / `handoff_approved`). Count all three so the "Applied" total reflects
  // the approvals that actually took effect (a rejected decision emits
  // `human_input_rejected`, counted as Declined).
  const appliedTypes = new Set(["human_input_resumed", "memory_saved", "handoff_approved"]);
  const resumed = run.events.filter((e) => appliedTypes.has(e.event_type)).length;
  const rejected = run.events.filter((e) => e.event_type === "human_input_rejected").length;
  if (!requested && !resumed && !rejected) return null;
  return (
    <Card>
      <CardBody>
        <h2 className="mb-2 text-sm font-semibold">Human approvals</h2>
        <Row label="Requested" value={requested} />
        <Row label="Applied" value={resumed} />
        <Row label="Declined" value={rejected} />
      </CardBody>
    </Card>
  );
}

function RunWarnings({ run }: { run: AgentRunResponse }) {
  if (!run.warnings.length) return null;
  return (
    <Card>
      <CardBody>
        <h2 className="mb-2 text-sm font-semibold">Warnings</h2>
        <ul className="space-y-1 text-sm text-warning">
          {run.warnings.map((w, i) => <li key={i}>{w}</li>)}
        </ul>
      </CardBody>
    </Card>
  );
}
