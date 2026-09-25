"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { TUTORIAL_STEPS } from "@/lib/tutorial/steps";
import { readTutorialState, shouldInvite, writeTutorialState } from "@/lib/tutorial/storage";
import { APP_HOME } from "@/lib/auth/routes";

/** Custom event any "Take the tour" control can dispatch to start the tour. */
export const START_TOUR_EVENT = "ask4mo:start-tour";

type Mode = "idle" | "invitation" | "tour";
const HIGHLIGHT = "ask4mo-tour-highlight";

/**
 * Guided product tour + first-visit invitation. A NON-blocking coach card (no
 * click-capturing backdrop) so it never blocks HITL approval, Practice answer controls
 * or dialogs. Route-aware: each step navigates to its route and highlights a stable
 * `data-tour` target when present, else shows a route-level explanation. State is a UI
 * preference only (see lib/tutorial/storage).
 */
export function TutorialController() {
  const [mode, setMode] = useState<Mode>("idle");
  const [index, setIndex] = useState(0);
  const router = useRouter();
  const pathname = usePathname();
  const cardRef = useRef<HTMLDivElement>(null);

  const total = TUTORIAL_STEPS.length;
  const step = TUTORIAL_STEPS[index];

  const start = useCallback(() => {
    setIndex(0);
    setMode("tour");
  }, []);

  // First-visit invitation (Home only, when eligible) + external "start tour" trigger.
  useEffect(() => {
    const onStart = () => start();
    window.addEventListener(START_TOUR_EVENT, onStart);
    return () => window.removeEventListener(START_TOUR_EVENT, onStart);
  }, [start]);

  useEffect(() => {
    if (mode === "idle" && pathname === APP_HOME && shouldInvite()) setMode("invitation");
    // Only auto-evaluate on mount / route change while idle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  // Route-aware: navigate to the current step's route if we're not there yet.
  useEffect(() => {
    if (mode !== "tour" || !step) return;
    if (pathname !== step.route) router.push(step.route);
  }, [mode, step, pathname, router]);

  // Highlight the step target when present on the current route (graceful if absent).
  useEffect(() => {
    if (mode !== "tour" || !step || pathname !== step.route) return;
    writeTutorialState({ lastStep: index });
    let el: HTMLElement | null = null;
    const t = window.setTimeout(() => {
      if (!step.target) return;
      el = document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
      if (el) {
        const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
        el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
        el.classList.add(HIGHLIGHT);
      }
    }, 120); // allow the destination route to render
    return () => {
      window.clearTimeout(t);
      if (el) el.classList.remove(HIGHLIGHT);
    };
  }, [mode, step, index, pathname]);

  // Focus the card when a step or the invitation opens (accessibility).
  useEffect(() => {
    if (mode !== "idle") cardRef.current?.focus();
  }, [mode, index]);

  const finish = useCallback(() => {
    writeTutorialState({ completed: true, lastStep: total - 1 });
    setMode("idle");
  }, [total]);

  const dismiss = useCallback(() => {
    writeTutorialState({ dismissed: true, lastStep: index });
    setMode("idle");
  }, [index]);

  const next = useCallback(() => {
    if (index >= total - 1) finish();
    else setIndex((i) => i + 1);
  }, [index, total, finish]);

  const back = useCallback(() => setIndex((i) => Math.max(0, i - 1)), []);

  useEffect(() => {
    if (mode === "idle") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") dismiss();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mode, dismiss]);

  if (mode === "idle") return null;

  if (mode === "invitation") {
    return (
      <div
        ref={cardRef}
        tabIndex={-1}
        role="dialog"
        aria-label="Welcome to Ask4Mo"
        className="fixed bottom-4 right-4 z-40 w-[min(92vw,22rem)] rounded-lg border border-border bg-surface p-4 shadow-soft outline-none"
      >
        <h2 className="text-base font-semibold">Welcome to Ask4Mo</h2>
        <p className="mt-1 text-sm text-muted">
          Learn how to prepare, practise and improve with your AI Coach. About 2 minutes.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={start}
            className="min-h-[36px] rounded bg-accent px-3 text-sm font-semibold text-accent-foreground"
          >
            Start tour
          </button>
          <button
            type="button"
            onClick={dismiss}
            className="min-h-[36px] rounded border border-border px-3 text-sm font-semibold"
          >
            Maybe later
          </button>
        </div>
      </div>
    );
  }

  // mode === "tour"
  return (
    <div
      ref={cardRef}
      tabIndex={-1}
      role="dialog"
      aria-label={`Guided tour: ${step.title}`}
      className="fixed inset-x-0 bottom-0 z-40 mx-auto w-full max-w-content p-3 sm:inset-x-auto sm:bottom-4 sm:right-4 sm:w-[min(92vw,24rem)] sm:p-0"
    >
      <div className="rounded-lg border border-border bg-surface p-4 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-base font-semibold">{step.title}</h2>
          <button
            type="button"
            onClick={dismiss}
            aria-label="Close tour"
            className="shrink-0 rounded p-1 text-muted hover:text-foreground"
          >
            ✕
          </button>
        </div>
        <p className="mt-1 text-sm text-muted">{step.body}</p>
        {step.helpHref ? (
          <p className="mt-2 text-sm">
            <Link href={step.helpHref} className="font-medium text-accent underline">
              Learn more
            </Link>
          </p>
        ) : null}
        <div className="mt-3 flex items-center justify-between gap-2">
          <span className="text-xs text-muted" aria-live="polite">
            {index + 1} of {total}
          </span>
          <div className="flex gap-2">
            <button type="button" onClick={dismiss} className="min-h-[36px] rounded px-2 text-sm text-muted">
              Skip
            </button>
            <button
              type="button"
              onClick={back}
              disabled={index === 0}
              className="min-h-[36px] rounded border border-border px-3 text-sm font-semibold disabled:opacity-50"
            >
              Back
            </button>
            <button
              type="button"
              onClick={next}
              className="min-h-[36px] rounded bg-accent px-3 text-sm font-semibold text-accent-foreground"
            >
              {index >= total - 1 ? "Finish" : "Next"}
            </button>
          </div>
        </div>
        {index >= total - 1 ? (
          <p className="mt-2 text-sm">
            <Link href="/help" onClick={finish} className="font-medium text-accent underline">
              Open Help Center
            </Link>
          </p>
        ) : null}
      </div>
    </div>
  );
}
