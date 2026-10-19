"""P10E-R1 model routing. Root cause of the P10E finding (19 of 152 requests on the code-default model): ``constants.DEFAULT_MODEL`` was computed at IMPORT time, before ``load_dotenv``
applied OPENROUTER_MODEL_* overrides, so ``CopilotConfig.default_model`` (and ``AppConfig.model``) froze the code default and every helper that builds a model from the config without an
explicit slug sent it. ``spec()`` and ``model_id()`` always honoured the overrides. The runtime loaders now resolve through the canonical registry at call time.
Deterministic: fake provider over a mock transport, no network, no paid call."""

from __future__ import annotations

import json

import httpx
import pytest
from langchain_openai import ChatOpenAI

from src.copilot import constants as copilot_constants
from src.llm import governed
from src.llm import models as registry
from src.llm.models import ModelProfile, model_id, spec

P = ModelProfile
ENVS = {P.FAST: "OPENROUTER_MODEL_FAST", P.BALANCED: "OPENROUTER_MODEL_BALANCED", P.ADVANCED: "OPENROUTER_MODEL_ADVANCED"}
OVERRIDE = {P.FAST: "vendor/fast-x", P.BALANCED: "vendor/balanced-y", P.ADVANCED: "vendor/advanced-z"}


@pytest.fixture()
def overrides(monkeypatch):
    for p, v in OVERRIDE.items():
        monkeypatch.setenv(ENVS[p], v)
    yield OVERRIDE
    governed.clear()


def _chat_cls(captured: list):
    def handler(req: httpx.Request):
        captured.append(json.loads(req.content))
        return httpx.Response(200, json={"id": "x", "object": "chat.completion", "created": 1, "model": captured[-1]["model"], "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})

    class C(ChatOpenAI):
        def __init__(self, **kw):
            super().__init__(http_client=httpx.Client(transport=httpx.MockTransport(handler)), **kw)
    return C


def test_each_profile_honours_its_own_override_and_leaves_the_others_alone(monkeypatch):
    defaults = {p: registry.default_slug(p) for p in P}
    for target in P:
        for p in P:
            monkeypatch.delenv(ENVS[p], raising=False)
        monkeypatch.setenv(ENVS[target], OVERRIDE[target])
        for p in P:
            expected = OVERRIDE[p] if p is target else defaults[p]
            assert model_id(p) == expected and spec(p).openrouter_id == expected                     # changing one profile never changes another


def test_a_missing_or_blank_override_falls_back_to_the_documented_registry_default(monkeypatch):
    for p in P:
        monkeypatch.delenv(ENVS[p], raising=False)
    assert {p: model_id(p) for p in P} == {p: registry.default_slug(p) for p in P}
    monkeypatch.setenv(ENVS[P.BALANCED], "   ")
    assert model_id(P.BALANCED) == registry.default_slug(P.BALANCED)                                  # a blank variable can never yield an invalid model id


def test_the_runtime_loaders_resolve_the_model_at_call_time_not_from_the_frozen_import_time_constant(overrides):
    from src.config import load_config as app_load
    from src.copilot.config import load_config as copilot_load
    # the import-time constant is stale by construction (computed before this test set the override): that is the root cause...
    assert copilot_constants.DEFAULT_MODEL != OVERRIDE[P.BALANCED]
    # ...and the loaders no longer use it
    assert copilot_load().default_model == OVERRIDE[P.BALANCED]
    assert app_load().model == OVERRIDE[P.BALANCED]


def test_a_missing_override_makes_the_loaders_fall_back_to_the_registry(monkeypatch):
    from src.config import load_config as app_load
    from src.copilot.config import load_config as copilot_load
    monkeypatch.delenv(ENVS[P.BALANCED], raising=False)
    assert copilot_load().default_model == registry.default_slug(P.BALANCED) == app_load().model


def test_an_explicit_copilot_model_setting_still_wins(monkeypatch, overrides):
    from src.copilot.config import load_config
    monkeypatch.setenv("COPILOT_MODEL", "vendor/explicit-model")
    assert load_config().default_model == "vendor/explicit-model"


def test_the_real_outgoing_request_carries_the_expected_model_for_a_helper_built_from_the_config(overrides, monkeypatch):
    """The failing scenario: a helper that builds a model from ``config.default_model`` with no explicit slug (the Career synthesis responder) must send the EFFECTIVE Balanced model."""
    from pydantic import SecretStr

    from src.copilot.config import load_config
    from src.copilot.llm.openrouter import build_chat_model
    from src.copilot.rag import responder as rag_responder

    seen: list = []
    cfg = load_config().model_copy(update={"api_key": SecretStr("test-key")})
    original = build_chat_model
    monkeypatch.setattr("src.copilot.llm.openrouter.build_chat_model", lambda config, **kw: original(config, chat_openai_cls=_chat_cls(seen), **kw))
    rag_responder.build_openrouter_responder(cfg)([{"role": "user", "content": "hi"}])
    assert seen[-1]["model"] == OVERRIDE[P.BALANCED]
    # an explicit profile slug is respected as well, per profile
    for p in P:
        build_chat_model(cfg, model=model_id(p), chat_openai_cls=_chat_cls(seen)).invoke([("human", "hi")])
        assert seen[-1]["model"] == OVERRIDE[p]


def test_the_structured_tool_and_the_agent_factory_follow_the_selected_profile(overrides, monkeypatch):
    from pydantic import BaseModel, SecretStr

    from src.application import agent_service
    from src.copilot.config import load_config
    from src.copilot.llm import openrouter
    from src.copilot.tools.structured import build_structured_producer

    cfg = load_config().model_copy(update={"api_key": SecretStr("test-key")})
    models_built: list[str] = []
    original = openrouter.build_chat_model

    def spy(config, **kw):
        models_built.append(kw.get("model") or config.default_model)
        return original(config, chat_openai_cls=_chat_cls([]), **kw)
    monkeypatch.setattr(openrouter, "build_chat_model", spy)

    class Out(BaseModel):
        x: str = ""
    build_structured_producer(cfg, Out, model=model_id(P.ADVANCED))
    build_structured_producer(cfg, Out)                                                               # no explicit model: must resolve through the config, which now follows the override
    monkeypatch.setattr("src.copilot.config.load_config", lambda: cfg)
    for p in P:
        agent_service._default_model_factory(p)                                                       # the agent factory for each selected profile
    assert models_built[0] == OVERRIDE[P.ADVANCED] and models_built[1] == OVERRIDE[P.BALANCED]
    assert models_built[2:] == [OVERRIDE[P.FAST], OVERRIDE[P.BALANCED], OVERRIDE[P.ADVANCED]]


def test_admin_governed_selection_is_honoured_and_never_bypassed(overrides):
    snap = governed.GovernedSnapshot(version_public_id="v", version=1, config_hash="h", environment="test", profile_slugs={"balanced": "vendor/governed-b", "fast": "vendor/governed-f", "advanced": "vendor/governed-a"})
    governed.set_provider(lambda: snap)
    try:
        assert {p: model_id(p) for p in P} == {P.FAST: "vendor/governed-f", P.BALANCED: "vendor/governed-b", P.ADVANCED: "vendor/governed-a"}
        from src.config import load_config as app_load
        from src.copilot.config import load_config as copilot_load
        assert copilot_load().default_model == "vendor/governed-b" == app_load().model                  # the loaders go through the registry, so a governed configuration wins
    finally:
        governed.clear()
    assert model_id(P.BALANCED) == OVERRIDE[P.BALANCED]                                               # clearing returns to the environment baseline


def test_no_application_code_hardcodes_a_raw_provider_slug_for_profile_selection():
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "src"
    offenders = []
    for f in list(root.joinpath("copilot").rglob("*.py")) + list(root.joinpath("agent").rglob("*.py")) + list(root.joinpath("application").rglob("*.py")):
        if not f.name.endswith("_eval.py") and re.search(r'["\']openai/gpt-[0-9]', f.read_text()):      # offline evaluators pass literal slugs as test INPUT; they do not route
            offenders.append(f.name)
    assert offenders == []
