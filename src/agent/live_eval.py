"""LIVE MODEL EVALUATION — real-model tool/retrieval/HITL decision benchmark.

This is DISTINCT from ``src/agent/eval.py`` (the deterministic scripted orchestration
regression). Here the REAL configured Agent model chooses actions under realistic
natural-language cases; we classify the observed, safe outcome (which tools ran,
whether retrieval happened, whether a HITL interrupt fired) against per-case
expectations. It is manual/paid and never runs in CI.

The classification + aggregation below are PURE and provider-free, so they are unit
tested with fake observations and re-run offline over recorded traces. Running the
real model (and any cost) lives in ``scripts/eval_agent_live.py``.

Traces are SANITISED: only case id, model profile, safe outcome flags, counts,
latency and (if the provider reports it) token usage — never candidate text,
chain-of-thought, prompts or provider payloads.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CASES_PATH = Path("evaluations/agent_live/cases.json")
TRACES_DIR = Path("evaluations/agent_live/traces")


@dataclass
class Observation:
    """The safe, observable outcome of one live run (no private content)."""

    case_id: str
    model_profile: str
    tools_used: list[str] = field(default_factory=list)
    retrieval_used: bool = False
    awaiting_human_input: bool = False
    pending_action_type: str | None = None
    step_count: int = 0
    status: str = "completed"
    latency_ms: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None

    def to_trace(self) -> dict:
        return asdict(self)

    @classmethod
    def from_trace(cls, d: dict) -> "Observation":
        known = {k: d.get(k) for k in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in known.items() if v is not None or k in ("case_id", "model_profile")})


def load_live_cases(path: Path = CASES_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def classify(case: dict, obs: Observation) -> dict:
    """Classify one observation against a case's expectations (pure/no provider)."""
    required = set(case.get("required_tools", []) or [])
    forbidden = set(case.get("forbidden_tools", []) or [])
    retrieval_expected = bool(case.get("retrieval_expected", False))
    hitl_expected = bool(case.get("hitl_expected", False))
    hitl_type = case.get("hitl_type")
    max_tool_calls = case.get("max_tool_calls")

    used = set(obs.tools_used or [])
    required_ok = required.issubset(used)
    forbidden_used = sorted(used & forbidden)
    within_budget = (max_tool_calls is None) or (len(obs.tools_used or []) <= max_tool_calls)
    # Overall tool selection is correct only if all required ran, none forbidden ran,
    # and the tool-call budget was respected.
    tool_selection_ok = required_ok and not forbidden_used and within_budget

    retrieval_ok = obs.retrieval_used == retrieval_expected
    unnecessary_retrieval = obs.retrieval_used and not retrieval_expected

    hitl_fired = bool(obs.awaiting_human_input)
    hitl_ok = (hitl_fired == hitl_expected) and (
        not hitl_expected or hitl_type is None or obs.pending_action_type == hitl_type)

    completed = obs.status in ("completed", "awaiting_human_input", "step_limit_reached")

    return {
        "case_id": case["id"],
        "tool_selection_ok": tool_selection_ok,
        "required_tool_recall_ok": required_ok,
        "forbidden_tools_used": forbidden_used,
        "within_tool_budget": within_budget,
        "retrieval_ok": retrieval_ok,
        "unnecessary_retrieval": unnecessary_retrieval,
        "hitl_ok": hitl_ok,
        "completed": completed,
        "tool_calls": len(obs.tools_used or []),
        "latency_ms": obs.latency_ms,
        "total_tokens": obs.total_tokens,
        "estimated_cost_usd": obs.estimated_cost_usd,
    }


def _rate(hits: int, total: int) -> float:
    return round(hits / total, 3) if total else 0.0


def _avg(values: list) -> float | None:
    nums = [v for v in values if isinstance(v, (int, float))]
    return round(sum(nums) / len(nums), 3) if nums else None


def aggregate(results: list[dict]) -> dict:
    """Aggregate per-case classifications into LIVE MODEL EVALUATION metrics."""
    n = len(results)
    retr_cases = [r for r in results if r["retrieval_ok"] is not None]
    return {
        "cases": n,
        "tool_selection_accuracy": _rate(sum(r["tool_selection_ok"] for r in results), n),
        "required_tool_recall": _rate(sum(r["required_tool_recall_ok"] for r in results), n),
        "unnecessary_tool_rate": _rate(sum(1 for r in results if r["forbidden_tools_used"]), n),
        "retrieval_decision_accuracy": _rate(sum(r["retrieval_ok"] for r in results), len(retr_cases)),
        "unnecessary_retrieval_rate": _rate(sum(r["unnecessary_retrieval"] for r in results), n),
        "hitl_decision_accuracy": _rate(sum(r["hitl_ok"] for r in results), n),
        "completion_rate": _rate(sum(r["completed"] for r in results), n),
        "average_tool_calls": _avg([r["tool_calls"] for r in results]),
        "average_latency_ms": _avg([r["latency_ms"] for r in results]),
        "average_total_tokens": _avg([r["total_tokens"] for r in results]),
        "average_cost_usd": _avg([r["estimated_cost_usd"] for r in results]),
    }


def hitl_frequency(observations: list[Observation]) -> dict:
    """Safe HITL interruption metrics over a set of runs (types + rates only; never
    any HITL response text). Goal: important decisions interrupt, routine ones do not."""
    runs = len(observations)
    with_interrupt = [o for o in observations if o.awaiting_human_input]
    type_counts: dict[str, int] = {}
    for o in with_interrupt:
        key = o.pending_action_type or "unknown"
        type_counts[key] = type_counts.get(key, 0) + 1
    return {
        "runs": runs,
        "runs_with_interrupt": len(with_interrupt),
        "total_interrupts": len(with_interrupt),
        "interrupt_rate": _rate(len(with_interrupt), runs),
        "interrupts_per_run": _avg([1 if o.awaiting_human_input else 0 for o in observations]) or 0.0,
        "interrupt_type_counts": type_counts,
    }


# --- sanitised trace persistence --------------------------------------------


def save_trace(obs: Observation, traces_dir: Path = TRACES_DIR) -> Path:
    traces_dir.mkdir(parents=True, exist_ok=True)
    path = traces_dir / f"{obs.case_id}.json"
    path.write_text(json.dumps(obs.to_trace(), indent=2) + "\n", encoding="utf-8")
    return path


def load_traces(traces_dir: Path = TRACES_DIR) -> list[Observation]:
    if not traces_dir.exists():
        return []
    out = []
    for p in sorted(traces_dir.glob("*.json")):
        out.append(Observation.from_trace(json.loads(p.read_text(encoding="utf-8"))))
    return out


def observation_from_result(case_id: str, profile: str, result: Any, latency_ms: int) -> Observation:
    """Build a sanitised Observation from an AgentRunResult (safe fields only)."""
    pending = getattr(result, "pending_action", None) or {}
    return Observation(
        case_id=case_id,
        model_profile=profile,
        tools_used=list(getattr(result, "tools_used", []) or []),
        retrieval_used=bool(getattr(result, "retrieval_used", False)),
        awaiting_human_input=bool(getattr(result, "awaiting_human_input", False)),
        pending_action_type=pending.get("type") if isinstance(pending, dict) else None,
        step_count=int(getattr(result, "step_count", 0) or 0),
        status=getattr(result, "status", "completed"),
        latency_ms=latency_ms,
    )
