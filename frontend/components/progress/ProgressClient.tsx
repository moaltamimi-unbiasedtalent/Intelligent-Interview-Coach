"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError, stateKeyForError } from "@/lib/api/errors";
import type { MemoryCategory, MemoryResponse, ProgressResponse } from "@/lib/api/types";
import { useT } from "@/components/i18n/I18nProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { EmptyState, EmptyStateIllustration, ErrorState, LoadingState } from "@/components/ui/States";
import { PracticeProgress } from "@/components/progress/PracticeProgress";

/** Candidate-friendly labels — technical categories are never shown raw. */
const CATEGORY_LABEL: Record<MemoryCategory, string> = {
  target_role: "Target role",
  recurring_gap: "Priority",
  strength: "Strength",
  completed_topic: "Completed",
  interview_preference: "Preference",
  preparation_goal: "Goal",
};

const GROUPS: Array<{ label: string; hint: string; categories: MemoryCategory[] }> = [
  { label: "Priorities", hint: "Areas you've chosen to work on.", categories: ["recurring_gap", "preparation_goal"] },
  { label: "Strengths", hint: "What you're doing well.", categories: ["strength"] },
  { label: "Completed preparation", hint: "Topics you've already practised.", categories: ["completed_topic"] },
  { label: "Preferences", hint: "Roles and interview styles you prefer.", categories: ["interview_preference", "target_role"] },
];

// P10B-W9.2: one small explicit read-resource shape shared by the two independent Progress regions
// (practice + memory). The parent owns BOTH lifecycles so it can render coherent degraded states.
type Resource<T> = {
  status: "loading" | "ready" | "error";
  data: T | null;
  error: ApiError | null;
  retrying: boolean;
};

const INITIAL: Resource<never> = { status: "loading", data: null, error: null, retrying: false };

/**
 * Progress = two logically independent read resources: Practice Progress (/progress) and
 * Preparation Memory (/memory). Either can fail or recover without destroying the other; when BOTH
 * fail we show ONE coherent page-level recoverable error (never the Pilot's duplicate catastrophic
 * pattern). Retry re-runs only the failed GET(s). Errors use the W9.1 truthful taxonomy.
 */
export function ProgressClient() {
  const t = useT();
  const [practice, setPractice] = useState<Resource<ProgressResponse>>(INITIAL);
  const [memory, setMemory] = useState<Resource<MemoryResponse[]>>(INITIAL);
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);

  // One controller per region, so a new load aborts the previous in-flight one (latest wins;
  // a stale response can never overwrite a newer success).
  const practiceCtrl = useRef<AbortController | null>(null);
  const memoryCtrl = useRef<AbortController | null>(null);

  const loadPractice = useCallback((isRetry = false) => {
    practiceCtrl.current?.abort();
    const ctrl = new AbortController();
    practiceCtrl.current = ctrl;
    setPractice((s) => (isRetry ? { ...s, retrying: true } : { ...INITIAL }));
    api.progress
      .get({ signal: ctrl.signal })
      .then((d) => {
        if (ctrl.signal.aborted) return;
        setPractice({ status: "ready", data: d, error: null, retrying: false });
      })
      .catch((e) => {
        if (ctrl.signal.aborted || (e instanceof DOMException && e.name === "AbortError")) return;
        setPractice({ status: "error", data: null, error: e as ApiError, retrying: false });
      });
  }, []);

  const loadMemory = useCallback((isRetry = false) => {
    memoryCtrl.current?.abort();
    const ctrl = new AbortController();
    memoryCtrl.current = ctrl;
    setMemory((s) => (isRetry ? { ...s, retrying: true } : { ...INITIAL }));
    api.memory
      .list(undefined, { signal: ctrl.signal })
      .then((r) => {
        if (ctrl.signal.aborted) return;
        setMemory({ status: "ready", data: r.memories, error: null, retrying: false });
      })
      .catch((e) => {
        if (ctrl.signal.aborted || (e instanceof DOMException && e.name === "AbortError")) return;
        setMemory({ status: "error", data: null, error: e as ApiError, retrying: false });
      });
  }, []);

  useEffect(() => {
    loadPractice();
    loadMemory();
    return () => {
      practiceCtrl.current?.abort();
      memoryCtrl.current?.abort();
    };
  }, [loadPractice, loadMemory]);

  const remove = useCallback(async (id: number) => {
    setBusyId(id);
    setRemoveError(null);
    try {
      await api.memory.remove(id);
      setMemory((s) => ({ ...s, data: s.data ? s.data.filter((m) => m.id !== id) : s.data }));
      setConfirmingId(null);
    } catch (e) {
      // A failed delete must NOT blank the list into an error region — surface a small, dismissible
      // note and leave the item in place (writes are never auto-retried).
      const err = e as ApiError;
      setRemoveError(t(stateKeyForError(err.kind)));
    } finally {
      setBusyId(null);
    }
  }, [t]);

  const errMessage = (r: Resource<unknown>) => (r.error ? t(stateKeyForError(r.error.kind)) : "");
  const bothError = practice.status === "error" && memory.status === "error";

  return (
    <section data-tour="progress">
      <PageHeader
        eyebrow="Your journey"
        title="Progress"
        description="Your practice progress, and what your coach remembers — the priorities, strengths and preferences you've chosen to save."
      />

      {bothError ? (
        // CASE 4: both regions failed -> ONE coherent page-level recoverable error (never two
        // competing catastrophic messages). One Retry safely reloads both GET resources.
        <ErrorState
          message={errMessage(practice)}
          requestId={practice.error?.requestId ?? memory.error?.requestId}
          retrying={practice.retrying || memory.retrying}
          onRetry={() => {
            loadPractice(true);
            loadMemory(true);
          }}
        />
      ) : (
        <>
          {/* Practice region: quiet while loading/empty; a compact section error (with Retry) on
              failure; tiles when ready. A practice failure never hides the memory region below. */}
          {practice.status === "error" ? (
            <div className="mb-8">
              <h2 className="text-sm font-semibold text-foreground">Practice progress</h2>
              <p className="mb-3 text-xs text-muted">From your completed practice interviews.</p>
              <ErrorState
                variant="section"
                message={errMessage(practice)}
                requestId={practice.error?.requestId}
                retrying={practice.retrying}
                onRetry={() => loadPractice(true)}
              />
            </div>
          ) : (
            <PracticeProgress data={practice.status === "ready" ? practice.data : null} />
          )}

          <p className="-mt-2 mb-4 text-sm" data-tour="memory">
            <a href="/settings" className="font-medium text-accent underline">
              Manage in Settings
            </a>{" "}
            <span className="text-muted">— edit, pin or remove your saved preparation memory.</span>
            {"  "}
            <a href="/help#progress" className="font-medium text-accent underline">How Progress works</a>
          </p>

          {removeError ? (
            <p className="mb-4 text-sm text-danger" role="alert">{removeError}</p>
          ) : null}

          {/* Memory region: loading -> skeleton; error -> section error (with Retry); ready ->
              empty state or grouped list. */}
          {memory.status === "loading" ? (
            <LoadingState label="Loading your preparation memory" />
          ) : null}
          {memory.status === "error" ? (
            <ErrorState
              variant="section"
              message={errMessage(memory)}
              requestId={memory.error?.requestId}
              retrying={memory.retrying}
              onRetry={() => loadMemory(true)}
            />
          ) : null}

          {memory.status === "ready" && memory.data ? (
            memory.data.length === 0 ? (
              <EmptyState
                title="Nothing saved yet."
                description="When you choose to save preparation priorities, they'll appear here. Your coach never saves anything without you asking."
                illustration={
                  <EmptyStateIllustration
                    src="/images/ask4mo/ask4mo-empty-progress-ink.png"
                    alt="Hand-painted stepping stones leading from a pencil toward a focused goal."
                  />
                }
                action={<ButtonLink href="/prepare">Prepare with Mo</ButtonLink>}
              />
            ) : (
              <div className="grid gap-6">
                {GROUPS.map((group) => {
                  const groupItems = memory.data!.filter((m) => group.categories.includes(m.category));
                  if (groupItems.length === 0) return null;
                  return (
                    <div key={group.label}>
                      <h2 className="text-sm font-semibold text-foreground">{group.label}</h2>
                      <p className="mb-2 text-xs text-muted">{group.hint}</p>
                      <div className="grid gap-3">
                        {groupItems.map((m) => (
                          <Card key={m.id}>
                            <CardBody className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <p className="font-medium break-words">{m.summary}</p>
                                <div className="mt-1 flex flex-wrap items-center gap-2">
                                  <Badge>{CATEGORY_LABEL[m.category]}</Badge>
                                  {m.target_role ? <Badge tone="neutral">{m.target_role}</Badge> : null}
                                  {m.pinned ? <Badge tone="low">📌 Pinned</Badge> : null}
                                </div>
                              </div>
                              <div className="shrink-0">
                                {confirmingId === m.id ? (
                                  <div
                                    className="flex items-center gap-2"
                                    role="group"
                                    aria-label={`Remove “${m.summary}”?`}
                                  >
                                    <span className="text-xs text-muted">Remove this?</span>
                                    <Button size="sm" variant="ghost" onClick={() => setConfirmingId(null)}>
                                      Cancel
                                    </Button>
                                    <Button
                                      size="sm"
                                      onClick={() => remove(m.id)}
                                      disabled={busyId === m.id}
                                    >
                                      Remove
                                    </Button>
                                  </div>
                                ) : (
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => setConfirmingId(m.id)}
                                    aria-label={`Remove saved memory: ${m.summary}`}
                                  >
                                    Remove
                                  </Button>
                                )}
                              </div>
                            </CardBody>
                          </Card>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            )
          ) : null}
        </>
      )}
    </section>
  );
}
