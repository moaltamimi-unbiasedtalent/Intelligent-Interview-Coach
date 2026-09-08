"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { HumanDecisionRequest } from "@/lib/api/types";
import { useMediaQuery } from "@/lib/useMediaQuery";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Field";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { Card, CardBody } from "@/components/ui/Card";
import { useAgentRun } from "./useAgentRun";
import { AgentConversation } from "./AgentConversation";
import { AgentComposer } from "./AgentComposer";
import { AgentContextRail } from "./AgentContextRail";
import { PendingHumanActionCard } from "./PendingHumanActionCard";
import { AgentRunLink } from "./AgentRunLink";

/** Candidate-facing Agent Coach — the LangGraph agent behind the Precision Coach UI. */
export function AgentPrepareWorkspace() {
  const { run, busy, restoring, error, runId, start, send, resume, reset, clearError } = useAgentRun();
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const [mobileTab, setMobileTab] = useState<"coach" | "prep">("coach");

  if (restoring && !run) {
    return (
      <section>
        <PageHeader eyebrow="Prepare" title="Your interview coach" />
        <LoadingState label="Restoring your preparation session" />
      </section>
    );
  }

  // A bookmarked run that no longer exists: offer a clean restart (never fake it).
  if (error?.notFound && !run) {
    return (
      <section>
        <PageHeader eyebrow="Prepare" title="Your interview coach" />
        <ErrorState message={error.message} requestId={error.requestId} />
        <div className="mt-4">
          <Button onClick={reset}>Start new preparation</Button>
        </div>
      </section>
    );
  }

  if (!run) {
    return (
      <section>
        <PageHeader
          eyebrow="Prepare"
          title="Your interview coach"
          description="Tell me what interview you're preparing for and I'll help you get ready."
        />
        <FirstMessageForm onStart={start} busy={busy} error={error} onDismissError={clearError} />
      </section>
    );
  }

  const coach = (
    <div>
      <AgentConversation run={run} busy={busy} messages={run.conversation} />

      {run.awaiting_human_input && run.pending_action ? (
        <div className="mt-4">
          <PendingHumanActionCard action={run.pending_action} busy={busy} onDecision={resume} />
        </div>
      ) : (
        <AgentComposer
          onSend={send}
          busy={busy}
          disabled={run.awaiting_human_input}
          disabledHint="Answer the request above to continue."
        />
      )}

      {run.warnings.length ? (
        <ul className="mt-3 space-y-1" role="status">
          {run.warnings.map((w, i) => (
            <li key={i} className="text-xs text-warning">{w}</li>
          ))}
        </ul>
      ) : null}

      {error && !error.notFound ? (
        <p role="alert" className="mt-3 text-sm text-danger">
          {error.message}
          {error.requestId ? <span className="block text-xs text-muted">Reference: {error.requestId}</span> : null}
        </p>
      ) : null}

      <div className="mt-4">{runId ? <AgentRunLink runId={runId} /> : null}</div>
      <HandoffRunner run={run} />
    </div>
  );

  const rail = <AgentContextRail run={run} />;

  return (
    <section>
      <PageHeader eyebrow="Prepare" title="Your interview coach" />
      {isDesktop ? (
        <div className="grid grid-cols-[minmax(0,1fr)_320px] gap-6">
          <div>{coach}</div>
          <aside aria-label="Preparation context">{rail}</aside>
        </div>
      ) : (
        <div>
          <div role="tablist" aria-label="Coach and preparation" className="mb-4 flex gap-2">
            <button role="tab" aria-selected={mobileTab === "coach"} onClick={() => setMobileTab("coach")}
              className={tabClass(mobileTab === "coach")}>Coach</button>
            <button role="tab" aria-selected={mobileTab === "prep"} onClick={() => setMobileTab("prep")}
              className={tabClass(mobileTab === "prep")}>Preparation</button>
          </div>
          {mobileTab === "coach" ? coach : rail}
        </div>
      )}
    </section>
  );
}

function tabClass(active: boolean): string {
  return active
    ? "min-h-[40px] rounded-lg bg-accent px-4 text-sm font-semibold text-accent-foreground"
    : "min-h-[40px] rounded-lg border border-border px-4 text-sm font-semibold";
}

function FirstMessageForm({
  onStart,
  busy,
  error,
  onDismissError,
}: {
  onStart: (req: { goal: string; target_role?: string; job_description?: string; candidate_background?: string }) => void;
  busy: boolean;
  error: { message: string; requestId?: string | null; notFound?: boolean } | null;
  onDismissError: () => void;
}) {
  const [goal, setGoal] = useState("");
  const [showContext, setShowContext] = useState(false);
  const [targetRole, setTargetRole] = useState("");
  const [jd, setJd] = useState("");
  const [background, setBackground] = useState("");

  const canStart = !busy && goal.trim().length > 0;

  function submit() {
    if (!canStart) return;
    onDismissError();
    onStart({
      goal: goal.trim(),
      target_role: targetRole.trim() || undefined,
      job_description: jd.trim() || undefined,
      candidate_background: background.trim() || undefined,
    });
  }

  return (
    <Card>
      <CardBody className="space-y-3">
        <label htmlFor="agent-goal" className="block text-sm font-medium">What interview are you preparing for?</label>
        <Textarea
          id="agent-goal"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="e.g. I have a Senior Product Manager interview next week and want to prepare."
          disabled={busy}
          maxLength={4000}
        />

        <button type="button" onClick={() => setShowContext((v) => !v)} className="text-sm font-medium text-accent">
          {showContext ? "− Hide extra context" : "+ Add context (optional)"}
        </button>

        {showContext ? (
          <div className="space-y-3">
            <div>
              <label htmlFor="agent-role" className="block text-sm text-muted">Target role (optional)</label>
              <Input id="agent-role" value={targetRole} onChange={(e) => setTargetRole(e.target.value)} disabled={busy} maxLength={200} />
            </div>
            <div>
              <label htmlFor="agent-jd" className="block text-sm text-muted">Job description (optional)</label>
              <Textarea id="agent-jd" value={jd} onChange={(e) => setJd(e.target.value)} disabled={busy} maxLength={12000} className="min-h-[100px]" />
            </div>
            <div>
              <label htmlFor="agent-bg" className="block text-sm text-muted">Your background (optional)</label>
              <Textarea id="agent-bg" value={background} onChange={(e) => setBackground(e.target.value)} disabled={busy} maxLength={12000} className="min-h-[100px]" />
            </div>
          </div>
        ) : null}

        <div className="flex items-center justify-between">
          <span className="text-xs text-muted" aria-live="polite">{busy ? "Starting your session…" : ""}</span>
          <Button onClick={submit} disabled={!canStart}>{busy ? "Starting…" : "Start preparing"}</Button>
        </div>

        {error && !error.notFound ? (
          <p role="alert" className="text-sm text-danger">
            {error.message}
            {error.requestId ? <span className="block text-xs text-muted">Reference: {error.requestId}</span> : null}
          </p>
        ) : null}
      </CardBody>
    </Card>
  );
}

/**
 * After an approved practice handoff, create the Interview session from the returned
 * PreparationContext and navigate to /practice — creation happens in the FRONTEND
 * (never inside LangGraph), once, guarded against double-submit.
 */
function HandoffRunner({ run }: { run: { handoff_approved: boolean; preparation_context?: unknown } }) {
  const router = useRouter();
  const started = useRef(false);
  const [error, setError] = useState<string | null>(null);

  const go = useCallback(async () => {
    if (started.current) return;
    started.current = true;
    const ctx = run.preparation_context as
      | (Record<string, unknown> & { target_role?: string; industry?: string })
      | null
      | undefined;
    if (!ctx?.target_role) {
      setError("Your preparation isn't ready for practice yet.");
      return;
    }
    try {
      const session = await api.interviews.create({
        preparation_context: ctx as never,
        industry_or_sector: (ctx.industry as string) || "General",
        career_level: "senior",
      });
      router.push(`/practice?session=${encodeURIComponent(session.session_id)}`);
    } catch (e) {
      started.current = false; // allow a retry on genuine failure
      setError((e as ApiError).userMessage ?? "Couldn't start practice.");
    }
  }, [router, run.preparation_context]);

  useEffect(() => {
    if (run.handoff_approved) void go();
  }, [run.handoff_approved, go]);

  if (!run.handoff_approved) return null;
  return (
    <div role="status" className="mt-3 text-sm text-muted">
      {error ? <span role="alert" className="text-danger">{error}</span> : "Setting up your interview practice…"}
    </div>
  );
}
