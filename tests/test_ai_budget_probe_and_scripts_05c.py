"""05C PR 1: the free OpenRouter models probe and the wiring of every paid-call script to the budget governor. Mocked transports only; the probe SCRIPT is never executed here.

The key value is a sentinel: a test fails if it ever appears in a result, a message or a script's output path.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import socket
import sys
from pathlib import Path

import httpx
import pytest

from src.llm.budget import config as C
from src.llm.budget import governor as G
from src.llm.budget.errors import BudgetError
from src.llm.budget.models_probe import compare_with_pricing, key_status, probe_models
from src.llm.budget.script_guard import REFUSED_EXIT, guard_embedder_script, guard_paid_script, require_paid_budget
from src.persistence import Base, make_engine, make_session_factory
from tests.test_ai_budget_governor_05c import MARKER, raw_config

ROOT = Path(__file__).resolve().parents[1]
KEY = "sk-or-v1-SENTINEL-KEY-0123456789"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for k in ("CI", "GITHUB_ACTIONS", C.MODE_ENV, C.CLASS_ENV, C.MARKER_ENV, C.KILL_ENV, C.CONFIG_PATH_ENV, "API_ENV", "OPENROUTER_API_KEY", "OPENROUTER_BASE_URL",
              "ASK4MO_ALLOW_PAID_EMBEDDINGS", "ASK4MO_EMBEDDING_BUDGET_MARKER", "ASK4MO_EMBEDDING_MAX_CALLS"):
        monkeypatch.delenv(k, raising=False)
    def refuse(*a, **k):
        raise AssertionError("a real network connection was attempted")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    yield
    G.uninstall()


@pytest.fixture()
def sf(tmp_path):
    eng = make_engine(f"sqlite:///{tmp_path / 'ledger.db'}")
    Base.metadata.create_all(eng)
    yield make_session_factory(eng)
    eng.dispose()


# ====================================================================================================== the free models probe
def models_payload():
    return {"data": [
        {"id": "openai/chat-a", "architecture": {"modality": "text->text", "output_modalities": ["text"]}},
        {"id": "vendor/embed-by-architecture", "architecture": {"output_modalities": ["embeddings"]}},
        {"id": "vendor/embed-by-modality", "architecture": {"modality": "text->embeddings"}},
        {"id": "vendor/plain"},
        {"not_an_id": True}, "garbage",
    ]}


def transport(models=None, embeddings=None, *, models_status=200, emb_status=200, seen=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if request.url.path.endswith("/embeddings/models"):
            return httpx.Response(emb_status, json=embeddings if embeddings is not None else {"data": [{"id": "vendor/embed-listed"}]})
        if request.url.path.endswith("/models"):
            return httpx.Response(models_status, json=models if models is not None else models_payload())
        raise AssertionError(f"unexpected request {request.method} {request.url.path}")
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_key_status_reports_presence_only(monkeypatch):
    assert key_status() == "absent"
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    assert key_status() == "present" and KEY not in key_status()


def test_probe_without_a_key_makes_no_request():
    seen: list = []
    out = probe_models(client=transport(seen=seen))
    assert out["ok"] is False and out["error"] == "key_absent" and out["key"] == "absent" and not seen and out["models"] == []


def test_probe_lists_ids_flags_embeddings_where_the_api_says_so_and_consumes_no_tokens(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    seen: list = []
    out = probe_models(client=transport(seen=seen))
    assert out["ok"] and out["tokens_consumed"] == 0 and out["embeddings_listing"] == "available"
    by_id = {m["id"]: m["embeddings_capable"] for m in out["models"]}
    assert by_id == {"openai/chat-a": False, "vendor/embed-by-architecture": True, "vendor/embed-by-modality": True, "vendor/plain": False, "vendor/embed-listed": True}
    assert out["counts"] == {"models": 5, "embeddings_capable": 3}
    assert [m["id"] for m in out["models"]] == sorted(by_id)
    assert {r.method for r in seen} == {"GET"} and not any(r.url.path.endswith("/chat/completions") for r in seen)        # only metadata listings
    assert KEY not in json.dumps(out)                                                                                    # the key is never in the result


def test_probe_failure_modes_report_fixed_codes_and_never_the_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    assert probe_models(client=transport(models_status=401))["error"] == "key_rejected"
    assert probe_models(client=transport(models_status=500))["error"] == "http_500"
    bad = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"<html>")))
    assert probe_models(client=bad)["error"] == "malformed_response"
    def timeout(r):
        raise httpx.ReadTimeout("slow", request=r)
    assert probe_models(client=httpx.Client(transport=httpx.MockTransport(timeout)))["error"] == "timeout"
    def boom(r):
        raise httpx.ConnectError(f"cannot connect with {KEY}", request=r)           # even an error that contains the key must not surface
    out = probe_models(client=httpx.Client(transport=httpx.MockTransport(boom)))
    assert out["error"] == "network" and KEY not in json.dumps(out)
    soft = probe_models(client=transport(emb_status=404))                          # a missing embeddings listing degrades, it does not fail the probe
    assert soft["ok"] and soft["embeddings_listing"] == "http_404"
    assert {m["id"] for m in soft["models"] if m["embeddings_capable"]} == {"vendor/embed-by-architecture", "vendor/embed-by-modality"}


def test_probe_sends_the_key_only_as_a_bearer_header(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    seen: list[httpx.Request] = []
    probe_models(client=transport(seen=seen))
    assert seen and all(r.headers.get("authorization") == f"Bearer {KEY}" for r in seen)
    assert all(KEY not in str(r.url) for r in seen)                                # never in a URL


def test_compare_with_pricing_lists_ids_only(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    out = probe_models(client=transport())
    assert compare_with_pricing(out, ["openai/chat-a", "missing/model"]) == {"priced_and_available": ["openai/chat-a"], "priced_but_not_listed": ["missing/model"]}


def test_probe_script_is_never_run_by_tests_and_cannot_print_a_key():
    src = (ROOT / "scripts/openrouter_models_probe.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    assert "get_secret_value" not in src and "read_secret" not in src and "Authorization" not in src and "headers" not in src      # the script never touches the key; the module does
    printed = [ast.unparse(n) for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print"]
    assert printed and "environ" not in src and "getenv" not in src and "os.environ" not in src          # the script never reads the environment, so it has no key to print
    allowed_names = {"json", "out", "result", "key_status", "dumps", "print"}
    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print"):
        names = {x.id for x in ast.walk(call) if isinstance(x, ast.Name)}
        assert names <= allowed_names, names                                                       # every printed value derives from the probe result or key_status() (present/absent)
    mod_src = (ROOT / "src/llm/budget/models_probe.py").read_text(encoding="utf-8")
    assert not re.search(r"print\(|logging|logger", mod_src)                       # the probe module cannot print or log anything
    for test_file in (ROOT / "tests").glob("test_*.py"):                           # no test imports or runs the script
        text = test_file.read_text(encoding="utf-8")
        if test_file.name == Path(__file__).name:
            continue
        assert "openrouter_models_probe" not in text, test_file


# ====================================================================================================== the script gate
def cfg_file(tmp_path, **over):
    f = tmp_path / "cfg.json"
    f.write_text(json.dumps(raw_config(**over)), encoding="utf-8")
    return f


def test_guard_refuses_without_config_without_marker_and_in_ci(sf, tmp_path, capsys):
    assert guard_paid_script("x", session_factory=sf, environ={}) == REFUSED_EXIT
    assert "config_unavailable" in capsys.readouterr().err
    f = cfg_file(tmp_path)
    assert guard_paid_script("x", session_factory=sf, environ={C.CONFIG_PATH_ENV: str(f)}) == REFUSED_EXIT
    err = capsys.readouterr().err
    assert "marker_missing" in err and MARKER not in err
    env = {C.CONFIG_PATH_ENV: str(f), C.MARKER_ENV: MARKER}
    assert guard_paid_script("x", session_factory=sf, environ={**env, "CI": "true"}) == REFUSED_EXIT
    assert guard_paid_script("x", session_factory=sf, environ={**env, C.MARKER_ENV: "OD-BUDGET:wrong-ref-1"}) == REFUSED_EXIT
    assert G.active_governor() is None                                            # a refusal installs nothing


def test_guard_refuses_when_the_kill_switch_is_engaged_or_the_ledger_is_missing(sf, tmp_path):
    f = cfg_file(tmp_path)
    env = {C.CONFIG_PATH_ENV: str(f), C.MARKER_ENV: MARKER}
    from src.llm.budget.ledger import DbBudgetLedger
    DbBudgetLedger(sf).kill("operator")
    with pytest.raises(BudgetError) as e:
        require_paid_budget("x", session_factory=sf, environ=env)
    assert e.value.reason == "kill_switch"
    empty = make_session_factory(make_engine(f"sqlite:///{tmp_path / 'empty.db'}"))
    with pytest.raises(BudgetError) as e:
        require_paid_budget("x", session_factory=empty, environ=env)
    assert e.value.reason == "ledger_unavailable"


def test_guard_installs_the_chokepoint_when_everything_is_approved(sf, tmp_path):
    f = cfg_file(tmp_path)
    env = {C.CONFIG_PATH_ENV: str(f), C.MARKER_ENV: MARKER}
    assert guard_paid_script("eval_x", category="evaluation", session_factory=sf, environ=env) is None
    gov = G.active_governor()
    assert gov is not None and gov.is_open and gov.budget_class == "evaluation" and gov.default_category == "evaluation"
    seen: list = []
    client = httpx.Client(transport=httpx.MockTransport(lambda r: (seen.append(r), httpx.Response(200, json={"usage": {"prompt_tokens": 5, "completion_tokens": 2}}))[1]))
    client.post("https://openrouter.ai/api/v1/chat/completions", json={"model": "provider/model-a", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 50})
    assert len(seen) == 1 and gov.status()["calls_by_state"] == {"settled": 1}
    with pytest.raises(BudgetError):                                              # no output cap: the script's requests are bounded too
        client.post("https://openrouter.ai/api/v1/chat/completions", json={"model": "provider/model-a", "messages": [{"role": "user", "content": "hi2"}]})


def test_free_embedders_need_no_governor_and_paid_ones_do(sf, tmp_path):
    class Fake:
        def __init__(self, provider):
            self.provider = provider
    assert guard_embedder_script("x", Fake("local"), session_factory=sf, environ={}) is None
    assert guard_embedder_script("x", Fake("openrouter"), session_factory=sf, environ={}) == REFUSED_EXIT


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(f"_script_{name}", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class PaidEmbedder:
    provider, model, dimensions = "openrouter", "vendor/embed", 8

    def embed_documents(self, texts):  # pragma: no cover - must never be reached
        raise AssertionError("a paid embedding call was attempted")

    embed_query = embed_documents


def test_multilingual_retrieval_script_keeps_its_own_refusal_then_requires_the_governor(monkeypatch, capsys):
    mod = _load_script("eval_multilingual_retrieval")
    monkeypatch.setattr(mod, "build_embedder", lambda cfg: PaidEmbedder())
    monkeypatch.setattr(mod, "run_benchmark", lambda *a, **k: (_ for _ in ()).throw(AssertionError("the benchmark ran without approval")))
    # 1) the EXISTING owner approval is still required first and reports its own codes
    assert mod.main(["--embedder", "configured"]) == 2
    assert "paid_flag_missing" in capsys.readouterr().err
    # 2) with the existing approval present, the governor is still required (no configuration, no marker)
    monkeypatch.setenv("ASK4MO_ALLOW_PAID_EMBEDDINGS", "1")
    monkeypatch.setenv("ASK4MO_EMBEDDING_BUDGET_MARKER", "OD-BUDGET:legacy-marker-1")
    monkeypatch.setenv("ASK4MO_EMBEDDING_MAX_CALLS", "5")
    assert mod.main(["--embedder", "configured"]) == 2
    err = capsys.readouterr().err
    assert "AI budget governor" in err and "config_unavailable" in err
    # 3) the free local embedder path is untouched and needs no approval
    monkeypatch.setattr(mod, "run_benchmark", lambda e, dataset=None: {"label": "L", "pending": "P", "results": {m: {s: {"overall": {"recall@1": 0, "recall@5": 0, "mrr": 0, "n": 0}} for s in ("same_language", "cross_language", "mixed_corpus")} for m in ("vector", "bm25", "rrf")}})
    assert mod.main([]) == 0


def test_rebuild_script_requires_the_governor_for_a_paid_embedder_before_any_build():
    src = (ROOT / "scripts/knowledge_embedding_rebuild.py").read_text(encoding="utf-8")
    assert src.index("guard_paid_script") < src.index("rebuild_into_new_index(sf, docs")                       # the gate precedes the build
    assert "is_free(embedder)" in src and "--confirm-embedder" in src                                       # the existing confirmation stays


# every script that could make a paid provider call, by pattern: each must go through the governor gate, or be listed with the reason it cannot spend
PAID_PATTERNS = re.compile(r"OpenRouterClient\(|build_embedder\(|--allow-paid|allow_paid|build_openrouter_responder|run_live_ragas|ChatOpenAI|build_chat_model|--run-live|--live\b|embed_documents|embed_query")
EXEMPT = {
    "scripts/audit_ragas_evaluation.py": "reporting only; it states that --allow-paid/--live are required elsewhere",
    "scripts/eval_admin_ai_models.py": "deterministic evaluator over fakes (0 provider calls)",
    "scripts/eval_admin_reporting.py": "deterministic evaluator over fakes (0 provider calls)",
    "scripts/eval_expanded.py": "forces embedding_provider=local",
    "scripts/knowledge/build_runtime_knowledge.py": "refuses any non-local embedder (_assert_free_embedder)",
    "scripts/p10d_measure_dev_retrieval.py": "constructs LocalHashEmbedder directly",
    "scripts/pilot/isolated_knowledge.py": "refuses any non-local embedder (UnsafeOutputError)",
    "scripts/demo/run_ragas.sh": "the capstone demonstration harness with its own separate EUR ledger (src/demo_live)",
    "scripts/openrouter_models_probe.py": "free metadata listing only; no completion, no token (documented)",
}


def _scripts():
    return sorted(p for p in (ROOT / "scripts").rglob("*") if p.suffix in (".py", ".sh") and "__pycache__" not in p.parts)


def test_every_paid_capable_script_goes_through_the_governor_gate_or_is_exempt_with_a_reason():
    ungoverned = []
    for p in _scripts():
        rel = p.relative_to(ROOT).as_posix()
        text = p.read_text(encoding="utf-8", errors="ignore")
        if PAID_PATTERNS.search(text) and "src.llm.budget" not in text and rel not in EXEMPT:
            ungoverned.append(rel)
    assert not ungoverned, f"paid-capable scripts without the budget governor gate: {ungoverned}"
    for rel, why in EXEMPT.items():
        assert (ROOT / rel).exists() and why, rel


def test_governed_scripts_call_the_gate_after_their_own_refusals_not_instead_of_them():
    # the existing refusal strings are all still present (nothing was weakened)
    expectations = {
        "scripts/eval_agent_live.py": ["did NOT run", "P10E", "_run_live"],
        "scripts/eval_agent_judge.py": ["DID NOT run the judge", "PAID RUN READY"],
        "scripts/eval_kb_model_quality.py": ["NOT AUTHORISED", "LiveRunRefused"],
        "scripts/run_feedback_intelligence.py": ["NOT RUN", "--allow-paid"],
        "scripts/eval_ragas.py": ["NOT RUN — paid evaluation not authorized", "--allow-paid"],
        "scripts/eval_multilingual_retrieval.py": ["REFUSED: a paid embedder needs explicit owner approval", "require_paid_embedding_approval"],
        "scripts/knowledge_embedding_rebuild.py": ["--confirm-embedder", "target_dir_required"],
        "scripts/compare_model_settings.py": ["Refusing to run", "--run --confirm"],
        "scripts/compare_prompts.py": ["Refusing to run", "--run --confirm"],
    }
    for rel, needles in expectations.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "script_guard" in text, rel
        for n in needles:
            assert n in text, (rel, n)
