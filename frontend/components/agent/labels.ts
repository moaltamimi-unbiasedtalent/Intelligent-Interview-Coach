import type { AgentEvent } from "@/lib/api/types";

/** Candidate-friendly labels for the controlled Career tools (never raw names). */
export const TOOL_LABEL: Record<string, string> = {
  AnalyzeJobDescription: "Analysing the job description",
  AnalyzeCandidateGaps: "Comparing your experience",
  BuildPreparationPlan: "Building your preparation plan",
  GenerateInterviewQuestions: "Preparing interview questions",
  SearchCareerKnowledge: "Checking career evidence",
  ProposePreparationMemory: "Suggesting something to remember",
  RequestPracticeHandoff: "Getting ready for practice",
};

/** Friendly labels for preparation-memory categories (shared with Progress). */
export const MEMORY_CATEGORY_LABEL: Record<string, string> = {
  target_role: "Target role",
  recurring_gap: "Preparation priority",
  strength: "Strength",
  completed_topic: "Completed preparation",
  interview_preference: "Interview preference",
  preparation_goal: "Preparation goal",
};

export function toolLabel(name?: string | null): string {
  if (!name) return "Working";
  return TOOL_LABEL[name] ?? name;
}

export function memoryCategoryLabel(category?: string | null): string {
  if (!category) return "Note";
  return MEMORY_CATEGORY_LABEL[category] ?? category;
}

/**
 * A safe, human-readable activity line derived from observable events/tools — never
 * chain-of-thought. Returns the most recent meaningful activity, or a default.
 */
export function activityFromEvents(events: AgentEvent[]): string {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const e = events[i];
    if (e.event_type === "tool_started" || e.event_type === "tool_requested") {
      return `${toolLabel(e.tool_name)}…`;
    }
    if (e.event_type === "request_understood") return "Understanding your request…";
    if (e.event_type === "memory_loaded") return "Reviewing your saved preparation…";
  }
  return "Working on your preparation…";
}
