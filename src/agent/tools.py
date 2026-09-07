"""Foundation agent tool(s).

Phase 4 registers the MINIMUM needed to prove orchestration — one deterministic
tool that reuses an existing capability (target-role resolution). No provider call,
no secrets, no fabricated user-facing capability. The real Career tools are migrated
in Phase 5.

Each tool's argument schema is a Pydantic model whose CLASS NAME is the tool name
the model calls (so bind_tools and the registry stay in sync).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResolvePreparationGoal(BaseModel):
    """Restate the candidate's preparation goal and resolve the target role
    deterministically. Use this to confirm what the candidate is preparing for."""

    goal: str = Field(description="The candidate's preparation goal or question.", max_length=4000)
    target_role: str | None = Field(default=None, description="A role the candidate named, if any.", max_length=200)


def resolve_preparation_goal(args: ResolvePreparationGoal) -> dict:
    """Deterministic handler — no provider call. Returns a safe structured result."""
    from src.integration.preparation_context import resolve_target_role

    resolved = resolve_target_role(user_confirmed_role=args.target_role) or ""
    return {
        "resolved_target_role": resolved,
        "goal": args.goal.strip()[:500],
        "note": (
            "Target role resolved deterministically from the candidate's input."
            if resolved
            else "No target role could be resolved yet — ask the candidate to name the role."
        ),
    }
