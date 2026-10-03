import { config } from "../config";
import { ApiError, apiErrorFromBody, parseRetryAfter, unreachableError } from "./errors";
import { runWithRetry } from "./retry";
import type {
  AdminAuditEvent,
  AdminCommandCenter,
  AdminPage,
  AdminAssignee,
  JobDetail,
  LegalOverview,
  LegalVersionRow,
  PreparationCoverage,
  PrivacyQuery,
  PrivacyRequestDetail,
  PrivacyRequestRow,
  KnowledgeMeta,
  KnowledgeQuery,
  KnowledgeRow,
  KnowledgeSourceDetail,
  KnowledgeVersionDetail,
  JobDiagnostics,
  JobQuery,
  JobRow,
  JobTypeInfo,
  IntegrationDetail,
  IntegrationRow,
  IntegrationTestResult,
  AssignablePlan,
  PlanDetail,
  PlanVersionRow,
  AdminProviders,
  AdminTicketDetail,
  AdminTicketQuery,
  AdminTicketSummary,
  AdminUserDetail,
  AdminUserQuery,
  AdminUserSummary,
  AdminWorkspaceDetail,
  AdminWorkspaceSummary,
} from "../admin/types";
import type {
  ActiveSessionsResponse,
  PlanResponse,
  LegalStatus,
  PrivacyRequestList,
  PrivacyRequestView,
  SupportCreateRequest,
  SupportTicketDetail,
  SupportTicketList,
  SupportTicketSummary,
  CapabilitiesResponse,
  CompanyIntelligenceRequest,
  CompanyIntelligenceReport,
  Opportunity,
  OpportunityOverview,
  OpportunityListResponse,
  OpportunityCreateRequest,
  OpportunityUpdateRequest,
  CareerChatRequest,
  CareerChatResponse,
  CreateInterviewRequest,
  ReportResponse,
  GapAnalysisRequest,
  GapAnalysisResult,
  HealthResponse,
  InterviewListResponse,
  InterviewDetailResponse,
  ProgressResponse,
  EvaluationRunResponse,
  InterviewQuestionSet,
  InterviewStateResponse,
  JobAnalysisRequest,
  RealtimeSessionRequest,
  RealtimeSessionResponse,
  RealtimeStatusResponse,
  AgentContinueRequest,
  AgentRunDeleteResponse,
  AgentRunRequest,
  AgentRunResponse,
  HumanDecisionRequest,
  InterviewOptionsResponse,
  FeedbackCreateRequest,
  FeedbackResponse,
  FeedbackSurface,
  MyWorkspaces,
  ShareGrantOut,
  WorkspaceDetail,
  WorkspaceSummary,
  KnowledgeSnapshotResponse,
  KnowledgeSourcesResponse,
  KnowledgeDiagnosticsResponse,
  MemoryCategory,
  MemoryCreateRequest,
  MemoryDeleteResponse,
  MemoryListResponse,
  MemoryPreviewResponse,
  MemoryResponse,
  MemoryUpdateRequest,
  PreparationPlan,
  PreparationPlanRequest,
  QuestionsRequest,
  RoleRequirements,
  ToolResultResponse,
  AccountResponse,
  AuthMessageResponse,
  LoginRequest,
  RegisterRequest,
  PremiumStatusResponse,
  PreferencesRequest,
  DocumentSummary,
  DocumentDetail,
  ClaimOut,
  StoryOut,
} from "./types";

const REQUEST_ID_HEADER = "x-request-id";
const RETRY_AFTER_HEADER = "retry-after";

interface RequestOptions {
  signal?: AbortSignal;
}

/** True unless the browser explicitly reports the device offline (SSR: assume online). */
function browserIsOnline(): boolean {
  return typeof navigator === "undefined" ? true : navigator.onLine;
}

function authHeaders(): Record<string, string> {
  // Transitional local-dev identity only (see lib/config.ts). Sent ONLY in dev, and
  // ignored by the backend in production (where a real session cookie is required).
  // A valid session cookie always takes precedence over this header server-side.
  return config.devUserSubject ? { "X-User-Subject": config.devUserSubject } : {};
}

/** Multipart upload helper (P4): sends FormData with the session cookie; no JSON body. */
async function upload<T>(path: string, form: FormData): Promise<T> {
  // Uploads are writes (POST multipart): NEVER auto-retried, so a document is never
  // ingested twice by transport-level resilience.
  let res: Response;
  try {
    res = await fetch(`${config.apiBaseUrl}${path}`, {
      method: "POST",
      credentials: "include",
      headers: { Accept: "application/json", ...authHeaders() }, // no Content-Type: browser sets the boundary
      body: form,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw unreachableError(browserIsOnline());
  }
  const requestId = res.headers.get(REQUEST_ID_HEADER);
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await res.json().catch(() => undefined) : undefined;
  if (!res.ok) {
    throw apiErrorFromBody(res.status, payload, requestId, parseRetryAfter(res.headers.get(RETRY_AFTER_HEADER)));
  }
  return payload as T;
}

async function request<T>(
  method: "GET" | "POST" | "PATCH" | "DELETE",
  path: string,
  { body, signal, headers }: { body?: unknown; signal?: AbortSignal; headers?: Record<string, string> } = {},
): Promise<T> {
  const url = `${config.apiBaseUrl}${path}`;

  // One network attempt. Wrapped by runWithRetry, which re-sends ONLY safe/idempotent
  // methods (GET/HEAD) on transient failures — never writes, so career chat, agent
  // messages, Practice answers, handoffs and memory mutations can't execute twice.
  const attempt = async (): Promise<T> => {
    let res: Response;
    try {
      res = await fetch(url, {
        method,
        // Send the session cookie with every request (the trusted production identity).
        // CORS on the backend allows credentials for the configured frontend origin.
        credentials: "include",
        headers: {
          Accept: "application/json",
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
          ...authHeaders(),
          ...(headers ?? {}),
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal,
      });
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
      // fetch() rejected: the response never arrived. Classify truthfully — offline vs an
      // Ask4Mo/backend/CORS problem — instead of blaming the candidate's connection.
      throw unreachableError(browserIsOnline());
    }

    const requestId = res.headers.get(REQUEST_ID_HEADER);
    const isJson = res.headers.get("content-type")?.includes("application/json");
    const payload = isJson ? await res.json().catch(() => undefined) : undefined;

    if (!res.ok) {
      throw apiErrorFromBody(
        res.status, payload, requestId, parseRetryAfter(res.headers.get(RETRY_AFTER_HEADER)));
    }
    return payload as T;
  };

  return runWithRetry(method, attempt, { signal });
}

/** Query string from defined, non-empty values only (admin list filters). */
function qs(params: Record<string, unknown>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const text = sp.toString();
  return text ? `?${text}` : "";
}

/** Typed FastAPI client. Add new typed methods here rather than calling fetch ad hoc. */
export const api = {
  health: (opts?: RequestOptions) => request<HealthResponse>("GET", "/health", opts),
  capabilities: (opts?: RequestOptions) =>
    request<CapabilitiesResponse>("GET", "/capabilities", opts),

  career: {
    chat: (body: CareerChatRequest, opts?: RequestOptions) =>
      request<CareerChatResponse>("POST", "/career/chat", { body, ...opts }),
    jobAnalysis: (body: JobAnalysisRequest, opts?: RequestOptions) =>
      request<ToolResultResponse<RoleRequirements>>("POST", "/career/job-analysis", { body, ...opts }),
    gapAnalysis: (body: GapAnalysisRequest, opts?: RequestOptions) =>
      request<ToolResultResponse<GapAnalysisResult>>("POST", "/career/gap-analysis", { body, ...opts }),
    preparationPlan: (body: PreparationPlanRequest, opts?: RequestOptions) =>
      request<ToolResultResponse<PreparationPlan>>("POST", "/career/preparation-plan", { body, ...opts }),
    questions: (body: QuestionsRequest, opts?: RequestOptions) =>
      request<ToolResultResponse<InterviewQuestionSet>>("POST", "/career/questions", { body, ...opts }),
  },

  interviews: {
    // `idempotencyKey` (e.g. an agent handoff's run id) makes creation safe to retry:
    // the same key returns the same session without re-running generation.
    create: (body: CreateInterviewRequest, opts?: RequestOptions & { idempotencyKey?: string }) =>
      request<InterviewStateResponse>("POST", "/interviews", {
        body,
        signal: opts?.signal,
        headers: opts?.idempotencyKey ? { "Idempotency-Key": opts.idempotencyKey } : undefined,
      }),
    get: (sessionId: string, opts?: RequestOptions) =>
      request<InterviewStateResponse>("GET", `/interviews/${encodeURIComponent(sessionId)}`, opts),
    options: (opts?: RequestOptions) =>
      request<InterviewOptionsResponse>("GET", "/interviews/options", opts),
    listActive: (opts?: RequestOptions) =>
      request<ActiveSessionsResponse>("GET", "/interviews", opts),
    remove: (sessionId: string, opts?: RequestOptions) =>
      request<{ deleted: boolean }>("DELETE", `/interviews/${encodeURIComponent(sessionId)}`, opts),
    submitAnswer: (sessionId: string, answer: string, opts?: RequestOptions) =>
      request<InterviewStateResponse>("POST", `/interviews/${encodeURIComponent(sessionId)}/answers`, { body: { answer }, ...opts }),
    nextQuestion: (sessionId: string, opts?: RequestOptions) =>
      request<InterviewStateResponse>("POST", `/interviews/${encodeURIComponent(sessionId)}/next-question`, opts),
    complete: (sessionId: string, opts?: RequestOptions) =>
      request<InterviewStateResponse>("POST", `/interviews/${encodeURIComponent(sessionId)}/complete`, opts),
    recover: (sessionId: string, opts?: RequestOptions) =>
      request<InterviewStateResponse>("POST", `/interviews/${encodeURIComponent(sessionId)}/recover`, opts),
    report: (sessionId: string, opts?: RequestOptions) =>
      request<ReportResponse>("GET", `/interviews/${encodeURIComponent(sessionId)}/report`, opts),
    generateReport: (sessionId: string, opts?: RequestOptions) =>
      request<ReportResponse>("POST", `/interviews/${encodeURIComponent(sessionId)}/report`, opts),
    deepDive: {
      start: (sessionId: string, mode: string, opts?: RequestOptions) =>
        request<InterviewStateResponse>("POST", `/interviews/${encodeURIComponent(sessionId)}/deep-dive`, { body: { mode }, ...opts }),
      answer: (sessionId: string, answer: string, opts?: RequestOptions) =>
        request<InterviewStateResponse>("POST", `/interviews/${encodeURIComponent(sessionId)}/deep-dive/answers`, { body: { answer }, ...opts }),
      next: (sessionId: string, opts?: RequestOptions) =>
        request<InterviewStateResponse>("POST", `/interviews/${encodeURIComponent(sessionId)}/deep-dive/next`, opts),
      return: (sessionId: string, opts?: RequestOptions) =>
        request<InterviewStateResponse>("POST", `/interviews/${encodeURIComponent(sessionId)}/deep-dive/return`, opts),
    },
  },

  knowledge: {
    sources: (opts?: RequestOptions) =>
      request<KnowledgeSourcesResponse>("GET", "/knowledge/sources", opts),
    snapshot: (opts?: RequestOptions) =>
      request<KnowledgeSnapshotResponse>("GET", "/knowledge/snapshot", opts),
    diagnostics: (opts?: RequestOptions) =>
      request<KnowledgeDiagnosticsResponse>("GET", "/knowledge/diagnostics", opts),
  },

  progress: {
    get: (opts?: RequestOptions) =>
      request<ProgressResponse>("GET", "/progress", opts),
  },

  evaluation: {
    latest: (opts?: RequestOptions) =>
      request<EvaluationRunResponse>("GET", "/evaluation/latest", opts),
  },

  history: {
    list: (opts?: RequestOptions) =>
      request<InterviewListResponse>("GET", "/history/interviews", opts),
    get: (reportId: number | string, opts?: RequestOptions) =>
      request<InterviewDetailResponse>(
        "GET", `/history/interviews/${encodeURIComponent(String(reportId))}`, opts),
    // P10B-W9.8: owner delete of one completed interview (hard delete; writes are never auto-retried).
    remove: (reportId: number | string, opts?: RequestOptions) =>
      request<{ deleted: boolean }>(
        "DELETE", `/history/interviews/${encodeURIComponent(String(reportId))}`, opts),
  },

  // Agent Coach (Phase 9): the candidate-facing LangGraph agent. All owner-scoped;
  // continue keeps the SAME run/thread; resume answers a pending HITL decision.
  agent: {
    start: (body: AgentRunRequest, opts?: RequestOptions) =>
      request<AgentRunResponse>("POST", "/agent/run", { body, ...opts }),
    getRun: (runId: string, opts?: RequestOptions) =>
      request<AgentRunResponse>("GET", `/agent/runs/${encodeURIComponent(runId)}`, opts),
    continue: (runId: string, body: AgentContinueRequest, opts?: RequestOptions) =>
      request<AgentRunResponse>("POST", `/agent/runs/${encodeURIComponent(runId)}/messages`, { body, ...opts }),
    resume: (runId: string, body: HumanDecisionRequest, opts?: RequestOptions) =>
      request<AgentRunResponse>("POST", `/agent/runs/${encodeURIComponent(runId)}/resume`, { body, ...opts }),
    remove: (runId: string, opts?: RequestOptions) =>
      request<AgentRunDeleteResponse>("DELETE", `/agent/runs/${encodeURIComponent(runId)}`, opts),
  },

  // Company Intelligence (P10B Wave 5). Directable company research; the server enforces
  // capability + operator pause + per-user cost, and resolves any selected JD owner-scoped.
  company: {
    research: (body: CompanyIntelligenceRequest, opts?: RequestOptions) =>
      request<CompanyIntelligenceReport>("POST", "/research/company", { body, ...opts }),
  },

  // Opportunities (P10B Wave 6). Owner-scoped candidate preparation contexts.
  opportunities: {
    list: (includeArchived = false, opts?: RequestOptions) =>
      request<OpportunityListResponse>(
        "GET", `/opportunities${includeArchived ? "?include_archived=true" : ""}`, opts),
    create: (body: OpportunityCreateRequest, opts?: RequestOptions) =>
      request<Opportunity>("POST", "/opportunities", { body, ...opts }),
    get: (id: number, opts?: RequestOptions) =>
      request<OpportunityOverview>("GET", `/opportunities/${id}`, opts),
    update: (id: number, body: OpportunityUpdateRequest, opts?: RequestOptions) =>
      request<Opportunity>("PATCH", `/opportunities/${id}`, { body, ...opts }),
    archive: (id: number, opts?: RequestOptions) =>
      request<Opportunity>("POST", `/opportunities/${id}/archive`, opts),
    remove: (id: number, opts?: RequestOptions) =>
      request<{ deleted: boolean }>("DELETE", `/opportunities/${id}`, opts),
  },

  // Long-term preparation memory (Phase 7). Writes are explicit/user-initiated.
  memory: {
    list: (params?: { category?: MemoryCategory }, opts?: RequestOptions) => {
      const query = params?.category ? `?category=${encodeURIComponent(params.category)}` : "";
      return request<MemoryListResponse>("GET", `/memory${query}`, opts);
    },
    create: (body: MemoryCreateRequest, opts?: RequestOptions) =>
      request<MemoryResponse>("POST", "/memory", { body, ...opts }),
    update: (id: number, body: MemoryUpdateRequest, opts?: RequestOptions) =>
      request<MemoryResponse>("PATCH", `/memory/${id}`, { body, ...opts }),
    remove: (id: number, opts?: RequestOptions) =>
      request<MemoryDeleteResponse>("DELETE", `/memory/${id}`, opts),
    preview: (targetRole?: string | null, opts?: RequestOptions) => {
      const query = targetRole ? `?target_role=${encodeURIComponent(targetRole)}` : "";
      return request<MemoryPreviewResponse>("GET", `/memory/preview${query}`, opts);
    },
  },

  // Accounts, authentication & session (Capstone P1/E1). The session lives in an
  // HttpOnly cookie sent automatically (credentials: "include"); no token in JS.
  auth: {
    /** The caller's own plan and entitlements (read-only). */
    plan: (opts?: RequestOptions) => request<PlanResponse>("GET", "/auth/plan", opts),
    register: (body: RegisterRequest, opts?: RequestOptions) =>
      request<AuthMessageResponse>("POST", "/auth/register", { body, ...opts }),
    login: (body: LoginRequest, opts?: RequestOptions) =>
      request<AuthMessageResponse>("POST", "/auth/login", { body, ...opts }),
    logout: (opts?: RequestOptions) =>
      request<AuthMessageResponse>("POST", "/auth/logout", opts),
    me: (opts?: RequestOptions) => request<AccountResponse>("GET", "/auth/me", opts),
    updatePreferences: (body: PreferencesRequest, opts?: RequestOptions) =>
      request<AccountResponse>("PATCH", "/auth/preferences", { body, ...opts }),
    onboarding: (body: { step?: number; complete?: boolean }, opts?: RequestOptions) =>
      request<AccountResponse>("POST", "/auth/onboarding", { body, ...opts }),
    verifyEmail: (token: string, opts?: RequestOptions) =>
      request<AuthMessageResponse>("POST", "/auth/verify-email", { body: { token }, ...opts }),
    resendVerification: (opts?: RequestOptions) =>
      request<AuthMessageResponse>("POST", "/auth/verify-email/resend", opts),
    forgotPassword: (email: string, opts?: RequestOptions) =>
      request<AuthMessageResponse>("POST", "/auth/forgot-password", { body: { email }, ...opts }),
    resetPassword: (token: string, password: string, opts?: RequestOptions) =>
      request<AuthMessageResponse>("POST", "/auth/reset-password", { body: { token, password }, ...opts }),
    premiumStatus: (opts?: RequestOptions) =>
      request<PremiumStatusResponse>("GET", "/auth/premium/status", opts),
    // Capstone P8: permanent, application-controlled account + data deletion (§14/§15).
    deleteAccount: (opts?: RequestOptions) =>
      request<AuthMessageResponse>("POST", "/auth/account/delete", opts),
  },

  // Private candidate documents, evidence & story bank (Capstone P4/E2/E3).
  documents: {
    list: (opts?: RequestOptions) => request<{ documents: DocumentSummary[] }>("GET", "/documents", opts),
    get: (id: number, opts?: RequestOptions) => request<DocumentDetail>("GET", `/documents/${id}`, opts),
    upload: (file: File, category: string, languageHint?: string) => {
      const form = new FormData();
      form.append("file", file);
      form.append("category", category);
      if (languageHint) form.append("language_hint", languageHint);
      return upload<DocumentDetail>("/documents", form);
    },
    replace: (id: number, file: File, languageHint?: string) => {
      const form = new FormData();
      form.append("file", file);
      if (languageHint) form.append("language_hint", languageHint);
      return upload<DocumentDetail>(`/documents/${id}/replace`, form);
    },
    reprocess: (id: number, opts?: RequestOptions) =>
      request<DocumentDetail>("POST", `/documents/${id}/reprocess`, opts),
    reviewClaim: (documentId: number, claimId: number, action: string, editedText?: string, opts?: RequestOptions) =>
      request<ClaimOut>("POST", `/documents/${documentId}/claims/${claimId}/review`, { body: { action, edited_text: editedText }, ...opts }),
    remove: (id: number, opts?: RequestOptions) => request<{ deleted: boolean }>("DELETE", `/documents/${id}`, opts),
    downloadUrl: (id: number) => `${config.apiBaseUrl}/documents/${id}/download`,
  },

  stories: {
    list: (opts?: RequestOptions) => request<{ stories: StoryOut[] }>("GET", "/stories", opts),
    get: (id: number, opts?: RequestOptions) => request<StoryOut>("GET", `/stories/${id}`, opts),
    create: (body: Partial<StoryOut> & { title: string; status?: string; claim_ids?: number[] }, opts?: RequestOptions) =>
      request<StoryOut>("POST", "/stories", { body, ...opts }),
    draft: (title: string, claimIds: number[], opts?: RequestOptions) =>
      request<StoryOut>("POST", "/stories/draft", { body: { title, claim_ids: claimIds }, ...opts }),
    update: (id: number, body: Partial<StoryOut>, opts?: RequestOptions) =>
      request<StoryOut>("PATCH", `/stories/${id}`, { body, ...opts }),
    remove: (id: number, opts?: RequestOptions) => request<{ deleted: boolean }>("DELETE", `/stories/${id}`, opts),
  },

  reports: {
    exportJsonUrl: (reportId: number) => `${config.apiBaseUrl}/reports/${reportId}/export.json`,
    exportMarkdownUrl: (reportId: number) => `${config.apiBaseUrl}/reports/${reportId}/export.md`,
  },

  // Candidate feedback (P5). Never modifies Agent behaviour — a human-reviewed signal.
  feedback: {
    submit: (body: FeedbackCreateRequest, opts?: RequestOptions) =>
      request<FeedbackResponse>("POST", "/feedback", { body, ...opts }),
    get: (surface: FeedbackSurface, targetId: string, opts?: RequestOptions) =>
      request<FeedbackResponse | null>(
        "GET",
        `/feedback?surface=${encodeURIComponent(surface)}&target_id=${encodeURIComponent(targetId)}`,
        opts,
      ),
    remove: (surface: FeedbackSurface, targetId: string, opts?: RequestOptions) =>
      request<{ deleted: boolean }>(
        "DELETE",
        `/feedback?surface=${encodeURIComponent(surface)}&target_id=${encodeURIComponent(targetId)}`,
        opts,
      ),
  },

  // Teams / Workspaces & explicit sharing (Capstone P6.5). Private-by-default: nothing
  // is shared unless the owner explicitly creates a VIEW share grant.
  workspaces: {
    list: (opts?: RequestOptions) => request<MyWorkspaces>("GET", "/workspaces", opts),
    create: (name: string, opts?: RequestOptions) =>
      request<WorkspaceSummary>("POST", "/workspaces", { body: { name }, ...opts }),
    get: (id: number, opts?: RequestOptions) => request<WorkspaceDetail>("GET", `/workspaces/${id}`, opts),
    invite: (id: number, email: string, role = "workspace_member", opts?: RequestOptions) =>
      request<{ invitation_id: number; status: string }>("POST", `/workspaces/${id}/invite`, { body: { email, role }, ...opts }),
    accept: (token: string, opts?: RequestOptions) =>
      request<WorkspaceSummary>("POST", "/workspaces/invitations/accept", { body: { token }, ...opts }),
    decline: (token: string, opts?: RequestOptions) =>
      request<{ status: string }>("POST", "/workspaces/invitations/decline", { body: { token }, ...opts }),
    leave: (id: number, opts?: RequestOptions) =>
      request<{ status: string }>("POST", `/workspaces/${id}/leave`, opts),
    removeMember: (id: number, targetUserId: number, opts?: RequestOptions) =>
      request<{ status: string }>("POST", `/workspaces/${id}/members/${targetUserId}/remove`, opts),
    transfer: (id: number, newOwnerUserId: number, opts?: RequestOptions) =>
      request<WorkspaceSummary>("POST", `/workspaces/${id}/transfer`, { body: { new_owner_user_id: newOwnerUserId }, ...opts }),
    deactivate: (id: number, opts?: RequestOptions) =>
      request<WorkspaceSummary>("POST", `/workspaces/${id}/deactivate`, opts),
  },

  shares: {
    mine: (opts?: RequestOptions) => request<{ shares: ShareGrantOut[] }>("GET", "/shares/mine", opts),
    withMe: (opts?: RequestOptions) => request<{ shares: ShareGrantOut[] }>("GET", "/shares/with-me", opts),
    create: (workspaceId: number, resourceType: string, resourceId: string, opts?: RequestOptions) =>
      request<{ share_id: number; status: string }>("POST", "/shares", { body: { workspace_id: workspaceId, resource_type: resourceType, resource_id: resourceId }, ...opts }),
    revoke: (shareId: number, opts?: RequestOptions) =>
      request<{ status: string }>("DELETE", `/shares/${shareId}`, opts),
  },

  // Realtime voice (Capstone P7.5, C1). Mints a short-lived, user-scoped session
  // credential; the browser streams audio directly to the provider. Never returns a
  // long-lived key. A 503 means "unavailable" → the UI falls back to turn-based voice.
  voice: {
    realtimeStatus: (opts?: RequestOptions) =>
      request<RealtimeStatusResponse>("GET", "/voice/realtime/status", opts),
    realtimeSession: (body: RealtimeSessionRequest, opts?: RequestOptions) =>
      request<RealtimeSessionResponse>("POST", "/voice/realtime/session", { body, ...opts }),
    endRealtimeSession: (opts?: RequestOptions) =>
      request<{ status: string }>("POST", "/voice/realtime/session/end", opts),
  },

  // Customer support (P10B-W10.3): owner-scoped candidate endpoints.
  support: {
    create: (body: SupportCreateRequest, opts?: RequestOptions) =>
      request<SupportTicketSummary>("POST", "/support/tickets", { body, ...opts }),
    list: (page = 1, opts?: RequestOptions) =>
      request<SupportTicketList>("GET", `/support/tickets?page=${page}&page_size=20`, opts),
    get: (publicId: string, opts?: RequestOptions) =>
      request<SupportTicketDetail>("GET", `/support/tickets/${encodeURIComponent(publicId)}`, opts),
    reply: (publicId: string, message: string, opts?: RequestOptions) =>
      request<SupportTicketDetail>("POST", `/support/tickets/${encodeURIComponent(publicId)}/messages`, { body: { message }, ...opts }),
  },

  // W10.10 candidate privacy requests and legal-version truth (owner-scoped).
  privacy: {
    createRequest: (body: { request_type: string; note?: string }, opts?: RequestOptions) =>
      request<PrivacyRequestView>("POST", "/privacy/requests", { body, ...opts }),
    requests: (opts?: RequestOptions) => request<PrivacyRequestList>("GET", "/privacy/requests?page=1&page_size=20", opts),
    legal: (opts?: RequestOptions) => request<LegalStatus>("GET", "/privacy/legal", opts),
    acceptLegal: (code: string, opts?: RequestOptions) =>
      request<LegalStatus>("POST", `/privacy/legal/${encodeURIComponent(code)}/accept`, opts),
  },

  // Platform Admin operations (Capstone P6.5). PLATFORM_ADMIN only; metadata only.
  admin: {
    home: (opts?: RequestOptions) => request<AdminCommandCenter>("GET", "/admin/home", opts),
    users: (query: AdminUserQuery = {}, opts?: RequestOptions) =>
      request<AdminPage<AdminUserSummary>>("GET", `/admin/users${qs(query as Record<string, unknown>)}`, opts),
    userDetail: (userId: number, opts?: RequestOptions) =>
      request<AdminUserDetail>("GET", `/admin/users/${userId}`, opts),
    setRole: (userId: number, role: string, reason?: string, opts?: RequestOptions) =>
      request<Record<string, unknown>>("POST", `/admin/users/${userId}/role`, { body: { role, reason }, ...opts }),
    setUserPlan: (userId: number, planCode: string, opts?: RequestOptions) =>
      request<Record<string, unknown>>("POST", `/admin/users/${userId}/plan`, { body: { plan_code: planCode }, ...opts }),
    setWorkspacePlan: (workspaceId: number, planCode: string, opts?: RequestOptions) =>
      request<Record<string, unknown>>("POST", `/admin/workspaces/${workspaceId}/plan`, { body: { plan_code: planCode }, ...opts }),
    integrations: (opts?: RequestOptions) => request<{ items: IntegrationRow[] }>("GET", "/admin/integrations", opts),
    integration: (code: string, opts?: RequestOptions) =>
      request<IntegrationDetail>("GET", `/admin/integrations/${encodeURIComponent(code)}`, opts),
    testIntegration: (code: string, opts?: RequestOptions) =>
      request<IntegrationTestResult>("POST", `/admin/integrations/${encodeURIComponent(code)}/test`, opts),
    /** WRITE-ONLY: the response never contains the value. Only offered when the credential store is writable. */
    replaceCredential: (code: string, slot: string, value: string, opts?: RequestOptions) =>
      request<{ integration: string; slot: string; configured: boolean }>(
        "POST", `/admin/integrations/${encodeURIComponent(code)}/credentials/${encodeURIComponent(slot)}`, { body: { value }, ...opts }),
    plans: (opts?: RequestOptions) => request<{ items: PlanVersionRow[] }>("GET", "/admin/plans", opts),
    plan: (versionId: number, opts?: RequestOptions) => request<PlanDetail>("GET", `/admin/plans/${versionId}`, opts),
    assignablePlans: (opts?: RequestOptions) => request<AssignablePlan[]>("GET", "/admin/plans/assignable", opts),
    createPlanDraft: (planCode: string, opts?: RequestOptions) =>
      request<{ id: number; plan_code: string; version: number }>("POST", `/admin/plans/${encodeURIComponent(planCode)}/versions`, opts),
    updatePlanDraft: (versionId: number, entitlements: Record<string, { enabled: boolean; limit?: number | null }>, opts?: RequestOptions) =>
      request<Record<string, unknown>>("PATCH", `/admin/plans/versions/${versionId}/entitlements`, { body: { entitlements }, ...opts }),
    activatePlan: (versionId: number, opts?: RequestOptions) =>
      request<Record<string, unknown>>("POST", `/admin/plans/versions/${versionId}/activate`, opts),
    retirePlan: (versionId: number, opts?: RequestOptions) =>
      request<Record<string, unknown>>("POST", `/admin/plans/versions/${versionId}/retire`, opts),
    setStatus: (userId: number, status: string, reason?: string, opts?: RequestOptions) =>
      request<Record<string, unknown>>("POST", `/admin/users/${userId}/status`, { body: { status, reason }, ...opts }),
    revokeSessions: (userId: number, reason?: string, opts?: RequestOptions) =>
      request<{ user_id: number; sessions_revoked: number }>("POST", `/admin/users/${userId}/sessions/revoke`, { body: { reason }, ...opts }),
    workspaces: (query: { q?: string; status?: string; page?: number; page_size?: number } = {}, opts?: RequestOptions) =>
      request<AdminPage<AdminWorkspaceSummary>>("GET", `/admin/workspaces${qs(query)}`, opts),
    workspaceDetail: (id: number, opts?: RequestOptions) =>
      request<AdminWorkspaceDetail>("GET", `/admin/workspaces/${id}`, opts),
    addWorkspaceMember: (id: number, userId: number, role: string, opts?: RequestOptions) =>
      request<Record<string, unknown>>("POST", `/admin/workspaces/${id}/members`, { body: { user_id: userId, role }, ...opts }),
    removeWorkspaceMember: (id: number, userId: number, opts?: RequestOptions) =>
      request<Record<string, unknown>>("DELETE", `/admin/workspaces/${id}/members/${userId}`, opts),
    setWorkspaceMemberRole: (id: number, userId: number, role: string, opts?: RequestOptions) =>
      request<Record<string, unknown>>("POST", `/admin/workspaces/${id}/members/${userId}/role`, { body: { role }, ...opts }),
    // W10.10 privacy and legal
    privacyQueue: (query: PrivacyQuery = {}, opts?: RequestOptions) =>
      request<AdminPage<PrivacyRequestRow>>("GET", `/admin/privacy/requests${qs(query as Record<string, unknown>)}`, opts),
    privacyRequest: (id: string, opts?: RequestOptions) =>
      request<PrivacyRequestDetail>("GET", `/admin/privacy/requests/${encodeURIComponent(id)}`, opts),
    privacyRecord: (account: string, requestType: string, note: string, opts?: RequestOptions) =>
      request<PrivacyRequestDetail>("POST", "/admin/privacy/requests", { body: { account, request_type: requestType, note: note || null }, ...opts }),
    privacyAssign: (id: string, assigneeUserId: number | null, opts?: RequestOptions) =>
      request<PrivacyRequestDetail>("POST", `/admin/privacy/requests/${encodeURIComponent(id)}/assign`, { body: { assignee_user_id: assigneeUserId }, ...opts }),
    privacyStatus: (id: string, status: string, resultCategory?: string, opts?: RequestOptions) =>
      request<PrivacyRequestDetail>("POST", `/admin/privacy/requests/${encodeURIComponent(id)}/status`, { body: { status, result_category: resultCategory ?? null }, ...opts }),
    privacyExecuteDeletion: (id: string, opts?: RequestOptions) =>
      request<PrivacyRequestDetail>("POST", `/admin/privacy/requests/${encodeURIComponent(id)}/execute-deletion`, opts),
    preparationCoverage: (opts?: RequestOptions) => request<PreparationCoverage>("GET", "/admin/privacy/preparation", opts),
    preparationBackfill: (opts?: RequestOptions) => request<{ job_id: string; created: boolean }>("POST", "/admin/privacy/preparation/backfill", opts),
    legalOverview: (opts?: RequestOptions) => request<LegalOverview>("GET", "/admin/legal", opts),
    legalCreateDraft: (code: string, body: { version: string; content_ref: string; content_hash: string; effective_at: string }, opts?: RequestOptions) =>
      request<LegalVersionRow>("POST", `/admin/legal/${encodeURIComponent(code)}/versions`, { body: { ...body, content_hash: body.content_hash || null, effective_at: body.effective_at || null }, ...opts }),
    legalPublish: (versionId: number, opts?: RequestOptions) => request<LegalVersionRow>("POST", `/admin/legal/versions/${versionId}/publish`, opts),
    feedback: (opts?: RequestOptions) => request<Record<string, unknown>>("GET", "/admin/feedback", opts),
    providers: (opts?: RequestOptions) => request<AdminProviders>("GET", "/admin/providers", opts),
    audit: (opts?: RequestOptions) => request<{ events: AdminAuditEvent[] }>("GET", "/admin/audit", opts),
    // W10.8 knowledge
    knowledgeMeta: (opts?: RequestOptions) => request<KnowledgeMeta>("GET", "/admin/knowledge/meta", opts),
    knowledgeSources: (query: KnowledgeQuery = {}, opts?: RequestOptions) =>
      request<AdminPage<KnowledgeRow>>("GET", `/admin/knowledge/sources${qs(query as Record<string, unknown>)}`, opts),
    knowledgeSource: (id: string, opts?: RequestOptions) =>
      request<KnowledgeSourceDetail>("GET", `/admin/knowledge/sources/${encodeURIComponent(id)}`, opts),
    knowledgeVersion: (id: string, opts?: RequestOptions) =>
      request<KnowledgeVersionDetail>("GET", `/admin/knowledge/versions/${encodeURIComponent(id)}`, opts),
    createKnowledgeSource: (form: FormData) => upload<{ source_public_id: string; version_public_id: string; version: number }>("/admin/knowledge/sources", form),
    addKnowledgeVersion: (sourceId: string, form: FormData) =>
      upload<{ source_public_id: string; version_public_id: string; version: number }>(`/admin/knowledge/sources/${encodeURIComponent(sourceId)}/versions`, form),
    knowledgeAction: (id: string, action: "approve" | "index" | "activate" | "retire" | "reprocess", opts?: RequestOptions) =>
      request<KnowledgeVersionDetail>("POST", `/admin/knowledge/versions/${encodeURIComponent(id)}/${action}`, opts),
    knowledgeReject: (id: string, reason: string, opts?: RequestOptions) =>
      request<KnowledgeVersionDetail>("POST", `/admin/knowledge/versions/${encodeURIComponent(id)}/reject`, { body: { reason }, ...opts }),
    knowledgeDelete: (id: string, opts?: RequestOptions) =>
      request<{ deleted: string }>("DELETE", `/admin/knowledge/versions/${encodeURIComponent(id)}`, opts),
    // W10.9 jobs
    jobs: (query: JobQuery = {}, opts?: RequestOptions) =>
      request<AdminPage<JobRow>>("GET", `/admin/jobs${qs(query as Record<string, unknown>)}`, opts),
    job: (id: string, opts?: RequestOptions) => request<JobDetail>("GET", `/admin/jobs/${encodeURIComponent(id)}`, opts),
    jobDiagnostics: (opts?: RequestOptions) => request<JobDiagnostics>("GET", "/admin/jobs/diagnostics", opts),
    jobTypes: (opts?: RequestOptions) => request<JobTypeInfo[]>("GET", "/admin/jobs/types", opts),
    enqueueJob: (jobType: string, payload: Record<string, string>, opts?: RequestOptions) =>
      request<{ job: JobRow; created: boolean }>("POST", "/admin/jobs", { body: { job_type: jobType, payload }, ...opts }),
    retryJob: (id: string, opts?: RequestOptions) => request<JobRow>("POST", `/admin/jobs/${encodeURIComponent(id)}/retry`, opts),
    cancelJob: (id: string, opts?: RequestOptions) => request<JobRow>("POST", `/admin/jobs/${encodeURIComponent(id)}/cancel`, opts),
    // W10.3 support
    supportTickets: (query: AdminTicketQuery = {}, opts?: RequestOptions) =>
      request<AdminPage<AdminTicketSummary>>("GET", `/admin/support/tickets${qs(query as Record<string, unknown>)}`, opts),
    supportTicket: (ref: string, opts?: RequestOptions) =>
      request<AdminTicketDetail>("GET", `/admin/support/tickets/${encodeURIComponent(ref)}`, opts),
    supportAssignees: (opts?: RequestOptions) => request<AdminAssignee[]>("GET", "/admin/support/assignees", opts),
    supportAssign: (ref: string, assigneeUserId: number | null, opts?: RequestOptions) =>
      request<Record<string, unknown>>("POST", `/admin/support/tickets/${encodeURIComponent(ref)}/assign`, { body: { assignee_user_id: assigneeUserId }, ...opts }),
    supportStatus: (ref: string, status: string, opts?: RequestOptions) =>
      request<Record<string, unknown>>("POST", `/admin/support/tickets/${encodeURIComponent(ref)}/status`, { body: { status }, ...opts }),
    supportPriority: (ref: string, priority: string, opts?: RequestOptions) =>
      request<Record<string, unknown>>("POST", `/admin/support/tickets/${encodeURIComponent(ref)}/priority`, { body: { priority }, ...opts }),
    supportReply: (ref: string, body: string, opts?: RequestOptions) =>
      request<Record<string, unknown>>("POST", `/admin/support/tickets/${encodeURIComponent(ref)}/reply`, { body: { body }, ...opts }),
    supportNote: (ref: string, body: string, opts?: RequestOptions) =>
      request<Record<string, unknown>>("POST", `/admin/support/tickets/${encodeURIComponent(ref)}/notes`, { body: { body }, ...opts }),
  },
};

export { ApiError };
