/**
 * TypeScript contracts mirrored from the FastAPI OpenAPI schema (/api/v1).
 *
 * Decision (§3): OpenAPI codegen remains DEFERRED — the consumed surface is still
 * modest and stable, and a Python contract test (tests/test_openapi_contract.py)
 * fails if the backend renames a field the frontend depends on, so drift is caught
 * without adding a codegen build step. These types contain only fields the backend
 * actually returns. No `any` for core payloads.
 */

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface CapabilitiesResponse {
  career_intelligence: boolean;
  interview_practice: boolean;
  knowledge_base: boolean;
  evaluation: boolean;
  live_interview_enabled: boolean;
  agentic_rag: boolean;
  agent_memory: boolean;
  human_in_the_loop: boolean;
  agent_coach_enabled: boolean;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  request_id?: string | null;
}

export interface ApiErrorEnvelope {
  error: ApiErrorBody;
}

// --- Career chat -------------------------------------------------------------

export interface CareerChatRequest {
  question: string;
  job_description?: string | null;
  candidate_background?: string | null;
  days_until_interview?: number | null;
  hours_per_week?: number | null;
}

export interface Citation {
  marker?: string | null;
  title?: string | null;
  source?: string | null;
  source_url?: string | null;
  page?: number | null;
}

export interface Source {
  title?: string | null;
  source_url?: string | null;
  evidence_type?: string | null;
  authority_level?: string | null;
  geography?: string | null;
  occupation_title?: string | null;
  reference_year?: number | null;
}

export interface ToolSummary {
  tool_name: string;
  status: string;
  summary?: string | null;
}

export interface CareerChatResponse {
  answer: string;
  citations: Citation[];
  sources: Source[];
  tools: ToolSummary[];
  input_flagged: boolean;
  has_evidence: boolean;
  preparation_available: boolean;
}

// --- Career tool results (domain dicts inside ToolResultResponse.result) ------

export interface RoleRequirements {
  role_title?: string | null;
  seniority?: string | null;
  key_responsibilities?: string[];
  required_skills?: string[];
  preferred_skills?: string[];
  technologies?: string[];
  leadership_expectations?: string[];
  stakeholder_expectations?: string[];
  likely_interview_themes?: string[];
  interpretation_notes?: string[];
}

export interface PriorityGap {
  requirement: string;
  category?: string | null;
  severity?: string | null;
  reason?: string | null;
}

export interface MatchStats {
  total_requirements: number;
  matched: number;
  partial: number;
  missing: number;
  match_percentage: number;
  weighted_match_percentage: number;
}

export interface GapAnalysisResult {
  matched: string[];
  partially_matched: string[];
  missing: string[];
  strengths: string[];
  priority_gaps: PriorityGap[];
  stats: MatchStats;
}

export interface GapAllocation {
  requirement: string;
  severity?: string | null;
  allocated_hours: number;
  share_percentage: number;
  actions?: string[];
}

export interface WeekPlan {
  week: number;
  hours: number;
  focus: string[];
}

export interface PreparationPlan {
  days_until_interview: number;
  hours_per_week: number;
  total_available_hours: number;
  allocations: GapAllocation[];
  weekly_structure: WeekPlan[];
  notes?: string[];
}

export interface QuestionCategory {
  name: string;
  questions: string[];
}

export interface InterviewQuestionSet {
  role: string;
  categories: QuestionCategory[];
}

export interface ToolResultResponse<T = unknown> {
  ok: boolean;
  tool_name: string;
  status: string;
  result: T | null;
  error?: string | null;
}

export interface JobAnalysisRequest {
  job_description: string;
}
export interface GapAnalysisRequest {
  candidate_background: string;
  role_requirements: RoleRequirements;
}
export interface PreparationPlanRequest {
  priority_gaps: PriorityGap[];
  days_until_interview: number;
  hours_per_week: number;
}
export interface QuestionsRequest {
  role: string;
  requirements: string[];
  focus: string[];
}

// --- Interview handoff -------------------------------------------------------

export interface PreparationContextInput {
  target_role: string;
  industry?: string | null;
  company_context?: string | null;
  job_description?: string | null;
  seniority?: string | null;
  required_skills?: string[];
  key_responsibilities?: string[];
  leadership_expectations?: string[];
  candidate_strengths?: string[];
  candidate_gaps?: string[];
  likely_interview_topics?: string[];
  priority_competencies?: string[];
}

export interface CreateInterviewRequest {
  preparation_context?: PreparationContextInput;
  industry_or_sector?: string | null;
  career_level?: string | null;
  interview_types?: string[];
  interviewer_persona?: string;
  difficulty?: string;
  response_detail?: string;
  number_of_questions?: number | null;
}

export interface QuestionOut {
  question_id: number;
  question: string;
  question_type: string;
  competency: string;
  difficulty: string;
}

export interface InterviewStateResponse {
  session_id: string;
  state: string;
  question_number: number;
  questions_planned?: number | null;
  current_question?: QuestionOut | null;
  report_available: boolean;
  last_evaluation?: Record<string, unknown> | null;
  target_role?: string | null;
}

// --- Knowledge / history -----------------------------------------------------

export interface KnowledgeSource {
  source_id?: string | null;
  title?: string | null;
  group?: string | null;
  source_type?: string | null;
}
export interface KnowledgeSourcesResponse {
  sources: KnowledgeSource[];
}
export interface KnowledgeSnapshotResponse {
  documents: number;
  chunks: number;
  document_types: number;
}
export interface InterviewListResponse {
  interviews: Array<Record<string, unknown>>;
}

// --- Preparation memory (Phase 7) -------------------------------------------

export type MemoryCategory =
  | "target_role"
  | "recurring_gap"
  | "strength"
  | "completed_topic"
  | "interview_preference"
  | "preparation_goal";

export interface MemoryCreateRequest {
  category: MemoryCategory;
  summary: string;
  target_role?: string | null;
}

export interface MemoryResponse {
  id: number;
  category: MemoryCategory;
  summary: string;
  target_role: string | null;
  source_run_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface MemoryListResponse {
  memories: MemoryResponse[];
}

export interface MemoryDeleteResponse {
  deleted: boolean;
  id: number;
}

// --- Agent Coach + HITL (Phase 9) -------------------------------------------

export interface CapabilitiesAgent {
  agentic_rag: boolean;
  agent_memory: boolean;
  human_in_the_loop: boolean;
  agent_coach_enabled: boolean;
}

export interface AgentRunRequest {
  goal: string;
  target_role?: string | null;
  job_description?: string | null;
  candidate_background?: string | null;
}

export interface AgentContinueRequest {
  message: string;
}

export type HumanActionType =
  | "confirm_role"
  | "approve_memory"
  | "approve_practice_handoff";

export interface PendingHumanAction {
  action_id: string;
  type: HumanActionType;
  message: string;
  options: string[];
  data: Record<string, unknown>;
  created_at?: string | null;
}

export interface HumanDecisionRequest {
  action_id: string;
  decision: "select" | "approve" | "reject";
  selected_role?: string | null;
}

export interface AgentConversationMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AgentToolCall {
  tool: string;
  status: string;
}

export interface AgentEvent {
  event_type: string;
  step?: number;
  tool_name?: string | null;
  duration_ms?: number | null;
  source_count?: number | null;
  status?: string | null;
  message?: string | null;
  timestamp?: number;
}

export interface AgentSource {
  title?: string | null;
  source_url?: string | null;
  evidence_type?: string | null;
  geography?: string | null;
  occupation_title?: string | null;
  reference_year?: number | null;
}

export interface AgentCitation {
  marker?: string | null;
  title?: string | null;
  source?: string | null;
  page?: number | null;
}

export type AgentStatus =
  | "running"
  | "completed"
  | "failed"
  | "step_limit_reached"
  | "awaiting_human_input";

export interface AgentRunResponse {
  run_id: string;
  status: AgentStatus | string;
  response: string;
  tools_used: string[];
  retrieval_used: boolean;
  sources: AgentSource[];
  citations: AgentCitation[];
  resolved_occupation?: string | null;
  resolved_geography?: string | null;
  memory_used: boolean;
  memory_count: number;
  awaiting_human_input: boolean;
  pending_action?: PendingHumanAction | null;
  handoff_approved: boolean;
  events: AgentEvent[];
  tool_calls: AgentToolCall[];
  warnings: string[];
  step_count: number;
  turn_step_count: number;
  conversation: AgentConversationMessage[];
  preparation_context?: PreparationContextInput | null;
}
