"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { MemoryCategory, MemoryResponse } from "@/lib/api/types";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";

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

/** Preparation memory the coach remembers (from /memory). User-owned, deletable. */
export function ProgressClient() {
  const [items, setItems] = useState<MemoryResponse[] | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<{ message: string; requestId?: string | null } | null>(null);
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback((signal?: AbortSignal) => {
    setStatus("loading");
    api.memory
      .list(undefined, { signal })
      .then((r) => {
        setItems(r.memories);
        setStatus("ready");
      })
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        const err = e as ApiError;
        setError({ message: err.userMessage ?? "Couldn't load your preparation memory.", requestId: err.requestId });
        setStatus("error");
      });
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  const remove = useCallback(async (id: number) => {
    setBusyId(id);
    try {
      await api.memory.remove(id);
      setItems((prev) => (prev ? prev.filter((m) => m.id !== id) : prev));
      setConfirmingId(null);
    } catch (e) {
      const err = e as ApiError;
      setError({ message: err.userMessage ?? "Couldn't remove that memory.", requestId: err.requestId });
    } finally {
      setBusyId(null);
    }
  }, []);

  return (
    <section>
      <PageHeader
        eyebrow="Your journey"
        title="Progress"
        description="What your coach remembers — preparation priorities, strengths and preferences you've chosen to save."
      />

      {status === "loading" ? <LoadingState label="Loading your preparation memory" /> : null}
      {status === "error" && error ? <ErrorState message={error.message} requestId={error.requestId} /> : null}

      {status === "ready" && items ? (
        items.length === 0 ? (
          <EmptyState
            title="Nothing saved yet."
            description="When you choose to save preparation priorities, they'll appear here. Your coach never saves anything without you asking."
          />
        ) : (
          <div className="grid gap-6">
            {GROUPS.map((group) => {
              const groupItems = items.filter((m) => group.categories.includes(m.category));
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
    </section>
  );
}
