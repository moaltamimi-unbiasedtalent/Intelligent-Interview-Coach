"""Sprint 4 Phase 9.5 — model registry, workload mapping, legacy compat, privacy.

Offline only (no provider call, no secret). Covers profile resolution + env overrides,
the workload→profile policy, capability flags, legacy-slug coercion, temperature
handling and the reasoning-privacy guarantee.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from src.llm.models import (
    INTERVIEW_RECOMMENDED_PROFILE,
    INTERVIEW_SESSION_DEFAULT_PROFILE,
    ModelProfile,
    ModelSelectionMode,
    Workload,
    WORKLOAD_PROFILE,
    all_specs,
    effective_interview_profile,
    legacy_synonyms,
    model_id,
    profile_for_model,
    recommended_profile,
    selection_mode,
    spec,
    supports_temperature,
    workload_profile,
)


# --- registry (§42) ----------------------------------------------------------


def test_all_profiles_registered_with_nonempty_ids():
    for profile in ModelProfile:
        assert model_id(profile).strip()


def test_profiles_are_distinct_by_default():
    ids = {model_id(p) for p in ModelProfile}
    assert len(ids) == 3


def test_default_slugs_are_the_documented_gpt56_family():
    assert model_id(ModelProfile.FAST) == "openai/gpt-5.6-luna"
    assert model_id(ModelProfile.BALANCED) == "openai/gpt-5.6-terra"
    assert model_id(ModelProfile.ADVANCED) == "openai/gpt-5.6-sol"


def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL_BALANCED", "acme/custom-balanced")
    assert model_id(ModelProfile.BALANCED) == "acme/custom-balanced"


def test_blank_override_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL_ADVANCED", "   ")
    assert model_id(ModelProfile.ADVANCED) == "openai/gpt-5.6-sol"


def test_agent_profile_supports_tools():
    assert spec(workload_profile(Workload.AGENT)).supports_tools is True


def test_structured_workloads_require_structured_output():
    for wl in (Workload.JD_ANALYSIS, Workload.QUESTION_GENERATION,
               Workload.ANSWER_EVALUATION, Workload.FINAL_REPORT):
        # recommended_profile works for both registry- and session-selected workloads.
        assert spec(recommended_profile(wl)).supports_structured_output is True


def test_registry_import_uses_no_secret():
    import inspect
    import src.llm.models as m
    src = inspect.getsource(m)
    assert "API_KEY" not in src and "api_key" not in src


# --- workload mapping (§43) — centrally-selected (REGISTRY) --------------------


@pytest.mark.parametrize("workload,expected", [
    (Workload.AGENT, ModelProfile.BALANCED),
    (Workload.CAREER_SYNTHESIS, ModelProfile.BALANCED),
    (Workload.JD_ANALYSIS, ModelProfile.BALANCED),
    (Workload.QUESTION_GENERATION, ModelProfile.BALANCED),
    (Workload.UTILITY, ModelProfile.FAST),
    (Workload.RAGAS, ModelProfile.FAST),
])
def test_registry_workload_effective_profile(workload, expected):
    assert selection_mode(workload) == ModelSelectionMode.REGISTRY
    assert workload_profile(workload) == expected


# Interview workloads are session-selected: their registry entry is a RECOMMENDATION,
# never an unconditional effective tier (evaluation/report recommend Advanced).
@pytest.mark.parametrize("workload,recommended", [
    (Workload.INTERVIEW_STRATEGY, ModelProfile.BALANCED),
    (Workload.INTERVIEW_QUESTION, ModelProfile.BALANCED),
    (Workload.ANSWER_EVALUATION, ModelProfile.ADVANCED),
    (Workload.FINAL_REPORT, ModelProfile.ADVANCED),
])
def test_interview_workload_is_session_selected_with_recommendation(workload, recommended):
    assert selection_mode(workload) == ModelSelectionMode.INTERVIEW_SESSION
    assert recommended_profile(workload) == recommended
    # It must NOT be exposed as an effective centrally-selected profile.
    assert workload not in WORKLOAD_PROFILE
    with pytest.raises(ValueError):
        workload_profile(workload)


def test_every_workload_is_classified_exactly_once():
    for wl in Workload:
        in_registry = wl in WORKLOAD_PROFILE
        in_interview = wl in INTERVIEW_RECOMMENDED_PROFILE
        assert in_registry != in_interview  # exactly one


def test_interview_session_default_is_balanced():
    assert INTERVIEW_SESSION_DEFAULT_PROFILE == ModelProfile.BALANCED


@pytest.mark.parametrize("profile", list(ModelProfile))
def test_effective_interview_profile_follows_the_session_model(profile):
    # All four interview operations share ModelSettings.model, so the effective tier
    # is whatever the session selected — not an unused registry entry.
    assert effective_interview_profile(model_id(profile)) == profile


def test_default_interview_model_settings_resolve_to_balanced():
    from src.models import ModelSettings
    assert effective_interview_profile(ModelSettings().model) == ModelProfile.BALANCED
    assert effective_interview_profile(ModelSettings().model) == INTERVIEW_SESSION_DEFAULT_PROFILE


# --- legacy compatibility (§44) ---------------------------------------------


@pytest.mark.parametrize("legacy,profile", [
    ("openai/gpt-5-nano", ModelProfile.FAST),
    ("openai/gpt-5-mini", ModelProfile.BALANCED),
    ("openai/gpt-5", ModelProfile.ADVANCED),
])
def test_legacy_slugs_map_to_profiles(legacy, profile):
    assert profile_for_model(legacy) == profile


def test_legacy_synonyms_point_to_current_ids():
    syn = legacy_synonyms()
    assert syn["openai/gpt-5-mini"] == model_id(ModelProfile.BALANCED)
    assert syn["openai/gpt-5"] == model_id(ModelProfile.ADVANCED)


def test_unknown_model_defaults_to_balanced():
    assert profile_for_model("some/unheard-of-model") == ModelProfile.BALANCED
    assert profile_for_model(None) == ModelProfile.BALANCED


def test_persisted_legacy_model_setting_coerces_not_crashes():
    from src.models import ModelSettings
    # An old saved selection must coerce to a current model, never crash.
    assert ModelSettings(model="openai/gpt-5-mini").model == model_id(ModelProfile.BALANCED)
    assert ModelSettings(model="openai/gpt-5").model == model_id(ModelProfile.ADVANCED)


def test_unapproved_arbitrary_model_still_rejected():
    from pydantic import ValidationError
    from src.models import ModelSettings
    with pytest.raises(ValidationError):
        ModelSettings(model="anthropic/claude-not-approved")


# --- model arguments / temperature (§45) ------------------------------------


def test_reasoning_models_omit_temperature():
    for p in ModelProfile:
        assert supports_temperature(model_id(p)) is False


def test_non_registry_model_keeps_temperature():
    assert supports_temperature("some/temperature-model") is True


def test_all_specs_have_documented_purpose_and_reasoning():
    for s in all_specs():
        assert s.purpose and s.default_reasoning


# --- reasoning privacy (§46) -------------------------------------------------


def test_provider_reasoning_never_leaks_into_agent_result():
    from src.application.agent_service import AgentApplicationService
    from src.agent.models import AgentRunRequest

    class _FakeCareer:
        def search_knowledge(self, *a, **k):  # pragma: no cover - unused here
            raise AssertionError

    class Model:
        def bind_tools(self, s):
            return self

        def invoke(self, messages):
            # A provider response carrying hidden reasoning metadata.
            return AIMessage(
                content="Here is your guidance.",
                additional_kwargs={"reasoning": "SECRET-CHAIN-OF-THOUGHT"},
                response_metadata={"reasoning_details": [{"text": "SECRET-DETAILS"}]},
            )

    svc = AgentApplicationService(model_factory=lambda: Model(), career_service=_FakeCareer())
    res = svc.run(AgentRunRequest(goal="Prep", user_id="1"))
    blob = str(res.events) + str(res.conversation) + str(res.tool_calls) + str(res.warnings)
    assert "SECRET-CHAIN-OF-THOUGHT" not in blob
    assert "SECRET-DETAILS" not in blob
    # The visible answer is still returned; only the hidden reasoning is excluded.
    assert res.response == "Here is your guidance."
    assert res.conversation and res.conversation[-1]["content"] == "Here is your guidance."
