// Ask4Mo seven-stage preparation journey (v4). One definition shared by the Getting Started workflow map and
// the in-app journey rail, so labels, order and destinations never drift. Routes are existing routes only.

export const JOURNEY_STAGES = ["opportunity", "context", "evidence", "prepare", "practice", "feedback", "progress"] as const;
export type JourneyStage = (typeof JOURNEY_STAGES)[number];

/** i18n key of a stage label in the in-app rail. */
export const STAGE_LABEL_KEY: Record<JourneyStage, string> = {
  opportunity: "journeyCues.stageOpportunity",
  context: "journeyCues.stageContext",
  evidence: "journeyCues.stageEvidence",
  prepare: "journeyCues.stagePrepare",
  practice: "journeyCues.stagePractice",
  feedback: "journeyCues.stageFeedback",
  progress: "journeyCues.stageProgress",
};

/** Existing destination for a stage, optionally scoped to an Opportunity id. */
export function stageHref(stage: JourneyStage, opportunityId?: number | null): string {
  const q = opportunityId ? `?opportunity=${opportunityId}` : "";
  switch (stage) {
    case "opportunity": return opportunityId ? `/opportunities/${opportunityId}` : "/opportunities";
    case "context": return `/company${q}`;
    case "evidence": return "/documents";
    case "prepare": return `/prepare${q}`;
    case "practice": return `/practice${q}`;
    case "feedback": return "/history";
    case "progress": return "/progress";
  }
}
