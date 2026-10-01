/**
 * Guided-tour definition — Tutorial v2 (P10B-W9.5).
 *
 * Reflects the product journey that ACTUALLY exists now: Opportunity -> context/evidence -> Prepare ->
 * Practice -> improve. It leads with the candidate mental model (not agents/RAG/model internals).
 * Every step either targets a `data-tour` anchor that reliably exists on its route, or is intentionally
 * route-only (no highlight) — there are ZERO permanently-dead targets (v1 had 4: practice-handoff,
 * practice-answer, deep-dive, report). Titles/bodies are i18n keys (localized across all 7 locales);
 * a step never requires fabricated candidate/product state to render.
 */

/** Bump when the tour changes materially so a completed user can be re-invited (account-scoped). */
export const ASK4MO_TUTORIAL_VERSION = 2;

export interface TutorialStep {
  id: string;
  route: string;
  /** data-tour value to highlight. Omitted => route-only card (no highlight, never a dead target). */
  target?: string;
  /** i18n keys (tutorial namespace). */
  titleKey: string;
  bodyKey: string;
  /** Help Center anchor for "Learn more" (reuses existing articles; no duplicate copy). */
  helpHref?: string;
}

// Targets verified to exist on their route (data-tour anchors): home-start, opportunity-entry (W9.4),
// target-role, ask-mo (/prepare), progress (/progress), history (/history), help (/help). The
// Documents and Practice steps are route-only on purpose (no stable anchor; never fabricate state).
export const TUTORIAL_STEPS: TutorialStep[] = [
  {
    id: "welcome", route: "/app", // route-only welcome
    titleKey: "tutorial.s1Title", bodyKey: "tutorial.s1Body", helpHref: "/help#getting-started",
  },
  {
    id: "opportunities", route: "/app", target: "opportunity-entry",
    titleKey: "tutorial.s2Title", bodyKey: "tutorial.s2Body", helpHref: "/help#getting-started",
  },
  {
    id: "role-jd", route: "/prepare", target: "target-role",
    titleKey: "tutorial.s3Title", bodyKey: "tutorial.s3Body", helpHref: "/help#prepare",
  },
  {
    id: "evidence", route: "/documents", // route-only (no stable anchor; never fabricate a CV)
    titleKey: "tutorial.s4Title", bodyKey: "tutorial.s4Body", helpHref: "/help#documents",
  },
  {
    id: "prepare", route: "/prepare", target: "ask-mo",
    titleKey: "tutorial.s5Title", bodyKey: "tutorial.s5Body", helpHref: "/help#prepare",
  },
  {
    id: "practice", route: "/practice", // route-only (no completed-interview state required)
    titleKey: "tutorial.s6Title", bodyKey: "tutorial.s6Body", helpHref: "/help#practice",
  },
  {
    id: "progress", route: "/progress", target: "progress",
    titleKey: "tutorial.s7Title", bodyKey: "tutorial.s7Body", helpHref: "/help#progress",
  },
  {
    id: "history", route: "/history", target: "history",
    titleKey: "tutorial.s8Title", bodyKey: "tutorial.s8Body", helpHref: "/help#history",
  },
  {
    id: "help", route: "/help", target: "help",
    titleKey: "tutorial.s9Title", bodyKey: "tutorial.s9Body", helpHref: "/help",
  },
];
