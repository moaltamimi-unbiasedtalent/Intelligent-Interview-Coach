"""Contract guard: the OpenAPI schema fields the Next.js frontend depends on.

The frontend hand-writes its TypeScript contracts (OpenAPI codegen was deferred in
Phase 3B/3C). This test pins the field names the frontend consumes, so a backend
rename breaks a test here instead of silently breaking the UI. Update this list and
`frontend/lib/api/types.ts` together when a contract intentionally changes.
"""

from __future__ import annotations

from src.api.main import create_app


def _schemas() -> dict:
    return create_app().openapi()["components"]["schemas"]


# Field names the frontend relies on, per component schema.
EXPECTED = {
    "HealthResponse": {"status", "service", "version"},
    "CapabilitiesResponse": {
        "career_intelligence", "interview_practice", "knowledge_base", "evaluation",
        "live_interview_enabled", "agentic_rag", "agent_memory", "human_in_the_loop",
        "agent_coach_enabled",
    },
    "CareerChatRequest": {
        "question", "job_description", "candidate_background",
        "days_until_interview", "hours_per_week",
    },
    "CareerChatResponse": {
        "answer", "citations", "sources", "tools",
        "input_flagged", "has_evidence", "preparation_available",
    },
    "JobAnalysisRequest": {"job_description"},
    "GapAnalysisRequest": {"candidate_background", "role_requirements"},
    "PreparationPlanRequest": {"priority_gaps", "days_until_interview", "hours_per_week"},
    "QuestionsRequest": {"role", "requirements", "focus"},
    "ToolResultResponse": {"ok", "tool_name", "status", "result", "error"},
    "PreparationContextIn": {
        "target_role", "industry", "company_context", "job_description", "seniority",
        "required_skills", "key_responsibilities", "leadership_expectations",
        "candidate_strengths", "candidate_gaps", "likely_interview_topics",
        "priority_competencies",
    },
    "CreateInterviewRequest": {
        "configuration", "preparation_context", "industry_or_sector", "career_level",
        "interview_types", "interviewer_persona", "difficulty", "response_detail",
        "number_of_questions",
    },
    "InterviewStateResponse": {
        "session_id", "state", "question_number", "questions_planned",
        "current_question", "report_available", "last_evaluation", "target_role",
    },
    "QuestionOut": {"question_id", "question", "question_type", "competency", "difficulty"},
    # Preparation memory (Phase 7) — user-scoped, no internal user id exposed.
    "MemoryCreateRequest": {"category", "summary", "target_role"},
    "MemoryResponse": {
        "id", "category", "summary", "target_role", "source_run_id",
        "created_at", "updated_at",
    },
    "MemoryListResponse": {"memories"},
    "MemoryDeleteResponse": {"deleted", "id"},
    # Agent HITL (Phase 8) — paused runs and typed resume decisions.
    "AgentRunResponse": {
        "run_id", "status", "response", "awaiting_human_input", "pending_action",
        "handoff_approved", "memory_used", "step_count", "turn_step_count",
        "conversation", "sources", "citations", "tools_used", "events",
        # Cost/performance instrumentation (P1) consumed by the Coach + Inspector.
        "usage", "profile", "latency_ms", "cache_hits", "cache_misses",
    },
    "AgentUsageResponse": {
        "agent_model_calls", "tool_model_calls", "model_calls", "input_tokens",
        "output_tokens", "total_tokens", "estimated_cost_usd", "usage_complete",
        "missing_usage_sources",
    },
    # The candidate-selectable Agent tier (validated Literal — never a raw model slug).
    "AgentRunRequest": {"goal", "profile"},
    "PendingActionResponse": {"action_id", "type", "message", "options", "data"},
    "HumanDecisionRequest": {"action_id", "decision", "selected_role"},
    "AgentContinueRequest": {"message"},
    "InterviewOptionsResponse": {"career_levels", "interview_types"},
}


def test_frontend_consumed_fields_exist_in_openapi():
    schemas = _schemas()
    missing: list[str] = []
    for name, fields in EXPECTED.items():
        props = set((schemas.get(name) or {}).get("properties", {}).keys())
        for field in fields:
            if field not in props:
                missing.append(f"{name}.{field}")
    assert not missing, f"OpenAPI/frontend contract drift — missing: {missing}"


def test_required_request_fields_are_marked_required():
    schemas = _schemas()
    # These are the fields the frontend always sends and the backend must require.
    required = {
        "CareerChatRequest": {"question"},
        "JobAnalysisRequest": {"job_description"},
        "GapAnalysisRequest": {"candidate_background", "role_requirements"},
        "PreparationContextIn": {"target_role"},
        "MemoryCreateRequest": {"category", "summary"},
    }
    for name, fields in required.items():
        marked = set((schemas.get(name) or {}).get("required", []))
        assert fields <= marked, f"{name} must require {fields - marked}"
