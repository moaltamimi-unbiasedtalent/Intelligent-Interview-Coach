"""Production configuration version identity (Capstone P6/E6, §16).

Gives every production behaviour an attributable, deterministic version id derived from
the ACTUAL configuration in the repository — so a Prompt Lab experiment (or a reviewer)
can state exactly which prompt / model-policy / specialist / knowledge version a result
was produced against. These are content hashes of committed configuration, NOT secrets and
NOT the prompt text itself (contents are never exposed to candidates).

Pure, read-only and offline: computing a version never calls a model or a provider.
"""

from __future__ import annotations

import hashlib
import json

__all__ = [
    "prompt_version", "model_policy_version", "specialist_config_version",
    "knowledge_version", "production_versions",
]


def _short(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def prompt_version() -> str:
    """A stable id for Mo's production system prompt (hash of its content)."""
    try:
        from src.agent.policies import SYSTEM_PROMPT
        return "prompt-" + _short(SYSTEM_PROMPT)
    except Exception:  # noqa: BLE001
        return "prompt-unknown"


def model_policy_version() -> str:
    """A stable id for the central per-operation model policy (E4) table."""
    try:
        from src.llm.policy import OPERATION_POLICY
        payload = {
            op.value: [
                p.capability.value, p.min_capability.value, p.fallback_floor.value,
                p.structured_output, p.requires_tools, p.max_output_tokens,
                p.timeout_s, p.max_retries,
            ]
            for op, p in sorted(OPERATION_POLICY.items(), key=lambda kv: kv[0].value)
        }
        return "policy-" + _short(json.dumps(payload, sort_keys=True))
    except Exception:  # noqa: BLE001
        return "policy-unknown"


def specialist_config_version() -> str:
    """A stable id for the bounded-specialist registry (P5)."""
    try:
        from src.agent.specialists.registry import SPECIALISTS
        payload = {
            name.value: [spec.operation.value, spec.model_backed, spec.reads_private_evidence,
                         spec.tool_name]
            for name, spec in sorted(SPECIALISTS.items(), key=lambda kv: kv[0].value)
        }
        return "specialists-" + _short(json.dumps(payload, sort_keys=True))
    except Exception:  # noqa: BLE001
        return "specialists-unknown"


def knowledge_version() -> str:
    """A stable id for the governed knowledge build (from build metadata provenance)."""
    try:
        from pathlib import Path
        build = json.loads(Path("data/knowledge/build_metadata.json").read_text(encoding="utf-8"))
        runtime = build.get("runtime_pipeline_version") or "unbuilt"
        built = build.get("built_at") or "unbuilt"
        return "knowledge-" + _short(f"{runtime}|{built}")
    except Exception:  # noqa: BLE001
        return "knowledge-unbuilt"


def production_versions() -> dict:
    """All production configuration versions — safe metadata for attribution / diagnostics."""
    return {
        "prompt_version": prompt_version(),
        "model_policy_version": model_policy_version(),
        "specialist_config_version": specialist_config_version(),
        "knowledge_version": knowledge_version(),
    }
