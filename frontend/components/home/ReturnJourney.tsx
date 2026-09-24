"use client";

/**
 * Authenticated return journey (Capstone P2/E2).
 *
 * A focused "welcome back" card built ENTIRELY from real persisted data — an active
 * (resumable) Practice, recent History, Progress and saved Memory. It renders nothing
 * when the account has no activity (first-use), preserving the existing onboarding.
 * It never fabricates activity, and it surfaces continuation actions rather than a
 * generic metrics dashboard. All data is owner-scoped by the server.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import type { ActiveSessionSummary } from "@/lib/api/types";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { Card, CardBody } from "@/components/ui/Card";
import { ButtonLink } from "@/components/ui/Button";

interface ReturnState {
  active: ActiveSessionSummary | null;
  completedCount: number;
  answersEvaluated: number;
  memoryCount: number;
}

export function ReturnJourney() {
  const status = useAuthOptional()?.status ?? "unauthenticated";
  const [state, setState] = useState<ReturnState | null>(null);

  useEffect(() => {
    // Only fetch for a resolved identity (dev anonymous or a real session). Skip on a
    // logged-out/unknown home so the public landing makes no owner-scoped calls.
    if (status !== "authenticated") {
      setState(null);
      return;
    }
    let cancelled = false;
    (async () => {
      const [activeRes, historyRes, progressRes, memoryRes] = await Promise.allSettled([
        api.interviews.listActive(),
        api.history.list(),
        api.progress.get(),
        api.memory.list(),
      ]);
      if (cancelled) return;
      const sessions =
        activeRes.status === "fulfilled" ? activeRes.value.sessions ?? [] : [];
      const completedCount =
        historyRes.status === "fulfilled" ? (historyRes.value.interviews ?? []).length : 0;
      const answersEvaluated =
        progressRes.status === "fulfilled" ? progressRes.value.answers_evaluated ?? 0 : 0;
      const memoryCount =
        memoryRes.status === "fulfilled" ? (memoryRes.value.memories ?? []).length : 0;
      setState({
        active: sessions[0] ?? null,
        completedCount,
        answersEvaluated,
        memoryCount,
      });
    })();
    return () => {
      cancelled = true;
    };
  }, [status]);

  if (!state) return null;

  const hasActivity =
    state.active !== null ||
    state.completedCount > 0 ||
    state.answersEvaluated > 0 ||
    state.memoryCount > 0;

  // First-use (no real activity): render nothing so onboarding/marketing is unchanged.
  if (!hasActivity) return null;

  return (
    <Card className="mb-6">
      <CardBody className="space-y-4">
        <h2 className="text-lg font-bold text-foreground">Welcome back</h2>

        {state.active ? (
          <div className="space-y-2">
            <p className="text-sm text-foreground">
              Continue your{" "}
              <span className="font-semibold">
                {state.active.target_role || "interview"}
              </span>{" "}
              practice
              {state.active.questions_planned
                ? ` — ${Math.min(
                    state.active.question_number,
                    state.active.questions_planned,
                  )} of ${state.active.questions_planned} questions`
                : ""}
              .
            </p>
            <ButtonLink href={`/practice?session=${encodeURIComponent(state.active.session_id)}`}>
              Continue practice
            </ButtonLink>
          </div>
        ) : (
          <p className="text-sm text-muted">Pick up where you left off, or prepare for a new role.</p>
        )}

        <div className="flex flex-wrap gap-2 pt-1 text-sm">
          {state.completedCount > 0 ? (
            <Link href="/history" className="rounded border border-border px-3 py-1.5 font-medium text-foreground hover:bg-surface-2">
              History ({state.completedCount})
            </Link>
          ) : null}
          {state.answersEvaluated > 0 ? (
            <Link href="/progress" className="rounded border border-border px-3 py-1.5 font-medium text-foreground hover:bg-surface-2">
              Progress
            </Link>
          ) : null}
          {state.memoryCount > 0 ? (
            <Link href="/settings" className="rounded border border-border px-3 py-1.5 font-medium text-foreground hover:bg-surface-2">
              Saved memory ({state.memoryCount})
            </Link>
          ) : null}
          <Link href="/prepare" className="rounded border border-border px-3 py-1.5 font-medium text-foreground hover:bg-surface-2">
            Prepare for another role
          </Link>
        </div>
      </CardBody>
    </Card>
  );
}
