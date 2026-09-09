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
import { AgentProfileSelector, DEFAULT_PROFILE, usageSummaryLine } from "./usage";
import { JourneyChrome, PreparationChecklist } from "./JourneyChrome";
import { FeedbackControl } from "@/components/feedback/FeedbackControl";
import type { AgentProfile } from "@/lib/api/types";
import type { PrepareDraft } from "@/lib/prepareDraft";

/** The saved candidate speed preference, or Balanced (§13). Never a raw model name. */
function savedProfile(): AgentProfile {
  try {
    const s = window.localStorage.getItem("agent.profile");
    if (s === "fast" || s === "balanced" || s === "advanced") return s;
  } catch {
    /* storage unavailable — fall through to the default */
  }
  return DEFAULT_PROFILE;
}

/** Candidate-facing Agent Coach — the LangGraph agent behind the Precision Coach UI. */
export function AgentPrepareWorkspace({ initialDraft }: { initialDraft?: PrepareDraft | null }) {
  const { run, busy, restoring, error, runId, start, send, resume, reset, clearError } = useAgentRun();
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const [mobileTab, setMobileTab] = useState<"coach" | "prep">("coach");

  // Home → Prepare handoff. Auto-start EXACTLY ONCE from a "start" draft, and only
  // when no run is being restored/active — an existing ?run= always wins (§9/§21/§26).
  const autoStarted = useRef(false);
  const goalDraft = initialDraft?.action === "start" ? (initialDraft.goal?.trim() ?? "") : "";
  const openContextField =
    initialDraft?.action === "job_description" ? "jd"
      : initialDraft?.action === "candidate_background" ? "bg"
      : null;
  useEffect(() => {
    if (autoStarted.current) return;
    if (!goalDraft) return;
    if (runId || run || restoring) return; // restored/active run takes precedence
    autoStarted.current = true;
    void start({ goal: goalDraft, profile: savedProfile() });
  }, [goalDraft, runId, run, restoring, start]);

  if (restoring && !run) {
    return (
      <section>
        <PageHeader eyebrow="Prepare" title="Mo — your interview coach" />
        <LoadingState label="Restoring your preparation session" />
      </section>
    );
  }

  // A bookmarked run that no longer exists: offer a clean restart (never fake it).
  if (error?.notFound && !run) {
    return (
      <section>
        <PageHeader eyebrow="Prepare" title="Mo — your interview coach" />
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
          title="Mo — your interview coach"
          description="Tell Mo what you're preparing for and get a focused preparation plan."
        />
        <FirstMessageForm
          onStart={start}
          busy={busy}
          error={error}
          onDismissError={clearError}
          initialGoal={goalDraft}
          openContextField={openContextField}
        />
      </section>
    );
  }

  const coach = (
    <div>
      <JourneyChrome journey={run.journey} />
      <PreparationChecklist journey={run.journey} />
      <MemoryLoadedCue run={run} />
      <AgentConversation run={run} busy={busy} messages={run.conversation} />

      {run.awaiting_human_input && run.pending_action ? (
        <div className="mt-4">
          <PendingHumanActionCard action={run.pending_action} busy={busy} onDecision={resume} handoffSummary={run.handoff_summary} />
        </div>
      ) : (
        <AgentComposer
          onSend={send}
          busy={busy}
          disabled={run.awaiting_human_input}
          disabledHint="Answer the request above to continue."
        />
      )}

      {!busy && !run.awaiting_human_input && usageSummaryLine(run) ? (
        <p className="mt-3 text-xs text-muted" role="status" aria-label="Run usage">
          {usageSummaryLine(run)}
        </p>
      ) : null}

      {(() => {
        // Feedback on the latest visible assistant answer — never while awaiting HITL,
        // on a failed run, or when there is no answer (§19).
        if (busy || run.awaiting_human_input || run.status === "failed") return null;
        const answers = run.conversation.filter((m) => m.role === "assistant" && m.response_id);
        const latest = answers[answers.length - 1];
        if (!latest?.response_id || !latest.content.trim()) return null;
        return <FeedbackControl surface="agent_answer" targetId={latest.response_id} />;
      })()}

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
      {runId ? <HandoffRunner run={run} runId={runId} /> : null}
    </div>
  );

  const rail = <AgentContextRail run={run} />;

  return (
    <section>
      <PageHeader eyebrow="Prepare" title="Mo — your interview coach" />
      {isDesktop ? (
        <div className="grid grid-cols-[minmax(0,1fr)_320px] gap-6">
          <div>{coach}</div>
          <aside aria-label="Preparation context">{rail}</aside>
        </div>
      ) : (
        <div>
          <div role="tablist" aria-label="Coach and preparation" className="mb-4 flex gap-2">
            <button role="tab" aria-selected={mobileTab === "coach"} onClick={() => setMobileTab("coach")}
              className={tabClass(mobileTab === "coach")}>Mo</button>
            <button role="tab" aria-selected={mobileTab === "prep"} onClick={() => setMobileTab("prep")}
              className={tabClass(mobileTab === "prep")}>Preparation</button>
          </div>
          {mobileTab === "coach" ? coach : rail}
        </div>
      )}
    </section>
  );
}

/** Safe cue that saved preparation memory was used this run (count + inspectable
 * summaries only — never checkpoint, prompt formatting or internal state). §35. */
function MemoryLoadedCue({ run }: { run: { memory_used: boolean; memory_count: number; memory_loaded?: { category: string; summary: string; target_role: string | null }[] } }) {
  if (!run.memory_used || run.memory_count === 0) return null;
  const loaded = run.memory_loaded ?? [];
  return (
    <details className="mb-3 rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm">
      <summary className="cursor-pointer text-muted">
        Using {run.memory_count} saved preparation {run.memory_count === 1 ? "memory" : "memories"}
      </summary>
      {loaded.length ? (
        <ul className="mt-2 grid gap-1">
          {loaded.map((m, i) => (
            <li key={i} className="break-words">
              <span className="text-muted">{m.category}:</span> {m.summary}
              {m.target_role ? <span className="text-muted"> ({m.target_role})</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      <p className="mt-2 text-xs text-muted">
        <a href="/settings" className="text-accent underline">Manage in Settings</a>
      </p>
    </details>
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
  initialGoal = "",
  openContextField = null,
}: {
  onStart: (req: { goal: string; target_role?: string; job_description?: string; candidate_background?: string; profile?: AgentProfile }) => void;
  busy: boolean;
  error: { message: string; requestId?: string | null; notFound?: boolean } | null;
  onDismissError: () => void;
  /** Prefill the goal from a Home handoff so it is never re-typed (§11/§12). */
  initialGoal?: string;
  /** A Home shortcut opens + focuses the matching context field (§15/§16). */
  openContextField?: "jd" | "bg" | null;
}) {
  const [goal, setGoal] = useState(initialGoal);
  const [showContext, setShowContext] = useState(!!openContextField);
  const [targetRole, setTargetRole] = useState("");
  const [jd, setJd] = useState("");
  const [background, setBackground] = useState("");
  const [profile, setProfile] = useState<AgentProfile>(DEFAULT_PROFILE);

  // A harmless UI preference (the chosen speed) may be remembered — never any private
  // conversation data (§21). Guarded so private windows / blocked storage never throw.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem("agent.profile");
      if (saved === "fast" || saved === "balanced" || saved === "advanced") setProfile(saved);
    } catch {
      /* storage unavailable — keep the default */
    }
  }, []);

  // Focus the field the Home entry pointed at (accessibility §17) — the JD or the
  // background for a shortcut, otherwise the goal box when it arrives prefilled.
  useEffect(() => {
    const id = openContextField === "jd" ? "agent-jd"
      : openContextField === "bg" ? "agent-bg"
      : initialGoal ? "agent-goal"
      : null;
    if (id) window.document.getElementById(id)?.focus();
    // Run once on mount for the initial handoff.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const chooseProfile = (p: AgentProfile) => {
    setProfile(p);
    try {
      window.localStorage.setItem("agent.profile", p);
    } catch {
      /* ignore */
    }
  };

  const canStart = !busy && goal.trim().length > 0;

  function submit() {
    if (!canStart) return;
    onDismissError();
    onStart({
      goal: goal.trim(),
      target_role: targetRole.trim() || undefined,
      job_description: jd.trim() || undefined,
      candidate_background: background.trim() || undefined,
      profile,
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

        <AgentProfileSelector value={profile} onChange={chooseProfile} disabled={busy} />

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
 * PreparationContext and navigate to /practice. Creation happens in the FRONTEND
 * (never inside LangGraph) and is idempotent: the same handoff (keyed by the agent
 * run id) resolves to the SAME session across double-click, refresh, remount or
 * retry. Missing industry/career level are requested explicitly — never fabricated.
 */
function HandoffRunner({
  run,
  runId,
}: {
  run: { handoff_approved: boolean; preparation_context?: unknown };
  runId: string;
}) {
  const router = useRouter();
  const attempted = useRef(false);
  const [needsConfig, setNeedsConfig] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const idempotencyKey = `agent-handoff:${runId}`;

  const create = useCallback(
    async (extra?: { industry_or_sector: string; career_level: string }) => {
      const ctx = run.preparation_context as (Record<string, unknown> & { target_role?: string }) | null | undefined;
      if (!ctx?.target_role) {
        setError("Your preparation isn't ready for practice yet.");
        return;
      }
      try {
        // Send the PreparationContext (backend derives industry/seniority→career_level);
        // include user-supplied gap-fillers only when the backend asked for them.
        const session = await api.interviews.create(
          { preparation_context: ctx as never, ...(extra ?? {}) },
          { idempotencyKey },
        );
        // `from=coach` lets Practice show honest "prepared in Coach" provenance (P4);
        // a standalone Practice has no such flag and shows no provenance.
        router.push(`/practice?session=${encodeURIComponent(session.session_id)}&from=coach`);
      } catch (e) {
        const err = e as ApiError;
        // Show the completion form ONLY for the specific missing-config case (stable
        // backend code) — never inferred from status 422 alone, which also covers other
        // validation problems. Any other error surfaces the backend's safe, actionable
        // message (falling back to a calm default), so the candidate never sees a bare
        // "check the information" when a better message exists.
        if (err.code === "missing_interview_handoff_config" && !extra) {
          setNeedsConfig(true);
        } else {
          setError(err.message || err.userMessage || "Couldn't start practice.");
        }
      }
    },
    [router, run.preparation_context, idempotencyKey],
  );

  useEffect(() => {
    if (run.handoff_approved && !attempted.current) {
      attempted.current = true;
      void create();
    }
  }, [run.handoff_approved, create]);

  if (!run.handoff_approved) return null;
  if (needsConfig) {
    return (
      <HandoffCompletionCard
        onSubmit={(industry_or_sector, career_level) => { setError(null); void create({ industry_or_sector, career_level }); }}
        error={error}
      />
    );
  }
  return (
    <div role="status" className="mt-3 text-sm text-muted">
      {error ? <span role="alert" className="text-danger">{error}</span> : "Setting up your interview practice…"}
    </div>
  );
}

/** Asks ONLY for the genuinely-missing interview configuration (§3), using the
 * backend career-level taxonomy as the single source of truth. */
function HandoffCompletionCard({
  onSubmit,
  error,
}: {
  onSubmit: (industry: string, careerLevel: string) => void;
  error: string | null;
}) {
  const [industry, setIndustry] = useState("");
  const [careerLevel, setCareerLevel] = useState("");
  const [levels, setLevels] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    api.interviews.options({ signal: ctrl.signal }).then((o) => setLevels(o.career_levels)).catch(() => setLevels([]));
    return () => ctrl.abort();
  }, []);

  // Re-enable the button if creation came back with an error (allow a retry).
  useEffect(() => { if (error) setBusy(false); }, [error]);

  const ready = industry.trim().length > 0 && careerLevel.length > 0 && !busy;

  return (
    <Card className="mt-3 border-accent">
      <CardBody className="space-y-3">
        <p className="font-medium">One last detail before practice</p>
        <div>
          <label htmlFor="handoff-industry" className="block text-sm text-muted">Industry / sector</label>
          <Input id="handoff-industry" value={industry} onChange={(e) => setIndustry(e.target.value)} maxLength={200} disabled={busy} />
        </div>
        <div>
          <label htmlFor="handoff-level" className="block text-sm text-muted">Career level</label>
          <select
            id="handoff-level"
            value={careerLevel}
            onChange={(e) => setCareerLevel(e.target.value)}
            disabled={busy}
            className="w-full rounded-lg border border-border bg-surface px-3.5 py-3 disabled:opacity-60"
          >
            <option value="">Select…</option>
            {levels.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>
        {/* Busy state guards against duplicate/concurrent submits (backend idempotency
            via the agent-handoff key remains the real safety boundary — §14/§15). */}
        <Button size="sm" disabled={!ready} onClick={() => { setBusy(true); onSubmit(industry.trim(), careerLevel); }}>
          {busy ? "Starting practice…" : "Start practice"}
        </Button>
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
      </CardBody>
    </Card>
  );
}
