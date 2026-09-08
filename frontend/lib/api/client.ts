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
  InterviewQuestionSet,
  InterviewStateResponse,
  JobAnalysisRequest,
  AgentContinueRequest,
  AgentRunRequest,
  AgentRunResponse,
  HumanDecisionRequest,
  InterviewOptionsResponse,
  KnowledgeSnapshotResponse,
  KnowledgeSourcesResponse,
  MemoryCategory,
  MemoryCreateRequest,
  MemoryDeleteResponse,
  MemoryListResponse,
  MemoryResponse,
  PreparationPlan,
  PreparationPlanRequest,
  QuestionsRequest,
  RoleRequirements,
  ToolResultResponse,
} from "./types";

const REQUEST_ID_HEADER = "x-request-id";

interface RequestOptions {
  signal?: AbortSignal;
}

function authHeaders(): Record<string, string> {
  // Transitional local-dev identity only (see lib/config.ts). Omitted when unset.
  return config.devUserSubject ? { "X-User-Subject": config.devUserSubject } : {};
}

async function request<T>(
  method: "GET" | "POST" | "DELETE",
  path: string,
  { body, signal, headers }: { body?: unknown; signal?: AbortSignal; headers?: Record<string, string> } = {},
): Promise<T> {
  const url = `${config.apiBaseUrl}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method,
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
  },

  history: {
    list: (opts?: RequestOptions) =>
      request<InterviewListResponse>("GET", "/history/interviews", opts),
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
  },

  // Long-term preparation memory (Phase 7). Writes are explicit/user-initiated.
  memory: {
    list: (params?: { category?: MemoryCategory }, opts?: RequestOptions) => {
      const query = params?.category ? `?category=${encodeURIComponent(params.category)}` : "";
      return request<MemoryListResponse>("GET", `/memory${query}`, opts);
    },
    create: (body: MemoryCreateRequest, opts?: RequestOptions) =>
      request<MemoryResponse>("POST", "/memory", { body, ...opts }),
    remove: (id: number, opts?: RequestOptions) =>
      request<MemoryDeleteResponse>("DELETE", `/memory/${id}`, opts),
  },
};

export { ApiError };
