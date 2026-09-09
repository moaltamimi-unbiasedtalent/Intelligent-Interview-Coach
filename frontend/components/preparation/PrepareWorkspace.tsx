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

const ACTIVITY = "Mo is checking relevant career evidence…";

export function PrepareWorkspace({ initialDraft }: { initialDraft?: PrepareDraft | null }) {
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
            ? { ...x, status: "error", error: err.userMessage ?? "That request couldn't be processed.", requestId: err.requestId }
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
            <h2 className="text-lg font-semibold">Tell Mo what you&rsquo;re preparing for</h2>
            <p className="mt-1 text-muted">
              Ask about the role, what to focus on, or how to prepare an answer. Add a
              job description below for more grounded guidance.
            </p>
          </CardBody>
        </Card>
      ) : (
        <div className="grid gap-3.5" aria-live="polite">
          {turns.map((t) => (
            <div key={t.id} className="grid gap-3.5">
              <CoachMessage from="you">{t.question}</CoachMessage>
              {t.status === "loading" ? <CoachActivity label={ACTIVITY} /> : null}
              {t.status === "done" && t.response ? <CareerAnswer response={t.response} /> : null}
              {t.status === "error" ? (
                <div role="alert" className="rounded-lg border border-danger bg-surface px-4 py-3 text-sm">
                  <p className="text-foreground">{t.error}</p>
                  {t.requestId ? <p className="mt-1 text-xs text-muted">Reference: {t.requestId}</p> : null}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}

      <form onSubmit={ask} className="mt-4">
        <div className="flex items-center gap-2 rounded-lg border border-border bg-surface p-2 pl-3.5 shadow-soft">
          <label htmlFor="prep-q" className="sr-only">Ask the coach</label>
          <Input
            id="prep-q"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={4000}
            placeholder="What interview are you preparing for?"
            className="border-0 bg-transparent px-1 py-1 shadow-none focus-visible:outline-none"
          />
          <Button type="submit" size="sm" disabled={busy || !question.trim()}>
            {busy ? "Sending…" : "Ask"}
          </Button>
        </div>
        <button
          type="button"
          onClick={() => setShowContext((s) => !s)}
          aria-expanded={showContext}
          className="mt-2 text-sm text-muted hover:text-foreground"
        >
          {showContext ? "− Hide context" : "＋ Add context"}
        </button>
        {showContext ? (
          <div className="mt-3 grid gap-3 rounded-lg border border-border bg-surface p-4">
            <div>
              <label htmlFor="ctx-jd" className="text-sm font-medium">Job description <span className="text-muted">(optional)</span></label>
              <Textarea id="ctx-jd" value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the job description…" className="mt-1 min-h-[90px]" />
            </div>
            <div>
              <label htmlFor="ctx-bg" className="text-sm font-medium">About you <span className="text-muted">(optional)</span></label>
              <Textarea id="ctx-bg" value={bg} onChange={(e) => setBg(e.target.value)} placeholder="A few lines about your experience so the coach can compare it with the role…" className="mt-1 min-h-[80px]" />
              <p className="mt-1 text-xs text-muted">Used only to personalise this preparation — not stored.</p>
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
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Target role</h3>
          <p className="mt-1 text-sm">{prep.targetRole ? prep.targetRole : <span className="text-muted">Not set yet — analyze a job description below.</span>}</p>
        </CardBody>
      </Card>
      {prep.strengths?.length ? (
        <Card><CardBody>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Your strengths</h3>
          <ul className="mt-1.5 space-y-1 text-sm">{prep.strengths.slice(0, 6).map((s, i) => <li key={i}>{s}</li>)}</ul>
        </CardBody></Card>
      ) : null}
      {prep.priorities?.length ? (
        <Card><CardBody>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Priorities to prepare</h3>
          <ul className="mt-1.5 space-y-1 text-sm">{prep.priorities.slice(0, 6).map((s, i) => <li key={i}>{s}</li>)}</ul>
        </CardBody></Card>
      ) : null}
      {lastResponse && lastResponse.sources.length ? (
        <Card><CardBody>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Career evidence</h3>
          <p className="mt-1.5 text-sm text-muted">{lastResponse.sources.length} source{lastResponse.sources.length === 1 ? "" : "s"} behind the latest answer.</p>
        </CardBody></Card>
      ) : null}
      <Card>
        <CardBody className="grid gap-2.5">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Ready when you are</h3>
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
        <summary className="cursor-pointer px-5 py-4 font-semibold">Preparation tools</summary>
        <div className="border-t border-border p-5">
          <PreparationTools onContext={patchPrep} />
        </div>
      </details>
    </section>
  );
}
