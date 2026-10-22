/**
 * Story Bank vocabulary (04A): the closed sets the server returns, mapped to i18n keys and a badge tone.
 * One place, so the list, the picker and the editor can never label the same state differently.
 */

import type { StoryVerification } from "@/lib/api/types";

export const VERIFICATIONS: StoryVerification[] = [
  "evidence_verified", "answer_linked", "self_confirmed", "unverified", "source_revoked",
];

// The three document-evidence states reuse the P2-04 vocabulary (documents.ev*): "supporting evidence", never "verified by" anyone.
export const VERIFICATION_KEY: Record<StoryVerification, string> = {
  evidence_verified: "documents.evVerified",
  source_revoked: "documents.evRevoked",
  answer_linked: "storyBank.v_answer_linked",
  self_confirmed: "storyBank.v_self_confirmed",
  unverified: "documents.evNone",
};

/** Filter-menu wording (a list of kinds, distinct from the per-story badge text above). */
export const VERIFICATION_FILTER_KEY: Record<StoryVerification, string> = {
  evidence_verified: "storyBank.f_evidence_verified",
  source_revoked: "storyBank.f_source_revoked",
  answer_linked: "storyBank.f_answer_linked",
  self_confirmed: "storyBank.f_self_confirmed",
  unverified: "storyBank.f_unverified",
};

export const VERIFICATION_HELP_KEY: Record<StoryVerification, string> = {
  evidence_verified: "storyBank.vh_evidence_verified",
  source_revoked: "storyBank.vh_source_revoked",
  answer_linked: "storyBank.vh_answer_linked",
  self_confirmed: "storyBank.vh_self_confirmed",
  unverified: "storyBank.vh_unverified",
};

/** A story is "verified" in the strong sense ONLY with live document evidence; everything else is shown in a neutral or warning tone. */
export const VERIFICATION_TONE: Record<StoryVerification, "low" | "medium" | "neutral" | "high"> = {
  evidence_verified: "low",
  answer_linked: "medium",
  self_confirmed: "medium",
  unverified: "neutral",
  source_revoked: "high",
};

export const STATUS_KEY: Record<string, string> = {
  source_backed: "documents.stSourceBacked",
  user_created: "documents.stUserCreated",
  user_corrected: "documents.stUserCorrected",
  model_suggested: "documents.stModelSuggested",
};

export const QUALITY_KEY: Record<string, string> = {
  situation_missing: "storyBank.q_situation_missing",
  task_missing: "storyBank.q_task_missing",
  action_missing: "storyBank.q_action_missing",
  result_missing: "storyBank.q_result_missing",
  action_thin: "storyBank.q_action_thin",
  result_no_figure: "storyBank.q_result_no_figure",
  no_tags: "storyBank.q_no_tags",
};

export const MAX_PRACTICE_STORIES = 5;

/** The server sends `verification`; an older payload carrying only `evidence_state` still renders truthfully (verified/source_revoked/none). */
export function verificationOf(s: { verification?: StoryVerification; evidence_state?: string }): StoryVerification {
  if (s.verification) return s.verification;
  if (s.evidence_state === "verified") return "evidence_verified";
  if (s.evidence_state === "source_revoked") return "source_revoked";
  return "unverified";
}
