import { config } from "../config";
import { ApiError, apiErrorFromBody } from "./errors";
import type {
  ActiveSessionsResponse,
  CapabilitiesResponse,
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
  AgentContinueRequest,
  AgentRunDeleteResponse,
  AgentRunRequest,
  AgentRunResponse,
  HumanDecisionRequest,
  InterviewOptionsResponse,
  FeedbackCreateRequest,
  FeedbackResponse,
  FeedbackSurface,
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

interface RequestOptions {
  signal?: AbortSignal;
}

function authHeaders(): Record<string, string> {
  // Transitional local-dev identity only (see lib/config.ts). Sent ONLY in dev, and
  // ignored by the backend in production (where a real session cookie is required).
  // A valid session cookie always takes precedence over this header server-side.
  return config.devUserSubject ? { "X-User-Subject": config.devUserSubject } : {};
}

/** Multipart upload helper (P4): sends FormData with the session cookie; no JSON body. */
async function upload<T>(path: string, form: FormData): Promise<T> {
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
    throw new ApiError({ kind: "network", status: null, code: "network_error", message: "Could not reach the service." });
  }
  const requestId = res.headers.get(REQUEST_ID_HEADER);
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await res.json().catch(() => undefined) : undefined;
  if (!res.ok) throw apiErrorFromBody(res.status, payload, requestId);
  return payload as T;
}

async function request<T>(
  method: "GET" | "POST" | "PATCH" | "DELETE",
  path: string,
  { body, signal, headers }: { body?: unknown; signal?: AbortSignal; headers?: Record<string, string> } = {},
): Promise<T> {
  const url = `${config.apiBaseUrl}${path}`;
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
    throw new ApiError({
      kind: "network",
      status: null,
      code: "network_error",
      message: "Could not reach the service.",
    });
  }

  const requestId = res.headers.get(REQUEST_ID_HEADER);
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await res.json().catch(() => undefined) : undefined;

  if (!res.ok) {
    throw apiErrorFromBody(res.status, payload, requestId);
  }
  return payload as T;
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
    register: (body: RegisterRequest, opts?: RequestOptions) =>
      request<AuthMessageResponse>("POST", "/auth/register", { body, ...opts }),
    login: (body: LoginRequest, opts?: RequestOptions) =>
      request<AuthMessageResponse>("POST", "/auth/login", { body, ...opts }),
    logout: (opts?: RequestOptions) =>
      request<AuthMessageResponse>("POST", "/auth/logout", opts),
    me: (opts?: RequestOptions) => request<AccountResponse>("GET", "/auth/me", opts),
    updatePreferences: (body: PreferencesRequest, opts?: RequestOptions) =>
      request<AccountResponse>("PATCH", "/auth/preferences", { body, ...opts }),
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
    requestDeletion: (opts?: RequestOptions) =>
      request<AuthMessageResponse>("POST", "/auth/account/delete-request", opts),
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
};

export { ApiError };
