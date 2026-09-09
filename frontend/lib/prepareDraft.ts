/**
 * Ephemeral Home → Prepare handoff (§3–§4, §18).
 *
 * A tiny, short-lived draft that carries the candidate's intent from the Home entry
 * field into /prepare so they never re-type it. It is browser-local and transient:
 * `sessionStorage` (same tab/session), with an in-memory fallback for privacy modes
 * where storage throws (§19). It is NEVER put in the URL, `localStorage`, long-term
 * memory, logs or observability, and it carries no ids/keys/checkpoints — only the
 * transient input needed for the immediate page transition.
 */

const KEY = "intelligent-interview-coach.prepare-draft.v1";

export type PrepareDraftAction = "start" | "job_description" | "candidate_background";

export interface PrepareDraft {
  source: "home";
  action: PrepareDraftAction;
  /** The candidate's typed preparation goal (only for action "start"). */
  goal?: string;
}

// Same-tab fallback for environments where sessionStorage is unavailable/throws.
// This is module state, so it survives client-side navigation within the SPA.
let memoryDraft: PrepareDraft | null = null;

function isDraft(value: unknown): value is PrepareDraft {
  if (!value || typeof value !== "object") return false;
  const d = value as Record<string, unknown>;
  if (d.source !== "home") return false;
  if (d.action !== "start" && d.action !== "job_description" && d.action !== "candidate_background") {
    return false;
  }
  if (d.goal !== undefined && typeof d.goal !== "string") return false;
  return true;
}

/** Persist the transient draft. Never throws; returns false if storage was unavailable
 *  (the in-memory fallback is still set so the same-tab handoff works). */
export function writePrepareDraft(draft: PrepareDraft): boolean {
  memoryDraft = draft;
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(draft));
    return true;
  } catch {
    return false; // private mode / storage blocked — the in-memory fallback covers it
  }
}

/** Read the transient draft (sessionStorage first, then the in-memory fallback). */
export function readPrepareDraft(): PrepareDraft | null {
  try {
    const raw = window.sessionStorage.getItem(KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (isDraft(parsed)) return parsed;
    }
  } catch {
    /* storage unavailable — fall through to the in-memory fallback */
  }
  return memoryDraft;
}

/** Remove the transient draft from both stores. Never throws. */
export function clearPrepareDraft(): void {
  memoryDraft = null;
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    /* nothing to clear / storage unavailable */
  }
}
