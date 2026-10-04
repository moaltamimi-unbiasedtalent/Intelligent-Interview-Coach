"""P10B-W10.7 corrections: governed configuration must reach the REAL runtime call sites (Interview Practice, Agent factory, Career structured
producer, OpenRouter client). Offline: fake clients and fake chat models only; no provider, no network."""

from __future__ import annotations

import socket
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from src import constants
from src.copilot import constants as copilot_constants
from src.ai_admin import config as K
from src.ai_admin.evaluator import snapshot_for
from src.config import AppConfig
from src.evaluation_service import EvaluationService
from src.interview_service import InterviewService
from src.llm import governed
from src.llm import models as M
from src.llm.policy import ModelOperation
from src.models import ModelSettings
from src.openrouter_client import ChatResult, NetworkError, OpenRouterClient
from src.pricing_service import PricingService
from tests.test_evaluation_service import _evaluation_json
from tests.test_interview_service import _config as _icfg
from tests.test_interview_service import _strategy_json


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a network call was attempted")
    monkeypatch.setattr(socket, "socket", boom)
    yield
    governed.clear()


def install(profiles=None, **ops):
    c = K.baseline_config()
    c["profiles"].update(profiles or {})
    for name, tun in ops.items():
        c["operations"][name].update(tun)
    canonical = K.normalise(c)
    governed.set_provider(lambda: snapshot_for(canonical, version_public_id="v" * 32, version=1, cfg_hash=K.config_hash(canonical)))
    return canonical


class FakeClient:
    def __init__(self, contents):
        self._contents, self.calls = list(contents), []

    def create_chat_completion(self, **kwargs) -> ChatResult:
        self.calls.append(kwargs)
        return ChatResult(content=self._contents.pop(0), model=kwargs["model"], prompt_tokens=10, completion_tokens=5, total_tokens=15,
                          reported_cost=None, duration_seconds=0.1, request_id="x")


def pricing():
    return PricingService(models_fetcher=lambda: [{"id": s, "pricing": {"prompt": "0.000001", "completion": "0.000002"},
                                                   "supported_parameters": ["temperature", "max_tokens", "response_format"]} for s in
                                                  (M.default_slug(p) for p in M.ModelProfile)])


def balanced_session():
    """A Practice session as the Next.js flow creates it: ModelSettings() (the candidate sends no model at all)."""
    return ModelSettings(prompt_technique="structured_procedure")


# ---------------- Practice: session PROFILE resolves through the governed mapping ----------------------------------------------

def test_practice_balanced_session_follows_governed_balanced_mapping_then_rolls_back():
    session = balanced_session()
    assert M.effective_interview_profile(session.model) is M.ModelProfile.BALANCED
    terra, sol = M.default_slug(M.ModelProfile.BALANCED), M.default_slug(M.ModelProfile.ADVANCED)

    base = FakeClient([_strategy_json()])
    InterviewService(base, pricing()).generate_strategy(_icfg(), session)
    assert base.calls[0]["model"] == terra                                           # baseline: Balanced -> Terra

    install(profiles={"balanced": "sol"})
    gov = FakeClient([_strategy_json(), _strategy_json()])
    svc = InterviewService(gov, pricing())
    strategy, usage = svc.generate_strategy(_icfg(), session)
    assert gov.calls[0]["model"] == sol                                              # same session, same profile, governed model
    assert usage.model == sol
    assert M.effective_interview_profile(session.model) is M.ModelProfile.BALANCED   # the session still means Balanced
    assert session.model == terra                                                    # the persisted marker is never rewritten
    assert len({c["model"] for c in gov.calls}) == 1                                 # one profile for all of its operations

    governed.clear()                                                                 # rollback: code defaults again
    again = FakeClient([_strategy_json()])
    InterviewService(again, pricing()).generate_strategy(_icfg(), session)
    assert again.calls[0]["model"] == terra


def test_practice_all_operations_share_the_session_profile_model():
    install(profiles={"balanced": "sol"})
    sol = M.default_slug(M.ModelProfile.ADVANCED)
    session = balanced_session()
    c1 = FakeClient([_strategy_json()])
    InterviewService(c1, pricing()).generate_strategy(_icfg(), session)
    c2 = FakeClient([_evaluation_json()])
    EvaluationService(c2, pricing()).evaluate_answer(_icfg(), "Q?", "An answer.", session)
    assert c1.calls[0]["model"] == c2.calls[0]["model"] == sol                       # strategy and evaluation: no per-operation routing


@pytest.mark.parametrize("legacy,profile", [("openai/gpt-5-mini", "balanced"), ("gpt-5-mini", "balanced"), ("openai/gpt-5-nano", "fast"),
                                            ("openai/gpt-5", "advanced"), ("openai/gpt-5.6-luna", "fast"), ("openai/gpt-5.6-terra", "balanced"),
                                            ("openai/gpt-5.6-sol", "advanced")])
def test_legacy_and_current_saved_slugs_keep_their_profile(legacy, profile):
    assert M.known_profile_for_slug(legacy) is M.ModelProfile(profile)
    s = ModelSettings(model=legacy)                                                  # saved sessions still load (coerced to the current id)
    assert M.effective_interview_profile(s.model) is M.ModelProfile(profile)


def test_unknown_slug_is_rejected_and_never_a_profile():
    assert M.known_profile_for_slug("evil/model-1") is None
    assert M.known_profile_for_slug("openai/gpt-5.6-sol-pro") is None
    with pytest.raises(Exception):
        ModelSettings(model="evil/model-1")
    from src.llm.runtime import governed_slug
    install(profiles={"balanced": "sol"})
    assert governed_slug("evil/model-1") == "evil/model-1"                           # an unknown slug is never remapped or trusted


def test_candidate_create_request_ignores_any_model_field():
    from src.api.schemas.interview import CreateInterviewRequest
    body = CreateInterviewRequest.model_validate({"configuration": None, "model": "openai/gpt-5.6-sol", "model_profile": "advanced"})
    assert not hasattr(body, "model") and not hasattr(body, "model_profile")


def test_governed_slug_is_a_valid_usage_record_model():
    install(profiles={"balanced": "sol"})
    c = FakeClient([_evaluation_json()])
    _e, usage = EvaluationService(c, pricing()).evaluate_answer(_icfg(), "Q?", "A.", balanced_session())
    assert usage.model == M.default_slug(M.ModelProfile.ADVANCED)


# ---------------- tunables reach the real call sites ----------------------------------------------------------------------------

def test_interview_evaluation_tunables_reach_the_client_call():
    install(evaluation={"max_output_tokens": 777, "timeout_s": 33.0, "max_retries": 0})
    c = FakeClient([_evaluation_json()])
    EvaluationService(c, pricing()).evaluate_answer(_icfg(), "Q?", "A.", balanced_session())
    call = c.calls[0]
    assert call["max_tokens"] == 777 and call["timeout_s"] == 33.0 and call["max_retries"] == 0


def test_interview_strategy_uses_structured_generation_tunables_not_evaluation():
    install(structured_generation={"max_output_tokens": 555, "timeout_s": 44.0, "max_retries": 2}, evaluation={"max_output_tokens": 999})
    c = FakeClient([_strategy_json()])
    InterviewService(c, pricing()).generate_strategy(_icfg(), balanced_session())
    assert c.calls[0]["max_tokens"] == 555 and c.calls[0]["timeout_s"] == 44.0 and c.calls[0]["max_retries"] == 2


def test_unchanged_tunables_leave_the_real_defaults_alone():
    install(profiles={"balanced": "sol"})                                            # only the mapping changed
    c = FakeClient([_evaluation_json()])
    EvaluationService(c, pricing()).evaluate_answer(_icfg(), "Q?", "A.", balanced_session())
    assert "timeout_s" not in c.calls[0] and "max_retries" not in c.calls[0]
    assert c.calls[0]["max_tokens"] == constants.DEFAULT_MAX_OUTPUT_TOKENS


def test_no_governed_config_changes_nothing_at_the_interview_call_site():
    c = FakeClient([_evaluation_json()])
    EvaluationService(c, pricing()).evaluate_answer(_icfg(), "Q?", "A.", balanced_session())
    assert set(c.calls[0]) >= {"model", "max_tokens"} and "timeout_s" not in c.calls[0] and "max_retries" not in c.calls[0]


class Captured:
    def __init__(self):
        self.kwargs = None

    def __call__(self, config, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(with_structured_output=lambda schema: SimpleNamespace(invoke=lambda m: None), invoke=lambda m: None)


def test_agent_orchestration_tunables_reach_the_chat_model(monkeypatch):
    import src.copilot.llm.openrouter as orr
    from src.application.agent_service import _default_model_factory
    cap = Captured()
    monkeypatch.setattr(orr, "build_chat_model", cap)
    install(profiles={"balanced": "sol"}, orchestration={"max_output_tokens": 900, "timeout_s": 25.0, "max_retries": 0})
    _default_model_factory(M.ModelProfile.BALANCED)
    assert cap.kwargs["model"] == M.default_slug(M.ModelProfile.ADVANCED)
    assert (cap.kwargs["max_tokens"], cap.kwargs["timeout_s"], cap.kwargs["max_retries"]) == (900, 25.0, 0)
    governed.clear()
    _default_model_factory(M.ModelProfile.BALANCED)
    assert cap.kwargs["model"] == M.code_model_id(M.ModelProfile.BALANCED)
    assert not {"max_tokens", "timeout_s", "max_retries"} & set(cap.kwargs)          # nothing governed: the code defaults apply


def test_career_structured_producer_tunables_reach_the_chat_model(monkeypatch):
    import src.copilot.llm.openrouter as orr
    from src.copilot.config import load_config
    from src.copilot.tools.structured import build_structured_producer
    from src.copilot.tools.schemas import RoleRequirements
    cap = Captured()
    monkeypatch.setattr(orr, "build_chat_model", cap)
    install(structured_generation={"max_output_tokens": 1234, "timeout_s": 20.0, "max_retries": 2})
    build_structured_producer(load_config(), RoleRequirements)
    assert (cap.kwargs["max_tokens"], cap.kwargs["timeout_s"], cap.kwargs["max_retries"]) == (1234, 20.0, 2)


def test_career_default_model_kwargs_follow_the_governed_profile_mapping_only_for_known_slugs():
    from src.copilot.config import load_config
    from src.copilot.llm.openrouter import default_model_kwargs
    install(profiles={"balanced": "sol"})
    cfg = load_config()
    assert default_model_kwargs(cfg)["model"] == M.default_slug(M.ModelProfile.ADVANCED)
    assert default_model_kwargs(cfg, model="custom/vendor-model")["model"] == "custom/vendor-model"
    assert default_model_kwargs(cfg, timeout_s=12, max_retries=0)["timeout"] == 12.0 and default_model_kwargs(cfg, max_retries=0)["max_retries"] == 0
    governed.clear()
    assert default_model_kwargs(cfg)["model"] == cfg.default_model
    assert default_model_kwargs(cfg)["max_retries"] == copilot_constants.LLM_MAX_RETRIES


def _client(handler):
    return OpenRouterClient(AppConfig(api_key=SecretStr("k")), http_client=httpx.Client(transport=httpx.MockTransport(handler)), sleeper=lambda s: None)


def test_openrouter_client_honours_governed_retries_and_timeout():
    calls = {"n": 0, "timeouts": []}

    def handler(request):
        calls["n"] += 1
        calls["timeouts"].append(request.extensions.get("timeout"))
        raise httpx.ConnectError("down")

    args = dict(model="m", messages=[{"role": "user", "content": "x"}], temperature=None, max_tokens=8)
    with pytest.raises(NetworkError):
        _client(handler).create_chat_completion(**args)
    default_calls = calls["n"]
    assert default_calls == 1 + constants.MAX_TRANSIENT_RETRIES
    calls["n"] = 0
    with pytest.raises(NetworkError):
        _client(handler).create_chat_completion(**args, max_retries=0, timeout_s=7)
    assert calls["n"] == 1                                                            # a governed 0 retries means one attempt
    assert calls["timeouts"][-1]["read"] == 7.0                                       # the governed timeout reached the request


def test_every_tunable_operation_has_a_documented_runtime_consumer():
    src = open("src/llm/runtime.py").read()
    for op in K.TUNABLE_OPERATIONS:
        assert op.name in src, op
    consumers = {ModelOperation.ORCHESTRATION: "src/application/agent_service.py", ModelOperation.STRUCTURED_GENERATION: "src/copilot/tools/structured.py",
                 ModelOperation.EVALUATION: "src/interview_service.py"}
    assert set(consumers) == set(K.TUNABLE_OPERATIONS)
    for op, path in consumers.items():
        text = open(path).read()
        assert "tunables(" in text and op.name in text, (op, path)
    for gone in (ModelOperation.FINAL_RESPONSE, ModelOperation.SPECIALIST_COACHING, ModelOperation.SPECIALIST_ROLE_ANALYSIS):
        assert gone not in K.TUNABLE_OPERATIONS
