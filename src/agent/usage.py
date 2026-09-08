"""Safe agent usage accounting (post-Sprint 4, P1 — MEASURE FIRST).

One canonical, privacy-safe aggregate of provider usage for a single Agent run:
how many model calls happened (outer LangGraph agent + model-backed Career tools),
how many tokens they used, and an estimated cost WHERE the numbers are genuinely
known. Two honesty rules run through everything here:

* **Unknown is not zero.** If any counted model call did not report usage, the run
  is marked ``usage_complete = False`` and the source is listed in
  ``missing_usage_sources`` — we never silently turn missing usage into 0 tokens or
  $0.00.
* **Count each provider call exactly once.** Outer agent calls and tool-internal
  calls are captured on separate, non-overlapping seams, so one real provider call
  appears once (agent JD + question generation + agent turn ⇒ 3, never 5–6).

No raw provider payloads, prompts, reasoning or candidate text ever reach this
module — only token counts, model-call counts, a model slug and (if the provider
reports it) a cost. Capture is done at the AGENT boundary (the outer agent node and
the agent tool handlers), so the Sprint-3 Career internals are untouched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

__all__ = [
    "MODEL_BACKED_TOOLS",
    "AgentRunUsage",
    "usage_from_message",
    "capture_tool_usage",
    "aggregate_usage",
]

# Career tools that ALWAYS make exactly one provider model call when they run.
# Deterministic tools (gap analysis, preparation plan) and the retrieval router are
# NOT here — they must never produce a fabricated usage record. Retrieval's own
# internal usage (if any) is captured opportunistically, not counted as a fixed call.
MODEL_BACKED_TOOLS = frozenset({"AnalyzeJobDescription", "GenerateInterviewQuestions"})

# A cost resolver maps (model_slug, input_tokens, output_tokens) -> USD or None. It is
# optional and defaults to absent so the runtime makes NO pricing network call; when a
# deployment wires reliable pricing (the existing PricingService) it can be supplied.
CostResolver = Callable[[str | None, int, int], float | None]


@dataclass
class AgentRunUsage:
    """Canonical, safe usage aggregate for one Agent run (see module docstring)."""

    agent_model_calls: int = 0
    tool_model_calls: int = 0
    model_calls: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    usage_complete: bool = True
    missing_usage_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_model_calls": self.agent_model_calls,
            "tool_model_calls": self.tool_model_calls,
            "model_calls": self.model_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "usage_complete": self.usage_complete,
            "missing_usage_sources": list(self.missing_usage_sources),
        }


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _extract_reported_cost(message: Any) -> float | None:
    """Best-effort reported cost from a provider message (never invented).

    OpenRouter, when asked, reports a per-request ``cost`` in the response metadata.
    We read it only if it is genuinely present and non-negative; otherwise None.
    """
    meta = getattr(message, "response_metadata", None) or {}
    for key in ("cost", "total_cost"):
        raw = meta.get(key)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw >= 0:
            return float(raw)
    usage = meta.get("token_usage") or meta.get("usage") or {}
    if isinstance(usage, dict):
        raw = usage.get("cost")
        if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw >= 0:
            return float(raw)
    return None


def _model_slug(message: Any) -> str | None:
    meta = getattr(message, "response_metadata", None) or {}
    slug = meta.get("model_name") or meta.get("model")
    return str(slug) if slug else None


def usage_from_message(message: Any, *, source: str = "agent") -> dict[str, Any]:
    """Build a safe usage entry for ONE outer agent model call from its AIMessage.

    ``usage_metadata`` is LangChain's normalised token record; when it is absent the
    entry is still counted as a model call but flagged ``has_usage=False`` (unknown,
    never zero).
    """
    um = getattr(message, "usage_metadata", None) or {}
    input_tokens = _int_or_none(um.get("input_tokens"))
    output_tokens = _int_or_none(um.get("output_tokens"))
    total_tokens = _int_or_none(um.get("total_tokens"))
    if total_tokens is None and (input_tokens is not None or output_tokens is not None):
        total_tokens = (input_tokens or 0) + (output_tokens or 0)
    has_usage = total_tokens is not None
    return {
        "source": source,
        "kind": "agent",
        "model_calls": 1,
        "model": _model_slug(message),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "reported_cost_usd": _extract_reported_cost(message),
        "has_usage": has_usage,
    }


def _sum_callback(callback: Any) -> tuple[int | None, int | None, int | None, int, str | None]:
    """Sum token usage the LangChain usage callback accumulated across model calls.

    Returns ``(input, output, total, model_count, sample_model_slug)``. When the
    callback saw nothing, model_count is 0 and the token sums are None.
    """
    data = getattr(callback, "usage_metadata", None) or {}
    if not data:
        return None, None, None, 0, None
    input_sum = output_sum = total_sum = 0
    sample_slug: str | None = None
    for slug, um in data.items():
        sample_slug = sample_slug or (str(slug) if slug else None)
        input_sum += _int_or_none((um or {}).get("input_tokens")) or 0
        output_sum += _int_or_none((um or {}).get("output_tokens")) or 0
        total_sum += _int_or_none((um or {}).get("total_tokens")) or 0
    return input_sum, output_sum, total_sum, len(data), sample_slug


def capture_tool_usage(
    tool_name: str, fn: Callable[[], Any]
) -> tuple[Any, dict[str, Any] | None]:
    """Run ``fn`` (a Career tool's model-backed call) and capture its provider usage.

    Uses LangChain's usage-metadata callback, whose context variable auto-attaches to
    any nested model invocation — including a ``with_structured_output`` call inside a
    Career tool — so we capture tool-internal usage WITHOUT changing any Sprint-3
    return contract. Returns ``(result, usage_entry_or_None)``.

    * For a declared model-backed tool: always returns an entry (one model call), with
      tokens if the callback reported them, else ``has_usage=False`` (unknown, not 0).
    * For any other tool: returns an entry ONLY if the callback actually observed a
      model call (e.g. retrieval-time query translation) — a purely deterministic tool
      contributes no usage record.
    """
    from langchain_core.callbacks import get_usage_metadata_callback

    with get_usage_metadata_callback() as cb:
        result = fn()
    inp, out, tot, seen, slug = _sum_callback(cb)
    model_backed = tool_name in MODEL_BACKED_TOOLS
    if not model_backed and seen == 0:
        return result, None
    model_calls = max(1, seen) if model_backed else seen
    entry = {
        "source": f"tool:{tool_name}",
        "kind": "tool",
        "model_calls": model_calls,
        "model": slug,
        "input_tokens": inp,
        "output_tokens": out,
        "total_tokens": tot,
        "reported_cost_usd": None,  # tool-internal reported cost is not surfaced here
        "has_usage": tot is not None and seen > 0,
    }
    return result, entry


def _sum_known(values: list[int | None]) -> int | None:
    known = [v for v in values if isinstance(v, int)]
    return sum(known) if known else None


def aggregate_usage(
    entries: list[dict[str, Any]] | None, *, cost_resolver: CostResolver | None = None
) -> AgentRunUsage:
    """Aggregate per-call usage entries into one truthful :class:`AgentRunUsage`.

    ``entries`` are the safe dicts produced by :func:`usage_from_message` (outer agent
    calls) and :func:`capture_tool_usage` (tool-internal calls). Counts are exact;
    tokens are summed only where genuinely known; ``usage_complete`` is True only when
    every counted call reported usage. Cost is reported-cost where the provider gave
    it, else computed via ``cost_resolver`` where available, else None — never invented.
    """
    entries = list(entries or [])
    agent_calls = sum(e.get("model_calls", 0) for e in entries if e.get("kind") == "agent")
    tool_calls = sum(e.get("model_calls", 0) for e in entries if e.get("kind") == "tool")

    input_tokens = _sum_known([e.get("input_tokens") for e in entries if e.get("has_usage")])
    output_tokens = _sum_known([e.get("output_tokens") for e in entries if e.get("has_usage")])
    total_tokens = _sum_known([e.get("total_tokens") for e in entries if e.get("has_usage")])

    missing = [e.get("source", "unknown") for e in entries if not e.get("has_usage")]
    usage_complete = bool(entries) and not missing

    # Cost: sum reported costs; fill gaps with a resolver ONLY where tokens are known.
    # If any counted model call has neither a reported nor a resolvable cost, we return
    # None rather than a misleadingly precise partial figure (see §38, no false precision).
    cost_known = True
    cost_total = 0.0
    for e in entries:
        reported = e.get("reported_cost_usd")
        if isinstance(reported, (int, float)) and not isinstance(reported, bool):
            cost_total += float(reported)
            continue
        if (
            cost_resolver is not None
            and e.get("has_usage")
            and e.get("input_tokens") is not None
            and e.get("output_tokens") is not None
        ):
            resolved = cost_resolver(e.get("model"), int(e["input_tokens"]), int(e["output_tokens"]))
            if resolved is not None:
                cost_total += float(resolved)
                continue
        cost_known = False
    estimated_cost = round(cost_total, 10) if (entries and cost_known) else None

    return AgentRunUsage(
        agent_model_calls=agent_calls,
        tool_model_calls=tool_calls,
        model_calls=agent_calls + tool_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost,
        usage_complete=usage_complete,
        missing_usage_sources=missing,
    )
