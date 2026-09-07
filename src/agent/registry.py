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

from src.agent.errors import AgentToolError
from src.agent.tooling import ToolContext, ToolOutcome
from src.agent.tools import build_career_tools

Handler = Callable[[BaseModel, ToolContext], ToolOutcome]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    args_model: type[BaseModel]
    handler: Handler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, args_model: type[BaseModel], handler: Handler) -> None:
        name = args_model.__name__
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered.")
        self._tools[name] = ToolSpec(name=name, args_model=args_model, handler=handler)

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return list(self._tools)

    def bind_schemas(self) -> list[type[BaseModel]]:
        """Pydantic schemas for ``model.bind_tools`` (name == class name)."""
        return [spec.args_model for spec in self._tools.values()]

    def validate_and_run(
        self, name: str, raw_args: dict[str, Any] | None, ctx: ToolContext
    ) -> ToolOutcome:
        """Allowlist + argument validation, then execute. Raises AgentToolError for
        an unknown tool or invalid arguments — never executes an unknown name."""
        spec = self._tools.get(name)
        if spec is None:
            raise AgentToolError(f"Tool '{name}' is not available.")
        try:
            args = spec.args_model(**(raw_args or {}))
        except ValidationError as exc:
            raise AgentToolError(f"Invalid arguments for tool '{name}'.") from exc
        return spec.handler(args, ctx)


def career_tool_registry(career_service: Any) -> ToolRegistry:
    """The Phase 5 allowlist — the four real Career tools (no retrieval tool)."""
    registry = ToolRegistry()
    for args_model, handler in build_career_tools(career_service):
        registry.register(args_model, handler)
    return registry
