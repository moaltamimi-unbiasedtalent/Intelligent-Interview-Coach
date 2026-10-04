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
import { DictationControl } from "@/components/ui/DictationControl";
import { useDictationLanguage } from "@/lib/speech/useDictationLanguage";
import { useOpportunityContext } from "@/lib/useOpportunityContext";
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
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { useT } from "@/components/i18n/I18nProvider";
import { DocumentPicker } from "@/components/documents/DocumentPicker";
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

/** Saved current-market-research capability preference (default ON). A harmless UI pref. */
function savedResearch(): boolean {
  try {
    return window.localStorage.getItem("agent.currentMarketResearch") !== "off";
  } catch {
    return true;
  }
}

/** Send `false` only when the user turned research OFF; otherwise keep the safe default. */
function researchFlag(): boolean | undefined {
  return savedResearch() ? undefined : false;
}

/** Candidate-facing Agent Coach — the LangGraph agent behind the Precision Coach UI. */
export function AgentPrepareWorkspace({ initialDraft }: { initialDraft?: PrepareDraft | null }) {
  const t = useT();
  const { run, busy, restoring, error, runId, start, send, resume, reset, clearError } = useAgentRun();
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const [mobileTab, setMobileTab] = useState<"coach" | "prep">("coach");
  // Mo conversation language (P3.5) + coaching style (P10B Wave 2): sent with every run from the
  // account preferences (independent of interface/dictation language; coaching tone never scores).
  // Undefined → server defaults (English / balanced).
  const account = useAuthOptional()?.account;
  const conversationLanguage = account?.conversation_language ?? undefined;
  const coachingStyle = account?.coaching_style ?? undefined;
  const startRun = useCallback(
    (req: Parameters<typeof start>[0]) =>
      start({ ...req, conversation_language: conversationLanguage, coaching_style: coachingStyle }),
    [start, conversationLanguage, coachingStyle],
  );

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
    void startRun({ goal: goalDraft, profile: savedProfile(), enable_current_market_research: researchFlag() });
  }, [goalDraft, runId, run, restoring, startRun]);

  if (restoring && !run) {
    return (
      <section>
        <PageHeader eyebrow={t("prepare.eyebrow")} title={t("prepare.coachTitle")} />
        <LoadingState label={t("prepare.restoringSession")} />
      </section>
    );
  }

  // A bookmarked run that no longer exists: offer a clean restart (never fake it).
  if (error?.notFound && !run) {
    return (
      <section>
        <PageHeader eyebrow={t("prepare.eyebrow")} title={t("prepare.coachTitle")} />
        <ErrorState message={error.message} requestId={error.requestId} />
        <div className="mt-4">
          <Button onClick={reset}>{t("prepare.startNewPreparation")}</Button>
        </div>
      </section>
    );
  }

  if (!run) {
    return (
      <section>
        <PageHeader
          eyebrow={t("prepare.eyebrow")}
          title={t("prepare.coachTitle")}
          description={t("prepare.coachDescription")}
        />
        <FirstMessageForm
          onStart={startRun}
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
          disabledHint={t("prepare.answerAboveToContinue")}
        />
      )}

      {!busy && !run.awaiting_human_input && usageSummaryLine(run, t) ? (
        <p className="mt-3 text-xs text-muted" role="status" aria-label={t("prepare.runUsageAria")}>
          {usageSummaryLine(run, t)}
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
          {error.paused ? t("states.platformPaused") : error.message}
          {error.requestId ? <span className="block text-xs text-muted">{t("prepare.reference", { id: error.requestId })}</span> : null}
        </p>
      ) : null}

      <div className="mt-4">{runId ? <AgentRunLink runId={runId} /> : null}</div>
      {runId ? <HandoffRunner run={run} runId={runId} /> : null}
    </div>
  );

  const rail = <AgentContextRail run={run} />;

  return (
    <section>
      <PageHeader eyebrow={t("prepare.eyebrow")} title={t("prepare.coachTitle")} />
      {isDesktop ? (
        <div className="grid grid-cols-[minmax(0,1fr)_320px] gap-6">
          <div>{coach}</div>
          <aside aria-label={t("prepare.preparationContextAria")}>{rail}</aside>
        </div>
      ) : (
        <div>
          <div role="tablist" aria-label={t("prepare.coachAndPrepAria")} className="mb-4 flex gap-2">
            <button role="tab" aria-selected={mobileTab === "coach"} onClick={() => setMobileTab("coach")}
              className={tabClass(mobileTab === "coach")}>Mo</button>
            <button role="tab" aria-selected={mobileTab === "prep"} onClick={() => setMobileTab("prep")}
              className={tabClass(mobileTab === "prep")}>{t("prepare.preparationTab")}</button>
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
  const t = useT();
  if (!run.memory_used || run.memory_count === 0) return null;
  const loaded = run.memory_loaded ?? [];
  return (
    <details className="mb-3 rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm">
      <summary className="cursor-pointer text-muted">
        {t(run.memory_count === 1 ? "prepare.savedMemory_one" : "prepare.savedMemory_other", { count: run.memory_count })}
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
        <a href="/settings" className="text-accent underline">{t("prepare.manageInSettings")}</a>
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
  onStart: (req: { goal: string; target_role?: string; job_description?: string; candidate_background?: string; job_description_document_id?: number; profile?: AgentProfile; enable_current_market_research?: boolean }) => void;
  busy: boolean;
  error: { message: string; requestId?: string | null; notFound?: boolean } | null;
  onDismissError: () => void;
  /** Prefill the goal from a Home handoff so it is never re-typed (§11/§12). */
  initialGoal?: string;
  /** A Home shortcut opens + focuses the matching context field (§15/§16). */
  openContextField?: "jd" | "bg" | null;
}) {
  const t = useT();
  const [goal, setGoal] = useState(initialGoal);
  const [showContext, setShowContext] = useState(!!openContextField);
  const [targetRole, setTargetRole] = useState("");
  const [jd, setJd] = useState("");
  const [jdDocId, setJdDocId] = useState<number | null>(null);
  const [background, setBackground] = useState("");
  const [profile, setProfile] = useState<AgentProfile>(DEFAULT_PROFILE);
  const [research, setResearch] = useState(true);

  // P10B Wave 6: when Prepare is opened from an Opportunity (`?opportunity=<id>`), pre-populate the
  // role + JD context (the candidate can still edit them; never overrides an explicit entry).
  const { opportunity } = useOpportunityContext();
  const oppPrefilled = useRef(false);
  const [oppNote, setOppNote] = useState(false);
  useEffect(() => {
    if (!opportunity || oppPrefilled.current) return;
    oppPrefilled.current = true;
    setOppNote(true);
    setShowContext(true);
    if (opportunity.target_role) setTargetRole((cur) => cur || opportunity.target_role);
    if (opportunity.jd_available && opportunity.job_description_document_id) {
      setJdDocId((cur) => cur ?? opportunity.job_description_document_id ?? null);
    }
  }, [opportunity]);
  // Dictation recognition locale — deliberately SEPARATE from the (future) application
  // locale, the model profile and the response-detail preference.
  const [dictationLang, setDictationLang] = useDictationLanguage();

  // A harmless UI preference (the chosen speed) may be remembered — never any private
  // conversation data (§21). Guarded so private windows / blocked storage never throw.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem("agent.profile");
      if (saved === "fast" || saved === "balanced" || saved === "advanced") setProfile(saved);
      setResearch(window.localStorage.getItem("agent.currentMarketResearch") !== "off");
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

  const toggleResearch = (on: boolean) => {
    setResearch(on);
    try {
      window.localStorage.setItem("agent.currentMarketResearch", on ? "on" : "off");
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
      // A selected JD document is resolved server-side (owner-scoped); a pasted JD takes priority.
      job_description_document_id: !jd.trim() && jdDocId ? jdDocId : undefined,
      candidate_background: background.trim() || undefined,
      profile,
      enable_current_market_research: research ? undefined : false,
    });
  }

  return (
    <Card>
      <CardBody className="space-y-3">
        <label htmlFor="agent-goal" className="block text-sm font-medium">{t("prepare.whatPreparingFor")}</label>
        <Textarea
          id="agent-goal"
          data-tour="target-role"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder={t("prepare.goalPlaceholder")}
          disabled={busy}
          maxLength={4000}
        />
        {/* Dictation is input-only: recognised speech is appended to the editable goal;
            starting is never submitting (§6). */}
        <DictationControl
          value={goal}
          onChange={(next) => setGoal(next)}
          disabled={busy}
          lang={dictationLang}
          onLangChange={setDictationLang}
        />

        {oppNote ? (
          <p className="rounded border border-border bg-surface-2 px-3 py-2 text-sm text-muted">
            {t("opportunity.savedNote")}
          </p>
        ) : null}

        <button type="button" onClick={() => setShowContext((v) => !v)} className="text-sm font-medium text-accent">
          {showContext ? t("prepare.hideExtraContext") : t("prepare.addContextOptional")}
        </button>

        {showContext ? (
          <div className="space-y-3">
            <div>
              <label htmlFor="agent-role" className="block text-sm text-muted">{t("prepare.targetRoleOptional")}</label>
              <Input id="agent-role" value={targetRole} onChange={(e) => setTargetRole(e.target.value)} disabled={busy} maxLength={200} />
            </div>
            <div>
              <label htmlFor="agent-jd" className="block text-sm text-muted">{t("prepare.jobDescriptionOptional")}</label>
              <Textarea id="agent-jd" value={jd} onChange={(e) => setJd(e.target.value)} disabled={busy} maxLength={12000} className="min-h-[100px]" />
            </div>
            {/* Or SELECT a stored JD from the one governed document system (P10B Wave 4). A pasted
                JD above takes priority; a selected document is resolved to text server-side. */}
            {!jd.trim() ? (
              <DocumentPicker category="job_description" value={jdDocId} onChange={setJdDocId}
                              label={t("prepctx.jobDescriptionDoc")} disabled={busy} />
            ) : null}
            <div>
              <label htmlFor="agent-bg" className="block text-sm text-muted">{t("prepare.yourBackgroundOptional")}</label>
              <Textarea id="agent-bg" value={background} onChange={(e) => setBackground(e.target.value)} disabled={busy} maxLength={12000} className="min-h-[100px]" />
            </div>
          </div>
        ) : null}

        <AgentProfileSelector value={profile} onChange={chooseProfile} disabled={busy} />

        <label className="flex items-center gap-2 text-sm text-muted">
          <input
            type="checkbox"
            checked={research}
            onChange={(e) => toggleResearch(e.target.checked)}
            disabled={busy}
            aria-label={t("prepare.allowResearchAria")}
          />
          <span>
            {t("prepare.allowResearch")}{" "}
            <span className="text-xs">{t("prepare.researchHint")}</span>
          </span>
        </label>

        <div className="flex items-center justify-between">
          <span className="text-xs text-muted" aria-live="polite">{busy ? t("prepare.startingSession") : ""}</span>
          <Button data-tour="ask-mo" onClick={submit} disabled={!canStart}>{busy ? t("prepare.starting") : t("prepare.startPreparing")}</Button>
        </div>

        {error && !error.notFound ? (
          <p role="alert" className="text-sm text-danger">
            {error.message}
            {error.requestId ? <span className="block text-xs text-muted">{t("prepare.reference", { id: error.requestId })}</span> : null}
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
  const t = useT();
  const router = useRouter();
  const attempted = useRef(false);
  const [needsConfig, setNeedsConfig] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const idempotencyKey = `agent-handoff:${runId}`;

  const create = useCallback(
    async (extra?: { industry_or_sector: string; career_level: string }) => {
      const ctx = run.preparation_context as (Record<string, unknown> & { target_role?: string }) | null | undefined;
      if (!ctx?.target_role) {
        setError(t("prepare.notReadyForPractice"));
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
          setError(err.message || err.userMessage || t("prepare.couldntStartPractice"));
        }
      }
    },
    [router, run.preparation_context, idempotencyKey, t],
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
      {error ? <span role="alert" className="text-danger">{error}</span> : t("prepare.settingUpPractice")}
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
  const t = useT();
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
        <p className="font-medium">{t("prepare.oneLastDetail")}</p>
        <div>
          <label htmlFor="handoff-industry" className="block text-sm text-muted">{t("prepare.industrySector")}</label>
          <Input id="handoff-industry" value={industry} onChange={(e) => setIndustry(e.target.value)} maxLength={200} disabled={busy} />
        </div>
        <div>
          <label htmlFor="handoff-level" className="block text-sm text-muted">{t("prepare.careerLevel")}</label>
          <select
            id="handoff-level"
            value={careerLevel}
            onChange={(e) => setCareerLevel(e.target.value)}
            disabled={busy}
            className="w-full rounded-lg border border-border bg-surface px-3.5 py-3 disabled:opacity-60"
          >
            <option value="">{t("prepare.selectPlaceholder")}</option>
            {levels.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>
        {/* Busy state guards against duplicate/concurrent submits (backend idempotency
            via the agent-handoff key remains the real safety boundary — §14/§15). */}
        <Button size="sm" disabled={!ready} onClick={() => { setBusy(true); onSubmit(industry.trim(), careerLevel); }}>
          {busy ? t("prepare.startingPractice") : t("prepare.startPractice")}
        </Button>
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
      </CardBody>
    </Card>
  );
}
