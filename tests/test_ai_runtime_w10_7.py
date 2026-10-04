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


# ---------------- explicit INHERIT vs explicit override semantics (no equality-with-a-baseline shortcut) ------------------------

from src.llm.policy import OPERATION_POLICY  # noqa: E402

FIELDS = ("max_output_tokens", "timeout_s", "max_retries")
KEY = {"max_output_tokens": "max_tokens", "timeout_s": "timeout_s", "max_retries": "max_retries"}


def _observe_practice(op):
    c = FakeClient([_evaluation_json() if op == "evaluation" else _strategy_json()])
    if op == "evaluation":
        EvaluationService(c, pricing()).evaluate_answer(_icfg(), "Q?", "A.", balanced_session())
    else:
        InterviewService(c, pricing()).generate_strategy(_icfg(), balanced_session())
    return c.calls[0]


def _observe_agent():
    import src.copilot.llm.openrouter as orr
    from src.application.agent_service import _default_model_factory
    cap, orig = Captured(), orr.build_chat_model
    orr.build_chat_model = cap
    try:
        _default_model_factory(M.ModelProfile.BALANCED)
    finally:
        orr.build_chat_model = orig
    return cap.kwargs


def _observe_career():
    import src.copilot.llm.openrouter as orr
    from src.copilot.config import load_config
    from src.copilot.tools.schemas import RoleRequirements
    from src.copilot.tools.structured import build_structured_producer
    cap, orig = Captured(), orr.build_chat_model
    orr.build_chat_model = cap
    try:
        build_structured_producer(load_config(), RoleRequirements)
    finally:
        orr.build_chat_model = orig
    return cap.kwargs


# (operation, consumer name, observer, key in the observed call, the REAL pre-W10.7 default for that key at that consumer)
CONSUMERS = [
    ("orchestration", "agent", _observe_agent, {"max_output_tokens": None, "timeout_s": None, "max_retries": None}),
    ("structured_generation", "career", _observe_career, {"max_output_tokens": copilot_constants.STRUCTURED_MAX_OUTPUT_TOKENS, "timeout_s": None, "max_retries": None}),
    ("structured_generation", "practice", lambda: _observe_practice("strategy"), {"max_output_tokens": constants.DEFAULT_MAX_OUTPUT_TOKENS, "timeout_s": None, "max_retries": None}),
    ("evaluation", "practice", lambda: _observe_practice("evaluation"), {"max_output_tokens": constants.DEFAULT_MAX_OUTPUT_TOKENS, "timeout_s": None, "max_retries": None}),
]
NON_BASELINE = {"max_output_tokens": 640, "timeout_s": 22.0, "max_retries": 3}


def _value(call, field):
    return call.get(KEY[field])


@pytest.mark.parametrize("op,consumer,observe,defaults", CONSUMERS, ids=[f"{o}-{c}" for o, c, _f, _d in CONSUMERS])
@pytest.mark.parametrize("field", FIELDS)
def test_inherit_explicit_old_baseline_nonbaseline_and_clear_at_the_real_consumer(op, consumer, observe, defaults, field):
    # A. INHERIT: the real call keeps its pre-W10.7 default (an absent key means the client's/consumer's own default)
    install()
    assert _value(observe(), field) == defaults[field]
    # B. EXPLICIT non-baseline value: exact
    install(**{op: {field: NON_BASELINE[field]}})
    assert _value(observe(), field) == NON_BASELINE[field]
    # C. EXPLICIT value equal to the OLD policy baseline: STILL applied exactly (never treated as inherit)
    baseline = getattr(OPERATION_POLICY[ModelOperation(op)], field)
    install(**{op: {field: baseline}})
    assert _value(observe(), field) == baseline
    # D. CLEAR back to inherit: the pre-W10.7 default returns
    install(**{op: {field: NON_BASELINE[field]}})
    assert _value(observe(), field) == NON_BASELINE[field]
    install(**{op: {field: None}})
    assert _value(observe(), field) == defaults[field]


def test_pre_w10_7_defaults_are_recorded_truthfully_and_differ_from_the_policy_table():
    d = K.consumer_defaults()
    assert d["orchestration"][0]["max_output_tokens"] == copilot_constants.DEFAULT_MAX_OUTPUT_TOKENS == 1024
    assert {x["max_output_tokens"] for x in d["structured_generation"]} == {copilot_constants.STRUCTURED_MAX_OUTPUT_TOKENS, constants.DEFAULT_MAX_OUTPUT_TOKENS}
    assert d["evaluation"][0]["timeout_s"] == constants.READ_TIMEOUT_SECONDS and d["evaluation"][0]["max_retries"] == constants.MAX_TRANSIENT_RETRIES
    mismatches = [op for op, rows in d.items() for r in rows for f in FIELDS if r[f] != getattr(OPERATION_POLICY[ModelOperation(op)], f)]
    assert mismatches                                                                  # the code policy table is NOT the runtime default (hence inherit)


def test_baseline_is_literally_inherit_and_inherit_hashes_differently_from_a_number():
    base = K.normalise(K.baseline_config())
    assert all(v is None for tun in base["operations"].values() for v in tun.values())
    from src.ai_admin.evaluator import snapshot_for as snap
    assert all(not s for s in snap(base).operation_overrides.values())                # a baseline config overrides nothing
    for op in K.TUNABLE_OPERATIONS:
        for field in FIELDS:
            explicit = K.baseline_config()
            explicit["operations"][op.value][field] = getattr(OPERATION_POLICY[op], field)    # a number that equals the old policy value
            assert K.config_hash(K.normalise(explicit)) != K.config_hash(base)


def test_baseline_governed_configuration_preserves_runtime_behaviour():
    before = {(o, c): obs() for o, c, obs, _d in CONSUMERS}
    install(profiles={})                                                              # an untouched baseline configuration
    assert {(o, c): obs() for o, c, obs, _d in CONSUMERS} == before


def test_bounds_apply_only_to_explicit_numbers_and_the_time_budget_uses_real_defaults_for_inherit():
    ok = K.baseline_config()
    assert K.passed(K.validate(K.normalise(ok)))                                      # inherit everywhere is valid
    bad = K.baseline_config(); bad["operations"]["evaluation"]["max_output_tokens"] = 10
    assert not K.passed(K.validate(K.normalise(bad)))
    big = K.baseline_config(); big["operations"]["evaluation"]["max_retries"] = 3     # timeout inherited (60 s real default): 60 x 4 = 240 s, fine
    assert K.passed(K.validate(K.normalise(big)))
    big["operations"]["evaluation"]["timeout_s"] = 180.0                              # 180 x 4 = 720 s > 600 s
    assert not K.passed(K.validate(K.normalise(big)))
    only_t = K.baseline_config(); only_t["operations"]["structured_generation"]["timeout_s"] = 180.0   # retries inherited at the real max (1): 360 s
    assert K.passed(K.validate(K.normalise(only_t)))
    only_r = K.baseline_config(); only_r["operations"]["structured_generation"]["max_retries"] = 3      # timeout inherited at the real max (60): 240 s
    assert K.passed(K.validate(K.normalise(only_r)))
