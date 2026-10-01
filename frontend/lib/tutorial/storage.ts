/**
 * Tutorial state — a NON-SENSITIVE UI preference only. It stores the tour version and whether the
 * user completed/dismissed it (plus the last step). It NEVER stores candidate data (CV, JD, answers,
 * roles, reports, memory, provider data or secrets). Guarded so private windows or blocked storage
 * never throw.
 *
 * P10B-W9.5: state is ACCOUNT-SCOPED. The key includes the account's own opaque `user_id`, so on a
 * shared browser Account A's completed/dismissed tour can NEVER suppress Account B's tour (the Pilot
 * shared-browser defect). The legacy global v1 key `ask4mo.tutorial` is deliberately NOT read as
 * authoritative for any authenticated account (see `readTutorialState`), so a device where v1 was
 * completed globally no longer hides v2 for a specific signed-in user. Durable cross-device state would
 * require a preferences migration, intentionally out of scope for W9.5 (see the W9.5 doc).
 */

import { ASK4MO_TUTORIAL_VERSION } from "./steps";

const LEGACY_KEY = "ask4mo.tutorial"; // v1 global key — intentionally ignored for account state.

/** Per-account key. `scope` is the opaque account id (or "anon" before an identity resolves). */
function keyFor(scope: string): string {
  return `ask4mo.tutorial:${scope || "anon"}`;
}

export interface TutorialState {
  version: number;
  completed: boolean;
  dismissed: boolean;
  lastStep: number;
}

const DEFAULT_STATE: TutorialState = {
  version: ASK4MO_TUTORIAL_VERSION,
  completed: false,
  dismissed: false,
  lastStep: 0,
};

export function readTutorialState(scope: string): TutorialState {
  try {
    const raw = window.localStorage.getItem(keyFor(scope));
    if (!raw) return { ...DEFAULT_STATE };
    const parsed = JSON.parse(raw) as Partial<TutorialState>;
    return {
      version: typeof parsed.version === "number" ? parsed.version : 0,
      completed: !!parsed.completed,
      dismissed: !!parsed.dismissed,
      lastStep: typeof parsed.lastStep === "number" ? parsed.lastStep : 0,
    };
  } catch {
    return { ...DEFAULT_STATE };
  }
}

export function writeTutorialState(scope: string, patch: Partial<TutorialState>): void {
  try {
    const next = { ...readTutorialState(scope), ...patch, version: ASK4MO_TUTORIAL_VERSION };
    window.localStorage.setItem(keyFor(scope), JSON.stringify(next));
  } catch {
    /* storage unavailable — the tour still works this session, just not remembered */
  }
}

/** First-visit eligibility for THIS account: not completed and not dismissed for the current version. */
export function shouldInvite(scope: string): boolean {
  const s = readTutorialState(scope);
  if (s.version !== ASK4MO_TUTORIAL_VERSION) return true; // a newer tour re-invites once
  return !s.completed && !s.dismissed;
}

/** One-time best-effort cleanup of the legacy global v1 key (never used for account state). */
export function forgetLegacyTutorialState(): void {
  try {
    window.localStorage.removeItem(LEGACY_KEY);
  } catch {
    /* ignore */
  }
}
