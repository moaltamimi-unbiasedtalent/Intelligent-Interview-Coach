"""Per-operation model policy (Capstone P5/E4): resolution, floors, fallback, safety."""

from __future__ import annotations

import pytest

from src.llm.models import ModelProfile
from src.llm.policy import (
    ModelCapability,
    ModelOperation,
    OPERATION_POLICY,
    all_policies,
    operation_uses_model,
    resolve_policy,
)


def test_every_operation_has_a_policy():
    assert set(OPERATION_POLICY) == set(ModelOperation)


def test_orchestration_requires_tools_and_never_degrades_below_balanced():
    rp = resolve_policy(ModelOperation.ORCHESTRATION, ModelProfile.FAST)
    assert rp.profile == ModelProfile.BALANCED       # clamped UP to the floor
    assert rp.capability_capped is True
    assert rp.requires_tools is True
    assert rp.capability is ModelCapability.TOOL_CALLING
    # Fallbacks never drop below the Balanced floor for orchestration.
    assert rp.fallback_profiles == []


def test_advanced_user_keeps_advanced_for_orchestration():
    rp = resolve_policy(ModelOperation.ORCHESTRATION, ModelProfile.ADVANCED)
    assert rp.profile == ModelProfile.ADVANCED
    assert rp.capability_capped is False
    # Fallback is bounded, strictly-lower, never below Balanced.
    assert rp.fallback_profiles == [ModelProfile.BALANCED]


def test_evidence_operation_is_deterministic_no_model():
    assert operation_uses_model(ModelOperation.SPECIALIST_EVIDENCE_ANALYSIS) is False
    rp = resolve_policy(ModelOperation.SPECIALIST_EVIDENCE_ANALYSIS, ModelProfile.ADVANCED)
    assert rp.uses_model is False
    assert rp.profile is None and rp.model_id is None and rp.spec is None
    assert rp.capability is ModelCapability.NONE


def test_fallback_chain_is_strictly_lower_and_bounded():
    order = {ModelProfile.FAST: 0, ModelProfile.BALANCED: 1, ModelProfile.ADVANCED: 2}
    for op in ModelOperation:
        for prof in ModelProfile:
            rp = resolve_policy(op, prof)
            if not rp.uses_model:
                continue
            assert all(order[f] < order[rp.profile] for f in rp.fallback_profiles)
            assert len(rp.fallback_profiles) <= 2  # at most FAST+BALANCED below ADVANCED


def test_raw_slug_is_never_honoured_as_a_profile():
    # A raw provider slug is not a ModelProfile → it can never SELECT that slug's model;
    # it falls back to the safe Balanced default. The browser can never pick a model.
    rp = resolve_policy(ModelOperation.ORCHESTRATION, "openai/gpt-5.6-sol")  # type: ignore[arg-type]
    assert rp.profile == ModelProfile.BALANCED
    assert rp.model_id != "openai/gpt-5.6-sol"


def test_unknown_operation_is_rejected():
    with pytest.raises(ValueError):
        resolve_policy("do_whatever_you_want", ModelProfile.BALANCED)  # type: ignore[arg-type]


def test_none_profile_defaults_to_balanced_floor():
    rp = resolve_policy(ModelOperation.STRUCTURED_GENERATION, None)
    assert rp.profile == ModelProfile.BALANCED


def test_evaluation_recommends_advanced_but_can_degrade_to_balanced():
    rp = resolve_policy(ModelOperation.EVALUATION, ModelProfile.BALANCED)
    assert rp.profile == ModelProfile.ADVANCED       # min capability floor
    assert rp.capability_capped is True
    assert ModelProfile.BALANCED in rp.fallback_profiles
    assert ModelProfile.FAST not in rp.fallback_profiles  # high-stakes floor


def test_to_dict_is_safe_and_carries_no_secret():
    rp = resolve_policy(ModelOperation.ORCHESTRATION, ModelProfile.BALANCED)
    d = rp.to_dict()
    blob = str(d).lower()
    assert "key" not in blob and "secret" not in blob and "prompt" not in blob
    assert d["operation"] == "orchestration"
    assert d["model_id"]  # a public, env-overridable slug (not a secret)


def test_all_policies_covers_every_operation():
    assert len(all_policies(ModelProfile.BALANCED)) == len(ModelOperation)
