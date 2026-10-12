// Candidate-facing provenance model (Pilot 2 P2-04). Four bounded kinds, no free-form labels:
//   ai                 Mo's wording is AI-generated (always true of an assistant answer).
//   external_source    career/market evidence retrieved from the knowledge system (run.sources).
//   candidate_evidence the candidate's OWN approved evidence was selected for this preparation.
//   candidate_reviewed the candidate accepted or corrected an extracted claim. This is NOT independent verification.
// "Verified" is deliberately not used: nothing in this product is verified by a third party.

import type { AgentRunResponse } from "@/lib/api/types";

export type ProvenanceKind = "ai" | "external_source" | "candidate_evidence" | "candidate_reviewed";

export const FIND_CANDIDATE_EVIDENCE_TOOL = "FindCandidateEvidence";

/** External sources are shown only when the run actually returned sources; the absence of sources never becomes a source claim. */
export function externalSourcesUsed(run: Pick<AgentRunResponse, "sources"> | null | undefined): number {
  return run?.sources?.length ?? 0;
}

/**
 * True ONLY when the deterministic Candidate Evidence specialist ran and returned a NON-EMPTY selection: the server emits a
 * `tool_completed` event for the FindCandidateEvidence tool with status "ok" and source_count = number of selected items.
 * It is NOT derived from retrieval_used or journey.understand.evidence_used (those mean career/external retrieval), from the mere
 * presence of a CV, or from configuration.
 */
export function candidateEvidenceSelected(run: Pick<AgentRunResponse, "events"> | null | undefined): boolean {
  return (run?.events ?? []).some(
    (e) => e.event_type === "tool_completed" && e.tool_name === FIND_CANDIDATE_EVIDENCE_TOOL && e.status === "ok" && (e.source_count ?? 0) > 0,
  );
}
