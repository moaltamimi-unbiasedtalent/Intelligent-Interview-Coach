/**
 * Tutorial state — a NON-SENSITIVE UI preference only. It stores the tour version and
 * whether the user completed/dismissed it. It NEVER stores candidate data (CV, JD,
 * answers, roles, reports, memory, provider data or secrets). Guarded so private windows
 * or blocked storage never throw.
 */

import { ASK4MO_TUTORIAL_VERSION } from "./steps";

const KEY = "ask4mo.tutorial";

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

export function readTutorialState(): TutorialState {
  try {
    const raw = window.localStorage.getItem(KEY);
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

export function writeTutorialState(patch: Partial<TutorialState>): void {
  try {
    const next = { ...readTutorialState(), ...patch, version: ASK4MO_TUTORIAL_VERSION };
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable — the tour still works this session, just not remembered */
  }
}

/** First-visit eligibility: not completed and not dismissed for the CURRENT version. */
export function shouldInvite(): boolean {
  const s = readTutorialState();
  if (s.version !== ASK4MO_TUTORIAL_VERSION) return true; // a newer tour re-invites once
  return !s.completed && !s.dismissed;
}
