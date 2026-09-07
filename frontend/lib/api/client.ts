import { config } from "../config";
import { ApiError, apiErrorFromBody } from "./errors";
import type {
  CapabilitiesResponse,
  CareerChatRequest,
  CareerChatResponse,
  CreateInterviewRequest,
  GapAnalysisRequest,
  GapAnalysisResult,
  HealthResponse,
  InterviewListResponse,
  InterviewQuestionSet,
  InterviewStateResponse,
  JobAnalysisRequest,
  KnowledgeSnapshotResponse,
  KnowledgeSourcesResponse,
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
  method: "GET" | "POST",
  path: string,
  { body, signal }: { body?: unknown; signal?: AbortSignal } = {},
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
    create: (body: CreateInterviewRequest, opts?: RequestOptions) =>
      request<InterviewStateResponse>("POST", "/interviews", { body, ...opts }),
    get: (sessionId: string, opts?: RequestOptions) =>
      request<InterviewStateResponse>("GET", `/interviews/${encodeURIComponent(sessionId)}`, opts),
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
};

export { ApiError };
