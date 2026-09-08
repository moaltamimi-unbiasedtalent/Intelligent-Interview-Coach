"""Post-Sprint-4 P1 — Fast / Balanced / Advanced Agent Coach profiles.

The candidate picks a speed/quality tier; it resolves to a registry model (never a
raw provider slug). All profiles preserve the tool allowlist, retrieval grounding,
citation guard, HITL, memory policy and the bounded step budget. No provider calls.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from src.agent.models import AgentRunRequest
from src.application.agent_service import _default_model_factory, _resolve_profile
from src.application.agent_service import AgentApplicationService
from src.application.errors import ValidationError
from src.llm.models import ModelProfile, model_id


def _model():
    class M:
        def bind_tools(self, s):
            return self

        def invoke(self, messages):
            return AIMessage(content="tips: use STAR.")
    return M()


# --- profile resolution / validation ----------------------------------------


@pytest.mark.parametrize("value,expected", [
    ("fast", ModelProfile.FAST),
    ("balanced", ModelProfile.BALANCED),
    ("advanced", ModelProfile.ADVANCED),
    ("ADVANCED", ModelProfile.ADVANCED),
    (None, ModelProfile.BALANCED),
    ("", ModelProfile.BALANCED),
])
def test_resolve_profile_valid(value, expected):
    assert _resolve_profile(value) is expected


@pytest.mark.parametrize("bad", ["openai/gpt-5.6-sol", "gpt-5", "turbo", "openai/foo-model"])
def test_resolve_profile_rejects_raw_slug(bad):
    # A raw provider model slug from the client is NEVER accepted as a profile.
    with pytest.raises(ValidationError):
        _resolve_profile(bad)


def test_default_factory_selects_profile_model(monkeypatch):
    # The default factory maps each profile to its registry slug — no arbitrary id.
    captured = {}

    def fake_build_chat_model(config, *, model=None, **kw):
        captured["model"] = model
        return _model()

    monkeypatch.setattr("src.copilot.llm.openrouter.build_chat_model", fake_build_chat_model)
    monkeypatch.setattr("src.copilot.config.load_config", lambda: object())
    _default_model_factory(ModelProfile.FAST)
    assert captured["model"] == model_id(ModelProfile.FAST)
    _default_model_factory(ModelProfile.ADVANCED)
    assert captured["model"] == model_id(ModelProfile.ADVANCED)


# --- profile effect through the service --------------------------------------


@pytest.mark.parametrize("profile", ["fast", "balanced", "advanced"])
def test_run_reports_selected_profile(profile):
    svc = AgentApplicationService(model_factory=lambda: _model(), career_service=object())
    res = svc.run(AgentRunRequest(goal="tips?", user_id="u1", profile=profile))
    assert res.profile == profile


def test_default_profile_is_balanced():
    svc = AgentApplicationService(model_factory=lambda: _model(), career_service=object())
    res = svc.run(AgentRunRequest(goal="tips?", user_id="u1"))
    assert res.profile == "balanced"


def test_invalid_profile_rejected_by_service():
    svc = AgentApplicationService(model_factory=lambda: _model(), career_service=object())
    with pytest.raises(ValidationError):
        svc.run(AgentRunRequest(goal="tips?", user_id="u1", profile="openai/foo-model"))


def test_profile_persists_across_a_continued_turn():
    svc = AgentApplicationService(model_factory=lambda: _model(), career_service=object())
    res = svc.run(AgentRunRequest(goal="tips?", user_id="u1", profile="fast"))
    cont = svc.continue_run(res.run_id, "u1", "and more?")
    assert cont.profile == "fast"  # the thread keeps its selected tier
