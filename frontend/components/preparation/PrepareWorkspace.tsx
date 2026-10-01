"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { CareerChatResponse } from "@/lib/api/types";
import type { PrepareDraft } from "@/lib/prepareDraft";
import { CoachActivity, CoachMessage } from "@/components/coach/CoachMessage";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Input, Textarea } from "@/components/ui/Field";
import { useT } from "@/components/i18n/I18nProvider";
import { CareerAnswer } from "./CareerAnswer";
import { PrepareResponsive } from "./PrepareResponsive";
import { PreparationTools, type PrepContextPatch } from "./PreparationTools";
import { RoleContext } from "./RoleContext";
import { StageProgress } from "./StageProgress";
import { StartPracticeButton, type PrepState } from "./StartPracticeButton";

interface Turn {
  id: string;
  question: string;
  status: "loading" | "done" | "error";
  response?: CareerChatResponse;
  error?: string;
  requestId?: string | null;
}

export function PrepareWorkspace({ initialDraft }: { initialDraft?: PrepareDraft | null }) {
  // Named `tr` (not `t`) because the turns array is mapped with a `t` element below.
  const tr = useT();
  const activityLabel = tr("prepare.activityChecking");
  const goalDraft = initialDraft?.action === "start" ? (initialDraft.goal?.trim() ?? "") : "";
  const draftOpensContext =
    initialDraft?.action === "job_description" || initialDraft?.action === "candidate_background";

  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState(goalDraft);
  const [showContext, setShowContext] = useState(!!draftOpensContext);
  const [jd, setJd] = useState("");
  const [bg, setBg] = useState("");
  const [prep, setPrep] = useState<PrepState>({});
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const autoAsked = useRef(false);

  function patchPrep(p: PrepContextPatch) {
    setPrep((prev) => ({ ...prev, ...p }));
  }

  async function runQuestion(q: string) {
    if (!q || busy) return;
    setBusy(true);
    const id =
      typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
    setTurns((t) => [...t, { id, question: q, status: "loading" }]);
    setQuestion("");
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const res = await api.career.chat(
        {
          question: q,
          job_description: jd.trim() || undefined,
          candidate_background: bg.trim() || undefined,
        },
        { signal: ctrl.signal },
      );
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, status: "done", response: res } : x)));
      if (jd.trim()) patchPrep({ jobDescription: jd.trim() });
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      const err = e as ApiError;
      setTurns((t) =>
        t.map((x) =>
          x.id === id
            ? { ...x, status: "error", error: err.userMessage ?? tr("prepare.requestFailed"), requestId: err.requestId }
            : x,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  function ask(e: React.FormEvent) {
    e.preventDefault();
    void runQuestion(question.trim());
  }

  // Home → Prepare handoff (deterministic fallback §14): a "start" draft submits the
  // transferred goal automatically (once); a shortcut opens + focuses the right field.
  useEffect(() => {
    if (autoAsked.current) return;
    autoAsked.current = true;
    if (goalDraft) {
      void runQuestion(goalDraft);
    } else if (initialDraft?.action === "job_description") {
      window.document.getElementById("ctx-jd")?.focus();
    } else if (initialDraft?.action === "candidate_background") {
      window.document.getElementById("ctx-bg")?.focus();
    }
    // Run once on mount for the initial handoff.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const lastResponse = [...turns].reverse().find((t) => t.status === "done")?.response;

  const coach = (
    <div className="animate-enter">
      {turns.length === 0 ? (
        <Card>
          <CardBody>
            <h2 className="text-lg font-semibold">{tr("prepare.tellMoPreparing")}</h2>
            <p className="mt-1 text-muted">{tr("prepare.askAboutRole")}</p>
          </CardBody>
        </Card>
      ) : (
        <div className="grid gap-3.5" aria-live="polite">
          {turns.map((t) => (
            <div key={t.id} className="grid gap-3.5">
              <CoachMessage from="you">{t.question}</CoachMessage>
              {t.status === "loading" ? <CoachActivity label={activityLabel} /> : null}
              {t.status === "done" && t.response ? <CareerAnswer response={t.response} /> : null}
              {t.status === "error" ? (
                <div role="alert" className="rounded-lg border border-danger bg-surface px-4 py-3 text-sm">
                  <p className="text-foreground">{t.error}</p>
                  {t.requestId ? <p className="mt-1 text-xs text-muted">{tr("prepare.reference", { id: t.requestId })}</p> : null}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}

      <form onSubmit={ask} className="mt-4">
        <div className="flex items-center gap-2 rounded-lg border border-border bg-surface p-2 pl-3.5 shadow-soft">
          <label htmlFor="prep-q" className="sr-only">{tr("prepare.askTheCoach")}</label>
          <Input
            id="prep-q"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={4000}
            placeholder={tr("prepare.whatPreparingFor")}
            className="border-0 bg-transparent px-1 py-1 shadow-none focus-visible:outline-none"
          />
          <Button type="submit" size="sm" disabled={busy || !question.trim()}>
            {busy ? tr("prepare.sending") : tr("prepare.ask")}
          </Button>
        </div>
        <button
          type="button"
          onClick={() => setShowContext((s) => !s)}
          aria-expanded={showContext}
          className="mt-2 text-sm text-muted hover:text-foreground"
        >
          {showContext ? tr("prepare.hideContext") : tr("prepare.addContext")}
        </button>
        {showContext ? (
          <div className="mt-3 grid gap-3 rounded-lg border border-border bg-surface p-4">
            <div>
              <label htmlFor="ctx-jd" className="text-sm font-medium">{tr("prepare.jobDescription")} <span className="text-muted">{tr("prepare.optional")}</span></label>
              <Textarea id="ctx-jd" value={jd} onChange={(e) => setJd(e.target.value)} placeholder={tr("prepare.pasteJobDescription")} className="mt-1 min-h-[90px]" />
            </div>
            <div>
              <label htmlFor="ctx-bg" className="text-sm font-medium">{tr("prepare.aboutYou")} <span className="text-muted">{tr("prepare.optional")}</span></label>
              <Textarea id="ctx-bg" value={bg} onChange={(e) => setBg(e.target.value)} placeholder={tr("prepare.experiencePlaceholderLong")} className="mt-1 min-h-[80px]" />
              <p className="mt-1 text-xs text-muted">{tr("prepare.usedToPersonalise")}</p>
            </div>
          </div>
        ) : null}
      </form>
    </div>
  );

  const context = (
    <>
      <Card>
        <CardBody>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{tr("prepare.targetRole")}</h3>
          <p className="mt-1 text-sm">{prep.targetRole ? prep.targetRole : <span className="text-muted">{tr("prepare.notSetYetAnalyze")}</span>}</p>
        </CardBody>
      </Card>
      {prep.strengths?.length ? (
        <Card><CardBody>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{tr("prepare.yourStrengths")}</h3>
          <ul className="mt-1.5 space-y-1 text-sm">{prep.strengths.slice(0, 6).map((s, i) => <li key={i}>{s}</li>)}</ul>
        </CardBody></Card>
      ) : null}
      {prep.priorities?.length ? (
        <Card><CardBody>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{tr("prepare.prioritiesToPrepare")}</h3>
          <ul className="mt-1.5 space-y-1 text-sm">{prep.priorities.slice(0, 6).map((s, i) => <li key={i}>{s}</li>)}</ul>
        </CardBody></Card>
      ) : null}
      {lastResponse && lastResponse.sources.length ? (
        <Card><CardBody>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{tr("prepare.careerEvidence")}</h3>
          <p className="mt-1.5 text-sm text-muted">{tr(lastResponse.sources.length === 1 ? "prepare.sourcesBehind_one" : "prepare.sourcesBehind_other", { count: lastResponse.sources.length })}</p>
        </CardBody></Card>
      ) : null}
      <Card>
        <CardBody className="grid gap-2.5">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{tr("prepare.readyWhenYouAre")}</h3>
          <StartPracticeButton prep={prep} />
        </CardBody>
      </Card>
    </>
  );

  return (
    <section>
      <div className="mb-4"><StageProgress current="Prepare" /></div>
      {prep.targetRole ? (
        <div className="mb-5"><RoleContext data={{ role: prep.targetRole, seniority: prep.seniority || undefined }} /></div>
      ) : null}
      <PrepareResponsive coach={coach} context={context} />
      <details className="mt-8 rounded-lg border border-border bg-surface">
        <summary className="cursor-pointer px-5 py-4 font-semibold">{tr("prepare.preparationTools")}</summary>
        <div className="border-t border-border p-5">
          <PreparationTools onContext={patchPrep} />
        </div>
      </details>
    </section>
  );
}
