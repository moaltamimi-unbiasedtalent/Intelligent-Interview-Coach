"""LangGraph agent foundation for Intelligent Interview Coach (Sprint 4 Phase 4).

A single, stateful, bounded, tool-using agent that runs side-by-side with the
deterministic Career flow (which is unchanged). This package belongs to the
orchestration layer: it may call application/domain services, but imports no
Streamlit, FastAPI routes, or frontend code. Importing it performs no provider
call, retrieval, or evaluation.

See ``docs/sprint4_architecture.md`` for the agent design and the single-agent
decision.
"""
