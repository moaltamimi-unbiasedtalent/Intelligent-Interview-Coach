"""Agent tool registry — a strict allowlist.

The model may only request registered tools; unknown names are rejected (never
executed). There is NO dynamic import, eval, or arbitrary function resolution.
Arguments are Pydantic-validated before the handler runs. Handlers receive a
:class:`ToolContext` (prior state) and return a :class:`ToolOutcome`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from src.agent.errors import TOOL_FAILURE_INVALID_ARGUMENTS, AgentToolError
from src.agent.tool_authorization import (
    AuthorizationDecision,
    RunAuthContext,
    ToolAuthorizationDenied,
    ToolAuthorizer,
    ToolPolicy,
    schema_fingerprint,
)
from src.agent.tooling import ToolContext, ToolOutcome
from src.agent.tools import build_career_tools, build_human_action_tools

Handler = Callable[[BaseModel, ToolContext], ToolOutcome]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    args_model: type[BaseModel]
    handler: Handler
    # SHA-256 of the argument JSON schema at registration (01D): a schema that changes afterwards is refused.
    schema_sha: str | None = None


class ToolRegistry:
    def __init__(self, authorizer: ToolAuthorizer | None = None) -> None:
        self._tools: dict[str, ToolSpec] = {}
        # Every registry has an authorizer (default-deny: a tool without a declared policy never runs).
        self.authorizer = authorizer or ToolAuthorizer()

    def register(self, args_model: type[BaseModel], handler: Handler, policy: ToolPolicy | None = None) -> None:
        name = args_model.__name__
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered.")
        if policy is not None:
            if policy.name != name:
                raise ValueError(f"Policy '{policy.name}' does not match tool '{name}'.")
            self.authorizer.add_policy(policy)
        self._tools[name] = ToolSpec(name=name, args_model=args_model, handler=handler,
                                     schema_sha=schema_fingerprint(args_model))

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return list(self._tools)

    def bind_schemas(self, exclude: set[str] | None = None) -> list[type[BaseModel]]:
        """Pydantic schemas for ``model.bind_tools`` (name == class name).

        ``exclude`` drops named tools from what the model can see — used to enforce a
        per-run capability toggle server-side (a disabled tool is never offered).
        """
        ex = exclude or set()
        return [spec.args_model for name, spec in self._tools.items() if name not in ex]

    def authorize(
        self, name: str, raw_args: Any, ctx: ToolContext, run: RunAuthContext | None = None
    ) -> AuthorizationDecision:
        """The server-side decision for one model-requested call (01D). Audited by the authorizer.

        ``run`` is built by the graph node from the trusted run state; a direct caller without one is
        authorized against the identity in ``ctx`` only (no goal, no history), which still refuses every
        tool that needs a goal or an owner.
        """
        spec = self._tools.get(name) if isinstance(name, str) else None
        run = run or RunAuthContext(user_id=ctx.user_id)
        return self.authorizer.decide(name, raw_args, run, spec)

    def validate_and_run(
        self, name: str, raw_args: dict[str, Any] | None, ctx: ToolContext, *,
        decision: AuthorizationDecision | None = None, run: RunAuthContext | None = None,
    ) -> ToolOutcome:
        """Authorize, validate arguments, then execute. This is the ONLY path to a handler.

        A handler is reached only with an ALLOW decision bound to this exact tool and arguments; a refusal
        raises :class:`ToolAuthorizationDenied` (no side effect). Raises AgentToolError for an unknown tool
        or invalid arguments — never executes an unknown name.
        """
        if decision is None:
            decision = self.authorize(name, raw_args, ctx, run)
        if not decision.allowed:
            raise ToolAuthorizationDenied(decision)
        if not decision.matches(name, raw_args):
            # A decision for a different call must never authorise this one.
            from dataclasses import replace

            from src.agent.tool_authorization import Reason

            raise ToolAuthorizationDenied(replace(decision, allowed=False, reason=Reason.DECISION_MISMATCH))
        spec = self._tools.get(name)
        if spec is None:
            raise AgentToolError(f"Tool '{name}' is not available.")
        try:
            args = spec.args_model(**(raw_args or {}))
        except ValidationError as exc:
            raise AgentToolError(f"Invalid arguments for tool '{name}'.",
                                 category=TOOL_FAILURE_INVALID_ARGUMENTS) from exc
        return spec.handler(args, ctx)


def career_tool_registry(career_service: Any, *, evidence_service: Any = None,
                         coaching_reasoner: Any = None,
                         authorizer: ToolAuthorizer | None = None) -> ToolRegistry:
    """The allowlist. Six real Career tools (job analysis, gap analysis, preparation
    plan, question generation, career-knowledge retrieval, current-market research) PLUS
    three bounded P5 specialist tools (AnalyzeRoleOpportunity, FindCandidateEvidence,
    BuildCoachingStrategy) behind Mo, PLUS two Phase 8 human-action tools
    (ProposePreparationMemory, RequestPracticeHandoff). The specialist and human-action
    tools are separate from the Career evidence tools: specialists are bounded,
    side-effect-free advisors; human-action tools propose a decision for approval and
    never persist or start anything themselves. Low-level stores (vector/BM25/
    repositories) are NEVER registered — the deterministic router owns lane selection
    inside SearchCareerKnowledge, and the owner-scoped Candidate Evidence specialist is
    the ONLY path to private approved evidence (via the trusted run-state user id)."""
    from src.agent.specialist_tools import build_specialist_tools

    from src.agent.tool_authorization import DEFAULT_POLICIES

    registry = ToolRegistry(authorizer=authorizer)
    for builder in (
        lambda: build_career_tools(career_service),
        lambda: build_specialist_tools(
            career_service, evidence_service=evidence_service, coaching_reasoner=coaching_reasoner),
        lambda: build_human_action_tools(career_service),
    ):
        for args_model, handler in builder():
            registry.register(args_model, handler, DEFAULT_POLICIES.get(args_model.__name__))
    return registry
