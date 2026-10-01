"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { TUTORIAL_STEPS } from "@/lib/tutorial/steps";
import {
  forgetLegacyTutorialState,
  shouldInvite,
  writeTutorialState,
} from "@/lib/tutorial/storage";
import { APP_HOME } from "@/lib/auth/routes";
import { useT } from "@/components/i18n/I18nProvider";
import { useAuthOptional } from "@/components/auth/AuthProvider";

/** Custom event any "Take the tour" control can dispatch to start the tour. */
export const START_TOUR_EVENT = "ask4mo:start-tour";
/** One-time sessionStorage flag set by the Welcome screen to auto-start the tour on /app. */
export const TUTORIAL_AUTOSTART_KEY = "ask4mo.tutorial.autostart";

type Mode = "idle" | "invitation" | "tour";
const HIGHLIGHT = "ask4mo-tour-highlight";

/**
 * Guided product tour + first-visit invitation (Tutorial v2, P10B-W9.5). A NON-blocking coach card
 * (no click-capturing backdrop) so it never blocks HITL approval, Practice controls or dialogs.
 * Route-aware: each step navigates to its route and highlights a stable `data-tour` target when
 * present, else shows a route-level explanation. State is an ACCOUNT-SCOPED UI preference (keyed by
 * the signed-in account id), so a shared browser never leaks one account's completion to another. All
 * chrome + steps are localized.
 */
export function TutorialController() {
  const [mode, setMode] = useState<Mode>("idle");
  const [index, setIndex] = useState(0);
  const router = useRouter();
  const pathname = usePathname();
  const t = useT();
  const auth = useAuthOptional();
  // Account scope for state (opaque id only; "anon" before an identity resolves).
  const scope = auth?.account?.user_id != null ? String(auth.account.user_id) : "anon";
  const authStatus = auth?.status;
  const cardRef = useRef<HTMLDivElement>(null);

  const total = TUTORIAL_STEPS.length;
  const step = TUTORIAL_STEPS[index];

  const start = useCallback(() => {
    setIndex(0);
    setMode("tour");
  }, []);

  // One-time cleanup of the legacy v1 global key (never used for account-scoped state).
  useEffect(() => {
    forgetLegacyTutorialState();
  }, []);

  // External "start tour" trigger (Help replay). Always starts intentionally from step 1.
  useEffect(() => {
    const onStart = () => start();
    window.addEventListener(START_TOUR_EVENT, onStart);
    return () => window.removeEventListener(START_TOUR_EVENT, onStart);
  }, [start]);

  // On /app while idle: a one-time Welcome auto-start takes precedence; otherwise a first-visit
  // (account-scoped) invitation. Never auto-opens elsewhere, and never after completed/dismissed.
  useEffect(() => {
    if (mode !== "idle" || pathname !== APP_HOME) return;
    // Wait until identity resolves so the invitation uses the correct ACCOUNT scope (never invite or
    // write under a transient "anon" scope, which would mis-key shared-browser state).
    if (authStatus == null || authStatus === "loading") return;
    try {
      if (window.sessionStorage.getItem(TUTORIAL_AUTOSTART_KEY)) {
        window.sessionStorage.removeItem(TUTORIAL_AUTOSTART_KEY);
        start();
        return;
      }
    } catch {
      /* sessionStorage blocked — fall through to the normal invitation */
    }
    if (shouldInvite(scope)) setMode("invitation");
  }, [pathname, mode, scope, authStatus, start]);

  // Route-aware: navigate to the current step's route if we're not there yet.
  useEffect(() => {
    if (mode !== "tour" || !step) return;
    if (pathname !== step.route) router.push(step.route);
  }, [mode, step, pathname, router]);

  // Highlight the step target when present on the current route (graceful if absent/route-only).
  useEffect(() => {
    if (mode !== "tour" || !step || pathname !== step.route) return;
    writeTutorialState(scope, { lastStep: index });
    let el: HTMLElement | null = null;
    const timer = window.setTimeout(() => {
      if (!step.target) return;
      el = document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
      if (el) {
        const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
        el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
        el.classList.add(HIGHLIGHT);
      }
    }, 120); // allow the destination route to render
    return () => {
      window.clearTimeout(timer);
      if (el) el.classList.remove(HIGHLIGHT);
    };
  }, [mode, step, index, pathname, scope]);

  // Focus the card when a step or the invitation opens (accessibility).
  useEffect(() => {
    if (mode !== "idle") cardRef.current?.focus();
  }, [mode, index]);

  const finish = useCallback(() => {
    writeTutorialState(scope, { completed: true, lastStep: total - 1 });
    setMode("idle");
  }, [total, scope]);

  const dismiss = useCallback(() => {
    writeTutorialState(scope, { dismissed: true, lastStep: index });
    setMode("idle");
  }, [index, scope]);

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
        aria-label={t("tutorial.invitationTitle")}
        className="fixed bottom-4 right-4 z-40 w-[min(92vw,22rem)] rounded-lg border border-border bg-surface p-4 shadow-soft outline-none"
      >
        <h2 className="text-base font-semibold">{t("tutorial.invitationTitle")}</h2>
        <p className="mt-1 text-sm text-muted">{t("tutorial.invitationBody")}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={start}
            className="min-h-[36px] rounded bg-accent px-3 text-sm font-semibold text-accent-foreground"
          >
            {t("tutorial.start")}
          </button>
          <button
            type="button"
            onClick={dismiss}
            className="min-h-[36px] rounded border border-border px-3 text-sm font-semibold"
          >
            {t("tutorial.later")}
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
      aria-label={t(step.titleKey)}
      className="fixed inset-x-0 bottom-0 z-40 mx-auto w-full max-w-content p-3 sm:inset-x-auto sm:bottom-4 sm:right-4 sm:w-[min(92vw,24rem)] sm:p-0"
    >
      <div className="rounded-lg border border-border bg-surface p-4 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-base font-semibold">{t(step.titleKey)}</h2>
          <button
            type="button"
            onClick={dismiss}
            aria-label={t("tutorial.close")}
            className="shrink-0 rounded p-1 text-muted hover:text-foreground"
          >
            ✕
          </button>
        </div>
        <p className="mt-1 text-sm text-muted">{t(step.bodyKey)}</p>
        {step.helpHref ? (
          <p className="mt-2 text-sm">
            <Link href={step.helpHref} className="font-medium text-accent underline">
              {t("tutorial.learnMore")}
            </Link>
          </p>
        ) : null}
        <div className="mt-3 flex items-center justify-between gap-2">
          <span className="text-xs text-muted" aria-live="polite">
            {t("tutorial.stepOf", { n: index + 1, total })}
          </span>
          <div className="flex gap-2">
            <button type="button" onClick={dismiss} className="min-h-[36px] rounded px-2 text-sm text-muted">
              {t("tutorial.skip")}
            </button>
            <button
              type="button"
              onClick={back}
              disabled={index === 0}
              className="min-h-[36px] rounded border border-border px-3 text-sm font-semibold disabled:opacity-50"
            >
              {t("tutorial.back")}
            </button>
            <button
              type="button"
              onClick={next}
              className="min-h-[36px] rounded bg-accent px-3 text-sm font-semibold text-accent-foreground"
            >
              {index >= total - 1 ? t("tutorial.finish") : t("tutorial.next")}
            </button>
          </div>
        </div>
        {index >= total - 1 ? (
          <p className="mt-2 text-sm">
            <Link href="/help" onClick={finish} className="font-medium text-accent underline">
              {t("tutorial.openHelp")}
            </Link>
          </p>
        ) : null}
      </div>
    </div>
  );
}
