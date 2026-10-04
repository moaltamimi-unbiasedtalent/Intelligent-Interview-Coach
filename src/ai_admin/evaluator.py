"""Deterministic evaluation of one exact configuration (P10B-W10.7). NO provider call, NO network, NO model.

The evaluator installs the candidate as a temporary governed snapshot and drives the REAL resolution code (``resolve_policy`` and the model
registry) for every operation and every candidate profile, then checks the invariants the product relies on. It evidences that a configuration
is CONTRACT-SAFE (right models, bounds, floors, deterministic and realtime boundaries, Interview and profile boundaries). It does NOT measure
answer quality: live model quality is a separate, human-owned evidence class that this wave does not produce and never claims.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager

from src.ai_admin import catalogue as C
from src.ai_admin import config as K
from src.llm import governed
from src.llm.models import ModelProfile, code_model_id, effective_interview_profile, model_id
from src.llm.policy import OPERATION_POLICY, ModelCapability, ModelOperation, resolve_policy

EVALUATOR_VERSION = "ai-eval-1"
_LOCK = threading.Lock()


def snapshot_for(canonical: dict, *, version_public_id: str = "evaluation", version: int = 0, cfg_hash: str = "", environment: str = "staging") -> governed.GovernedSnapshot:
    return governed.GovernedSnapshot(
        version_public_id=version_public_id, version=version, config_hash=cfg_hash, environment=environment,
        profile_slugs={p: C.slug_for(entry) for p, entry in canonical["profiles"].items()},
        operation_overrides={name: dict(tun) for name, tun in canonical["operations"].items()})


@contextmanager
def installed(snapshot: governed.GovernedSnapshot):
    """Temporarily route the registry through ``snapshot`` (serialised; the previous provider is always restored)."""
    with _LOCK:
        previous = governed._provider
        governed.set_provider(lambda: snapshot)
        try:
            yield
        finally:
            governed.set_provider(previous)


def evaluate(canonical: dict) -> dict:
    """Return ``{"passed", "checks", "summary", "live_calls"}`` for a canonical configuration."""
    checks = [c.as_dict() for c in K.validate(canonical)]
    cases = 0
    failures: list[str] = []

    def add(code: str, label: str, ok: bool, detail: str = "") -> None:
        checks.append({"code": code, "label": label, "passed": bool(ok), "detail": "" if ok else detail})

    if not K.passed(K.validate(canonical)):
        return {"passed": False, "checks": checks, "summary": {"resolution_cases": 0, "changed_from_baseline": K.diff_from_baseline(canonical),
                                                                "note": "Validation failed, so resolution was not exercised."}, "live_calls": 0}

    snap = snapshot_for(canonical)
    slugs = set(snap.profile_slugs.values())
    with installed(snap):
        for op in ModelOperation:
            policy = OPERATION_POLICY[op]
            for user in ModelProfile:
                cases += 1
                r = resolve_policy(op, user)
                where = f"{op.value}/{user.value}"
                if policy.capability is ModelCapability.NONE:
                    if r.uses_model or r.model_id is not None:
                        failures.append(f"{where}: a deterministic operation resolved to a model")
                    continue
                if policy.capability is ModelCapability.REALTIME:
                    if r.model_id is not None:
                        failures.append(f"{where}: realtime resolved to a chat slug")
                    continue
                effective_floor = max(user, policy.min_capability, key=lambda p: K._TIER_ORDER[p])
                if r.profile is not effective_floor:
                    failures.append(f"{where}: effective profile differs from max(user, floor)")
                if r.model_id not in slugs or r.model_id != snap.profile_slugs[r.profile.value]:
                    failures.append(f"{where}: resolved slug is not the catalogue slug of the effective profile")
                for fb, slug in zip(r.fallback_profiles, r.fallback_model_ids):
                    if K._TIER_ORDER[fb] < K._TIER_ORDER[policy.fallback_floor] or slug != snap.profile_slugs[fb.value]:
                        failures.append(f"{where}: fallback outside floor or catalogue")
                tun = canonical["operations"].get(op.value)
                if tun and (r.max_output_tokens, r.timeout_s, r.max_retries) != (tun["max_output_tokens"], tun["timeout_s"], tun["max_retries"]):
                    failures.append(f"{where}: tunables not applied exactly")
                if (r.capability, r.structured_output, r.requires_tools, r.temperature) != (policy.capability, policy.structured_output, policy.requires_tools, policy.temperature):
                    failures.append(f"{where}: a code-defined field was altered")
        interview_ok = all(effective_interview_profile(code_model_id(p)) is p for p in ModelProfile)
        registry_ok = all(model_id(p) == snap.profile_slugs[p.value] for p in ModelProfile)
    add("resolution_matrix", f"All {cases} operation x profile resolutions hold their invariants", not failures, "; ".join(failures[:4]))
    add("registry_follows_snapshot", "The model registry resolves each profile to its configured catalogue slug", registry_ok, "A profile did not resolve to its configured slug.")
    add("interview_profile_boundary", "Saved Interview session models keep their profile meaning", interview_ok,
        "A saved session slug no longer maps to its original profile.")
    deterministic = [o for o in ModelOperation if OPERATION_POLICY[o].capability is ModelCapability.NONE]
    add("deterministic_operations_model_free", "Deterministic operations stay model-free", bool(deterministic) and all(not resolve_policy(o, None).uses_model for o in deterministic),
        "A deterministic operation uses a model.")
    specialists = [o for o in ModelOperation if o.value.startswith("specialist_")]
    add("exactly_three_specialists", "Exactly three specialist operations exist; none is an evaluation specialist", len(specialists) == 3 and not any("evaluation" in o.value for o in specialists),
        "The specialist set changed.")
    from src.application.agent_service import _resolve_profile

    try:
        _resolve_profile("openai/gpt-5.6-sol")
        raw_rejected = False
    except Exception:  # noqa: BLE001 - any rejection is the expected outcome
        raw_rejected = True
    add("raw_slug_rejected_at_boundary", "A candidate-supplied raw slug is still rejected", raw_rejected, "A raw slug was accepted as a profile.")

    ok = all(c["passed"] for c in checks)
    return {"passed": ok, "checks": checks, "live_calls": 0,
            "summary": {"resolution_cases": cases, "failed_cases": len(failures), "checks": len(checks), "failed_checks": sum(1 for c in checks if not c["passed"]),
                        "changed_from_baseline": K.diff_from_baseline(canonical),
                        "evidence_class": "deterministic contract evaluation; not a measure of live model quality"}}
