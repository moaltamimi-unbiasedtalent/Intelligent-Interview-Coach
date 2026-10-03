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
  // Realtime voice (Capstone P7.5) — deployment flag AND a configured provider key.
  // When false, the UI stays on P7 turn-based voice.
  realtime_voice_enabled: boolean;
  // Company Intelligence (P10B Wave 5) — the directable company-research surface is on
  // (external research enabled and not operator-paused). Never implies a provider key.
  company_research_enabled: boolean;
}

// --- Opportunities (P10B Wave 6) ---------------------------------------------
// A candidate's private preparation context for one job. Distinct from a Workspace
// (collaboration/sharing). Owner-scoped; mirrors src/api/schemas/opportunity.py.

export type OpportunityStatus =
  | "active" | "interviewing" | "offer" | "closed" | "archived";

export interface Opportunity {
  id: number;
  title: string;
  target_role: string;
  company_name?: string | null;
  company_location?: string | null;
  company_country?: string | null;
  company_domain?: string | null;
  job_description_document_id?: number | null;
  status: OpportunityStatus;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  archived_at?: string | null;
}

export interface OpportunityOverview extends Opportunity {
  jd_available: boolean;
  interview_ids: number[];
  interview_count: number;
}

export interface OpportunityListResponse {
  opportunities: Opportunity[];
}

export interface OpportunityCreateRequest {
  target_role: string;
  title?: string | null;
  company_name?: string | null;
  company_location?: string | null;
  company_country?: string | null;
  company_domain?: string | null;
  job_description_document_id?: number | null;
  notes?: string | null;
}

export interface OpportunityUpdateRequest {
  target_role?: string | null;
  title?: string | null;
  company_name?: string | null;
  company_location?: string | null;
  company_country?: string | null;
  company_domain?: string | null;
  job_description_document_id?: number | null;
  notes?: string | null;
  status?: OpportunityStatus | null;
}

// --- Company Intelligence (P10B Wave 5) --------------------------------------
// Mirrors src/application/company_intelligence_service.py. The UI must render FACT / REVIEW /
// MODEL_INFERENCE distinctly and never blur them.

export type CompanyClaimKind = "fact" | "review" | "model_inference";

export type CompanyProviderState =
  | "configured" | "unavailable" | "disabled" | "partial" | "failed" | "stale"
  | "not_integrated" | "live_unvalidated";

export type CompanyReportStatus =
  | "ready" | "partial" | "needs_clarification" | "insufficient_evidence" | "unavailable";

export interface CompanyIntelligenceRequest {
  company_name: string;
  location?: string | null;
  country?: string | null;
  website?: string | null;
  target_role?: string | null;
  job_description_document_id?: number | null;
}

export interface CompanySourceRef {
  id: string;
  title: string;
  url?: string | null;
  source_type: string;
  provider: string;
  retrieved_at?: string | null;
  effective_date?: string | null;
  self_reported: boolean;
}

export interface CompanyClaim {
  kind: CompanyClaimKind;
  text: string;
  source_ids: string[];
}

export interface CompanyProviderStatus {
  key: string;
  label: string;
  state: CompanyProviderState;
  detail?: string | null;
  external_url?: string | null;
}

export interface CompanyIdentity {
  company_name: string;
  location?: string | null;
  country?: string | null;
  website?: string | null;
  domain?: string | null;
  confidence: "confirmed" | "needs_clarification";
  note?: string | null;
}

export interface CompanySnapshot {
  industry?: string | null;
  description?: string | null;
  website?: string | null;
  retrieved_at?: string | null;
}

export interface CompanyInterviewPreparation {
  topics: CompanyClaim[];
  questions_to_ask: CompanyClaim[];
  clarify: CompanyClaim[];
}

export interface CompanyIntelligenceReport {
  status: CompanyReportStatus;
  identity: CompanyIdentity;
  snapshot: CompanySnapshot;
  business_market: CompanyClaim[];
  recent_developments: CompanyClaim[];
  culture: CompanyClaim[];
  review_signals: CompanyClaim[];
  role_relevance: CompanyClaim[];
  interview_preparation: CompanyInterviewPreparation;
  sources: CompanySourceRef[];
  provider_statuses: CompanyProviderStatus[];
  limitations: string[];
  warnings: string[];
  retrieved_at?: string | null;
  cache_hit: boolean;
  jd_linked: boolean;
}

// Realtime voice (Capstone P7.5, C1).
export interface RealtimeSessionRequest {
  locale?: string;
  surface?: "practice" | "prepare";
  interview_session_id?: string | null;
}

export interface RealtimeSessionResponse {
  provider: string;
  model: string;
  voice: string;
  locale: string;
  client_secret: string; // ephemeral, short-lived — never the long-lived key
  expires_at: number;
  session_id: string;
  base_url: string;
  max_session_seconds: number;
  idle_timeout_seconds: number;
}

export interface RealtimeStatusResponse {
  enabled: boolean;
  configured: boolean;
  available: boolean;
  provider: string;
  supported_locales: string[];
  max_session_seconds: number;
  max_concurrent_per_user: number;
  fallback: string;
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
  /** Mo conversation language (bounded locale code). Owns Mo's prose + deterministic fallback text. */
  conversation_language?: string | null;
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
  authority_level?: number | null; // numeric authority tier (1..3), matches the API SourceOut
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

export interface InterviewConfigInput {
  target_role: string;
  industry_or_sector: string;
  career_level: string;
  interview_types?: string[];
  interviewer_persona?: string;
  difficulty?: string;
  response_detail?: string;
  number_of_questions?: number | null;
  /** Prose language for generated question/evaluation/report (Practice multilingual, Wave 4). */
  conversation_language?: string | null;
  /** Owner-scoped selected JD document; the server resolves it to text (raw text never sent). */
  job_description_document_id?: number | null;
  /** Compose candidate context from the caller's APPROVED evidence only. */
  use_candidate_evidence?: boolean;
}

export interface CreateInterviewRequest {
  configuration?: InterviewConfigInput;
  preparation_context?: PreparationContextInput;
  industry_or_sector?: string | null;
  career_level?: string | null;
  interview_types?: string[];
  interviewer_persona?: string;
  difficulty?: string;
  response_detail?: string;
  number_of_questions?: number | null;
  // Optional organising link to a candidate Opportunity (P10B Wave 6); server verifies ownership.
  opportunity_id?: number | null;
}

export interface QuestionOut {
  question_id: number;
  question: string;
  question_type: string;
  competency: string;
  difficulty: string;
}

/** Candidate-safe answer feedback (mirrors the backend EvaluationOut exactly). */
export interface EvaluationOut {
  overall_score: number;
  relevance: number;
  structure: number;
  evidence: number;
  role_knowledge: number;
  problem_solving: number;
  communication: number;
  credibility: number;
  strengths: string[];
  improvement_areas: string[];
  missing_evidence: string[];
  stronger_answer_structure: string;
  improved_example_answer: string;
  follow_up_question: string;
}

export interface BranchQuestionOut {
  branch_id: string;
  parent_question_id: number;
  question: string;
  branch_mode: string;
  focus_area: string;
  difficulty: string;
  depth: number;
}

export interface DeepDiveStateOut {
  active: boolean;
  mode?: string | null;
  depth: number;
  max_depth: number;
  parent_question_id?: number | null;
  current_branch_question?: BranchQuestionOut | null;
  last_branch_evaluation?: EvaluationOut | null;
  can_go_deeper: boolean;
}

export interface InterviewStateResponse {
  session_id: string;
  state: string;
  question_number: number;
  questions_planned?: number | null;
  current_question?: QuestionOut | null;
  report_available: boolean;
  last_evaluation?: EvaluationOut | null;
  target_role?: string | null;
  deep_dive?: DeepDiveStateOut | null;
  error?: string | null;
  error_recoverable?: boolean;
  cumulative_cost_usd?: number | null;
}

export interface ReportResponse {
  session_id: string;
  report: Record<string, unknown>;
  saved_report_id?: number | null;
  save_failed?: boolean;
}

export interface ActiveSessionSummary {
  session_id: string;
  target_role?: string | null;
  state: string;
  question_number: number;
  questions_planned?: number | null;
  updated_at?: string | null;
}

export interface ActiveSessionsResponse {
  sessions: ActiveSessionSummary[];
}

// --- Knowledge / history -----------------------------------------------------

export interface KnowledgeSource {
  source_id?: string | null;
  title?: string | null;
  group?: string | null;
  source_type?: string | null;
  /** Curated official landing page (https only); absent when no public record exists. */
  source_url?: string | null;
  provider?: string | null;
  country?: string | null;
  reference_year?: number | null;
}
export interface KnowledgeSourcesResponse {
  sources: KnowledgeSource[];
}
export interface KnowledgeSnapshotResponse {
  documents: number;
  chunks: number;
  document_types: number;
}

/** Read-only Knowledge/RAG diagnostics — runtime counts + offline retrieval evaluation. */
export interface KnowledgeDiagnosticsResponse {
  runtime: {
    occupations?: number | null;
    aliases?: number | null;
    skills?: number | null;
    tasks?: number | null;
    knowledge_areas?: number | null;
    work_activities?: number | null;
    compensation?: number | null;
    labour_market?: number | null;
    competencies?: number | null;
    credentials?: number | null;
    sources?: number | null;
    runtime_pipeline_version?: string | null;
    normalized_pipeline_version?: string | null;
    built_at?: string | null;
  };
  retrieval_evaluation: {
    cases?: number | null;
    passed?: number | null;
    pass_rate?: number | null;
    evidence_coverage_rate?: number | null;
    citation_completeness_rate?: number | null;
    geography_correctness_rate?: number | null;
    unknown_role_safety_rate?: number | null;
    unsupported_geography_safety_rate?: number | null;
    no_fabricated_citation_rate?: number | null;
    safety_pass_rate?: number | null;
  };
  known_gaps: string[];
}
export interface InterviewSummary {
  id: number;
  target_role?: string | null;
  mode?: string | null;
  status?: string | null;
  questions?: number | null;
  created_at?: string | null;
}

/** A stored (offline) RAGAS evaluation run from GET /evaluation/latest. Read-only. */
export interface EvaluationRunResponse {
  available: boolean;
  metrics?: Record<string, number> | null;
  run_config?: Record<string, unknown> | null;
}

/** Practice progress from GET /progress — derived only from the caller's own interviews. */
export interface ProgressResponse {
  interviews_completed: number;
  answers_evaluated: number;
  average_practice_score?: number | null;
  most_common_improvement_area?: string | null;
  average_answer_seconds?: number | null;
  recent_interviews: InterviewSummary[];
}
export interface InterviewListResponse {
  interviews: Array<Record<string, unknown>>;
}

/** Full history record from GET /history/interviews/{id} (report already included). */
export interface InterviewDetail {
  id: number;
  configuration?: Record<string, unknown> | null;
  mode?: string | null;
  status?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  created_at?: string | null;
  questions?: Array<Record<string, unknown>>;
  report?: {
    report?: Record<string, unknown> | null;
    usage?: Record<string, unknown> | null;
    cost_usd?: number | null;
  } | null;
}
export interface InterviewDetailResponse {
  interview: InterviewDetail;
}

export interface InterviewOptionsResponse {
  career_levels: string[];
  interview_types: string[];
  difficulty_levels?: string[];
  deep_dive_modes?: string[];
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

/** Partial edit (P2). Omit a field to leave it untouched; target_role:null clears it. */
export interface MemoryUpdateRequest {
  category?: MemoryCategory;
  summary?: string;
  target_role?: string | null;
  pinned?: boolean;
}

export interface MemoryResponse {
  id: number;
  category: MemoryCategory;
  summary: string;
  target_role: string | null;
  pinned: boolean;
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

/** One memory that WOULD load for a run (safe projection + order/reason). */
export interface MemoryPreviewItem {
  id: number;
  category: MemoryCategory;
  summary: string;
  target_role: string | null;
  pinned: boolean;
  order: number;
  reason: string;
}

export interface MemoryPreviewResponse {
  target_role: string | null;
  load_limit: number;
  items: MemoryPreviewItem[];
}

// --- Agent Coach + HITL (Phase 9) -------------------------------------------

export interface CapabilitiesAgent {
  agentic_rag: boolean;
  agent_memory: boolean;
  human_in_the_loop: boolean;
  agent_coach_enabled: boolean;
}

/** The three Agent speed/quality tiers a candidate may pick (never a raw model slug). */
export type AgentProfile = "fast" | "balanced" | "advanced";

export interface AgentRunRequest {
  goal: string;
  target_role?: string | null;
  job_description?: string | null;
  candidate_background?: string | null;
  profile?: AgentProfile | null;
  /** Capability toggle (#16): false withholds ResearchCurrentMarket for the run (server-enforced). */
  enable_current_market_research?: boolean | null;
  /** Mo conversation language (P3.5): a bounded locale code; sets Mo's prose language only. */
  conversation_language?: string | null;
  /** Mo coaching style (P10B Wave 2): a bounded tone; wording only, never scoring. */
  coaching_style?: string | null;
  /** Owner-scoped selected JD document; the server resolves it to text (raw text never sent). */
  job_description_document_id?: number | null;
}

/** Safe provider-usage aggregate. Unknown usage is never reported as zero. */
export interface AgentUsage {
  agent_model_calls: number;
  tool_model_calls: number;
  model_calls: number;
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
  estimated_cost_usd?: number | null;
  usage_complete: boolean;
  missing_usage_sources: string[];
}

export interface AgentContinueRequest {
  message: string;
}

export interface AgentRunDeleteResponse {
  deleted: boolean;
  run_id: string;
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

/** An edited memory for an APPROVE_MEMORY 'approve' (edit-before-save, P2). */
export interface EditedMemory {
  category: MemoryCategory;
  summary: string;
  target_role?: string | null;
}

export interface HumanDecisionRequest {
  action_id: string;
  decision: "select" | "approve" | "reject";
  selected_role?: string | null;
  memory?: EditedMemory;
}

export interface AgentConversationMessage {
  role: "user" | "assistant";
  content: string;
  /** Stable per-answer id for feedback targeting (assistant messages only, P5). */
  response_id?: string;
}

export interface AgentToolCall {
  tool: string;
  status: string;
  /** Safe failure category on a failed call (missing_prerequisite | invalid_arguments | execution_failed). */
  category?: string | null;
}

export interface AgentEvent {
  event_type: string;
  step?: number;
  tool_name?: string | null;
  duration_ms?: number | null;
  source_count?: number | null;
  status?: string | null;
  /** Safe failure category on a tool_failed event; never arguments or content. */
  category?: string | null;
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

export type JourneyStageStatus = "not_started" | "in_progress" | "complete";

/** Candidate journey (UNDERSTAND→PREPARE→PRACTISE) derived from real state (P4). */
export interface PreparationJourney {
  understand: { status: JourneyStageStatus; role_known: boolean; requirements_known: boolean; evidence_used: boolean };
  prepare: { status: JourneyStageStatus; gaps_known: boolean; plan_known: boolean; questions_known: boolean };
  practise: { status: JourneyStageStatus; handoff_approved: boolean };
}

/** Safe explanation of what/where the Practice handoff carries (P4). */
export interface PracticeHandoffSummary {
  target_role: { value: string; source: string };
  focus_areas?: { value: string; source: string }[];
  question_count?: number;
  question_source?: string;
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
  /** Safe summaries of the memories loaded into this run (category/summary/role). */
  memory_loaded?: { category: MemoryCategory; summary: string; target_role: string | null }[];
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
  /** Cost/performance instrumentation (P1). */
  usage?: AgentUsage | null;
  profile?: AgentProfile | string | null;
  latency_ms?: number | null;
  cache_hits?: number;
  cache_misses?: number;
  /** Candidate journey + handoff provenance (P4). */
  journey?: PreparationJourney;
  handoff_summary?: PracticeHandoffSummary | null;
  /** Presentation contract for progressive disclosure (P2/E2). */
  presentation?: ResponsePresentation | null;
}

// --- Candidate feedback (P5) -------------------------------------------------

export type FeedbackSurface = "agent_answer" | "interview_evaluation" | "final_report";
export type FeedbackRating = "helpful" | "not_helpful";

export interface FeedbackCreateRequest {
  surface: FeedbackSurface;
  target_id: string;
  rating: FeedbackRating;
  comment?: string | null;
  category?: string | null;
}

export interface FeedbackResponse {
  id: number;
  surface: FeedbackSurface;
  target_id: string;
  rating: FeedbackRating;
  comment: string | null;
  category?: string | null;
  created_at: string | null;
  updated_at: string | null;
}

// --- Teams / Workspaces & sharing (Capstone P6.5) ----------------------------

export interface WorkspaceSummary {
  id: number;
  name: string;
  status: string;
  owner_user_id: number;
  member_count: number;
  created_at: string | null;
  my_role?: string;
}

export interface WorkspaceMember {
  user_id: number;
  role: string;
  status: string;
  joined_at: string | null;
}

export interface WorkspaceInvite {
  id: number;
  workspace_id: number;
  role: string;
  status: string;
  expires_at: string | null;
  workspace_name?: string | null;
}

export interface WorkspaceDetail extends WorkspaceSummary {
  members: WorkspaceMember[];
  pending_invitations?: WorkspaceInvite[];
}

export interface MyWorkspaces {
  workspaces: WorkspaceSummary[];
  invited: WorkspaceInvite[];
}

export interface ShareGrantOut {
  id: number;
  owner_user_id: number;
  workspace_id: number;
  resource_type: string;
  resource_id: string;
  permission: string;
  status: string;
  created_at: string | null;
  revoked_at: string | null;
}

// --- Authentication & account (Capstone P1/E1) -------------------------------

export interface AuthMessageResponse {
  message: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  display_name?: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export type ResponseDetail = "brief" | "detailed";

export interface AccountResponse {
  user_id: number;
  email: string | null;
  display_name: string | null;
  platform_role: string;
  tier: string;
  status: string;
  email_verified: boolean;
  providers: string[];
  auth_method: string;
  capabilities: string[];
  admin_permissions?: string[];
  /** Presentation depth (P2/E2) — brief/detailed. Not a model profile. */
  response_detail: ResponseDetail;
  /** Interface UI language (P3.5). Independent of conversation/dictation language. */
  interface_locale: string;
  /** Mo conversation language (P3.5). Independent of interface/dictation language. */
  conversation_language: string;
  /** Bounded Mo coaching tone (P10B Wave 2). Tone only — never changes scoring. */
  coaching_style: string;
  /** Account-default career geography (P10B Wave 2). Independent of any language. */
  career_geography: string;
  /** Account-default career-focus role (P10B Wave 2). */
  target_role: string;
  /** First-run onboarding lifecycle (P10B Wave 2). */
  onboarding_completed: boolean;
  onboarding_step: number;
}

/** Partial preference update (P2/E2 + P3.5 + P10B Wave 2) — send only the fields you change. */
export interface PreferencesRequest {
  response_detail?: ResponseDetail;
  interface_locale?: string;
  conversation_language?: string;
  coaching_style?: string;
  career_geography?: string;
  target_role?: string;
  display_name?: string;
}

/** Deterministic presentation contract for progressive disclosure (P2/E2). */
export interface ResponsePresentation {
  answer: string;
  details: string;
  has_details: boolean;
  next_step: { label: string; kind: string } | null;
}

export interface PremiumStatusResponse {
  entitled: boolean;
  tier: string;
  message: string;
}

// --- Private documents & evidence (Capstone P4/E2/E3) ------------------------

export interface DocumentSummary {
  id: number;
  category: string;
  title: string;
  status: string;
  current_version: number;
  updated_at?: string | null;
  failure_kind?: string | null;
  extraction_origin?: string | null;
}

export interface DocumentVersionOut {
  version: number;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  page_count?: number | null;
  extraction_origin?: string | null;
  status: string;
  failure_reason?: string | null;
  failure_kind?: string | null;
  language_hint?: string | null;
}

export interface ClaimOut {
  id: number;
  document_id: number;
  version_id: number;
  claim_type: string;
  text: string;
  edited_text?: string | null;
  display_text: string;
  source_page?: number | null;
  source_section?: string | null;
  review_state: string;
}

export interface DocumentDetail {
  id: number;
  category: string;
  title: string;
  status: string;
  current_version: number;
  created_at?: string | null;
  versions: DocumentVersionOut[];
  claims: ClaimOut[];
}

export interface StoryOut {
  id: number;
  title: string;
  situation?: string | null;
  task?: string | null;
  action?: string | null;
  result?: string | null;
  competencies: string[];
  status: string;
  evidence_state: string;
  evidence_claim_ids: number[];
  updated_at?: string | null;
}

// --- Customer support (P10B-W10.3). Candidate-visible shapes only: no internal notes, priority or operator identity.
export type SupportCategory =
  | "account_login" | "opportunity" | "prepare" | "practice_interview" | "documents" | "ai_response"
  | "billing" | "privacy" | "accessibility" | "technical" | "data_issue" | "other";
export type SupportStatus = "new" | "triaged" | "in_progress" | "waiting_for_customer" | "resolved" | "closed";
export interface SupportTicketSummary {
  public_id: string;
  category: SupportCategory;
  status: SupportStatus;
  subject: string;
  created_at: string | null;
  updated_at: string | null;
}
export interface SupportTicketList {
  items: SupportTicketSummary[];
  total: number;
  page: number;
  page_size: number;
}
export interface SupportThreadMessage {
  id: number;
  author_kind: "candidate" | "support";
  body: string;
  created_at: string | null;
}
export interface SupportTicketDetail extends SupportTicketSummary {
  can_reply: boolean;
  messages: SupportThreadMessage[];
}
export interface SupportCreateRequest {
  category: SupportCategory;
  subject: string;
  message: string;
  request_id?: string;
  source_route?: string;
}

// --- Plans (P10B-W10.4): the caller's OWN plan. Read-only; no price, payment or internal plan metadata. ---
export interface EntitlementState {
  enabled: boolean;
  limit: number | null;
  unlimited: boolean;
}
export interface PlanResponse {
  plan_code: string;
  plan_version: number | null;
  entitlements: Record<string, EntitlementState>;
}
