/**
 * TypeScript contracts mirrored from the FastAPI OpenAPI schema (/api/v1).
 *
 * Decision (§33): OpenAPI codegen was evaluated and deferred for Phase 3B — the
 * surface consumed now is tiny (health + capabilities), so a handful of hand-typed
 * contracts is clearer than adding a codegen build step. When Phase 3C consumes the
 * larger career/interview surface, revisit `openapi-typescript` to generate these
 * from src/api at build time. These types intentionally contain only fields the
 * backend actually returns.
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
}

/** The stable error envelope: { error: { code, message, request_id } }. */
export interface ApiErrorBody {
  code: string;
  message: string;
  request_id?: string | null;
}

export interface ApiErrorEnvelope {
  error: ApiErrorBody;
}
