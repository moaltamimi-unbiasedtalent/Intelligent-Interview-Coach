"""02E: the multi-model embedding benchmark runner, end to end with a FAKE provider. No network, no key, no paid call."""

from __future__ import annotations

import json
import math
import socket
import subprocess
import sys
import types
from pathlib import Path

import pytest

from src.copilot import constants
from src.copilot import embedding_budget as EBUD
from src.copilot.embeddings import BaseEmbedder, EmbeddingProviderError, LocalHashEmbedder
from src.copilot.evaluation import embedding_benchmark as EB
from src.copilot.evaluation import multilingual_retrieval as ML
from src.copilot.index_manifest import IndexIncompatibleError

ROOT = Path(__file__).resolve().parents[1]
APPROVAL = {EB.BUDGET_MARKER_ENV: "OD-BUDGET:test-fixture-only", EBUD.PAID_FLAG_ENV: "1", EBUD.BUDGET_MARKER_ENV: "OD-BUDGET:test-fixture-only",
            EBUD.MAX_CALLS_ENV: "1000"}
N_CALLS = math.ceil(49 / constants.EMBED_BATCH_SIZE) + 49 + 21


class FakeProvider(BaseEmbedder):
    """A deterministic stand-in for a provider. Counts calls; never touches a network."""

    def __init__(self, spec: EB.ModelSpec, dims: int = 48, provider: str = "fake"):
        self._h = LocalHashEmbedder(dims)
        self.provider, self.model, self.dimensions, self.version = provider, spec.model, dims, spec.version
        self.doc_calls = self.query_calls = 0

    def embed_documents(self, texts):
        self.doc_calls += 1
        return self._h.embed_documents(texts)

    def embed_query(self, text):
        self.query_calls += 1
        return self._h.embed_query(text)


def _specs(n=2, provider="fake"):
    return [EB.ModelSpec(f"m{i}", f"vendor/model-{i}", 48, f"v{i}", provider) for i in range(n)]


class Factory:
    def __init__(self, provider="fake"):
        self.built: list[FakeProvider] = []
        self.provider = provider

    def __call__(self, spec):
        e = FakeProvider(spec, 32 + 16 * len(self.built), self.provider)
        self.built.append(e)
        return e


def _ticker():
    state = {"t": 0.0}

    def clock():
        state["t"] += 0.001
        return state["t"]
    return clock


def _run(tmp_path, specs=None, factory=None, **kw):
    kw.setdefault("allow_fake", True)
    kw.setdefault("clock", _ticker())
    return EB.run_embedding_benchmark(specs or _specs(), factory or Factory(), store_root=tmp_path / "idx", **kw)


# ------------------------------------------------------------------ configuration, datasets, dry run
def test_candidate_models_come_from_configuration_in_order_without_a_selection():
    specs = EB.load_models()
    assert [s.key for s in specs] == ["openai-3-large", "openai-3-small", "bge-m3", "qwen3-embedding-8b", "multilingual-e5-large"]
    raw = json.loads(EB.MODELS_PATH.read_text(encoding="utf-8"))
    assert "UNVERIFIED" in raw["availability"] and "selection" not in raw
    assert all(s.provider == "openrouter" for s in specs)
    # provider model ids live in the config file, not scattered in the runner
    src = Path(EB.__file__).read_text(encoding="utf-8")
    assert "text-embedding-3" not in src and "bge-m3" not in src and "qwen3" not in src


def test_models_config_validation(tmp_path):
    def write(models):
        p = tmp_path / "m.json"
        p.write_text(json.dumps({"models": models}), encoding="utf-8")
        return p
    ok = {"key": "a", "model": "x/y", "dimensions": 8, "version": "v"}
    assert [s.key for s in EB.load_models(write([ok]))] == ["a"]
    for bad in ([], [ok, ok], [ok, {**ok, "key": "b"}], [{**ok, "key": "Bad Key"}], [{"key": "a"}]):
        with pytest.raises(EB.BenchmarkRefused):
            EB.load_models(write(bad))
    with pytest.raises(EB.BenchmarkRefused):
        EB.load_models(tmp_path / "missing.json")


def test_abstention_dataset_is_frozen_and_covers_seven_languages():
    ds = EB.load_abstention()
    assert {q["language"] for q in ds["queries"]} == set(ML.LANGUAGES) and len(ds["queries"]) == 21
    assert "NOT an independent set" in ds["independence"]


def test_dry_run_plan_counts_calls_and_tokens_from_the_dataset_with_no_network(monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("network touched")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    specs = EB.load_models()
    plan = EB.plan_run(specs, ML.load_dataset(), EB.load_abstention())
    assert len(plan["models"]) == 5 and all(m["embedding_calls"] == N_CALLS for m in plan["models"])
    assert plan["total_embedding_calls"] == 5 * N_CALLS
    assert plan["models"][0]["estimated_tokens"] > 0 and plan["models"][0]["estimated_cost_usd"] is None     # no price configured: unknown, not 0
    assert plan["questions"] == 70 and plan["documents"] == 49


def test_cli_dry_run_prints_calls_per_model_and_writes_nothing(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_embedding_benchmark.py")], capture_output=True, text=True, cwd=tmp_path, timeout=120,
                         env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT)})
    assert out.returncode == 0, out.stderr
    assert "DRY RUN" in out.stdout and f"calls={N_CALLS:4d}" in out.stdout and "openai/text-embedding-3-large" in out.stdout
    assert list(tmp_path.iterdir()) == []


# ------------------------------------------------------------------ hard refusal
def test_a_live_run_is_refused_without_the_governor_marker_before_any_provider_is_built(tmp_path):
    factory = Factory("openai")
    with pytest.raises(EB.BenchmarkRefused) as e:
        EB.run_embedding_benchmark(_specs(provider="openrouter"), factory, store_root=tmp_path / "idx", env={})
    assert "governor_marker_missing" in e.value.codes and "paid_flag_missing" in e.value.codes
    assert factory.built == [] and not (tmp_path / "idx").exists()


@pytest.mark.parametrize("drop", [EB.BUDGET_MARKER_ENV, EBUD.PAID_FLAG_ENV, EBUD.BUDGET_MARKER_ENV, EBUD.MAX_CALLS_ENV])
def test_every_approval_element_is_required(tmp_path, drop):
    env = {k: v for k, v in APPROVAL.items() if k != drop}
    factory = Factory("openai")
    with pytest.raises(EB.BenchmarkRefused):
        EB.run_embedding_benchmark(_specs(1, "openrouter"), factory, store_root=tmp_path / "i", env=env)
    assert factory.built == []


def test_an_invalid_marker_is_refused_and_its_value_never_appears(tmp_path):
    env = {**APPROVAL, EB.BUDGET_MARKER_ENV: "not-a-marker-SECRETVALUE"}
    with pytest.raises(EB.BenchmarkRefused) as e:
        EB.run_embedding_benchmark(_specs(1, "openrouter"), Factory("openai"), store_root=tmp_path / "i", env=env)
    assert "governor_marker_invalid" in e.value.codes and "SECRETVALUE" not in str(e.value)


def test_fake_provider_is_refused_unless_explicitly_allowed(tmp_path):
    factory = Factory()
    with pytest.raises(EB.BenchmarkRefused) as e:
        EB.run_embedding_benchmark(_specs(), factory, store_root=tmp_path / "i", allow_fake=False, env=APPROVAL)
    assert e.value.codes == ["fake_provider_not_allowed"] and factory.built == []
    with pytest.raises(EB.BenchmarkRefused):
        EB.run_embedding_benchmark([], factory, store_root=tmp_path / "i", allow_fake=True)


def test_planned_calls_above_the_approved_ceiling_are_refused_up_front(tmp_path):
    factory = Factory("openai")
    env = {**APPROVAL, EBUD.MAX_CALLS_ENV: str(N_CALLS - 1)}
    with pytest.raises(EB.BenchmarkRefused) as e:
        EB.run_embedding_benchmark(_specs(1, "openrouter"), factory, store_root=tmp_path / "i", env=env, clock=_ticker())
    assert e.value.codes == ["planned_calls_exceed_approved_ceiling"] and factory.built == []
    env2 = {**APPROVAL, EBUD.MAX_CALLS_ENV: str(N_CALLS)}
    res = EB.run_embedding_benchmark(_specs(1, "openrouter"), factory, store_root=tmp_path / "j", env=env2, clock=_ticker())
    assert len(res["models"]) == 1 and res["failed_models"] == [] and factory.built[0].doc_calls + factory.built[0].query_calls == N_CALLS
    assert res["label"].startswith("owner-approved governed run")           # approved path is labelled as such, still directional


def test_the_governor_guard_is_consulted_when_its_module_exists(tmp_path, monkeypatch):
    calls = []
    guard = types.SimpleNamespace(guard_paid_script=lambda script, **kw: calls.append((script, kw.get("category"))) or 2)
    pkg = types.ModuleType("src.llm.budget")
    pkg.script_guard = guard
    monkeypatch.setitem(sys.modules, "src.llm.budget", pkg)
    factory = Factory("openai")
    with pytest.raises(EB.BenchmarkRefused) as e:
        EB.run_embedding_benchmark(_specs(1, "openrouter"), factory, store_root=tmp_path / "i", env=APPROVAL)
    assert e.value.codes == ["governor_refused"] and calls == [("run_embedding_benchmark", "embedding")] and factory.built == []
    guard.guard_paid_script = lambda script, **kw: None
    res = EB.run_embedding_benchmark(_specs(1, "openrouter"), factory, store_root=tmp_path / "j", env=APPROVAL, clock=_ticker())
    assert len(res["models"]) == 1


def test_the_cli_refuses_a_live_run_without_approval(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_embedding_benchmark.py"), "--run", "--store-dir", str(tmp_path / "s")], capture_output=True,
                         text=True, cwd=tmp_path, timeout=120, env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT)})
    assert out.returncode == 2 and "REFUSED before any provider call" in out.stderr and "governor_marker_missing" in out.stderr
    assert not (tmp_path / "s").exists()


# ------------------------------------------------------------------ end to end with the fake provider
def test_end_to_end_result_schema_and_honest_labelling(tmp_path):
    res = _run(tmp_path)
    assert res["schema_version"] == EB.SCHEMA and [m["key"] for m in res["models"]] == ["m0", "m1"] and res["failed_models"] == []
    assert res["production_embedder_selected"] is False and res["retrieval_quality_claimed"] is False and res["selection"] is None
    assert res["label"].startswith("FAKE PROVIDER") and "NOT retrieval-quality evidence" in res["label"]
    assert "not independent" in res["independence_limitation"]
    assert res["datasets"]["multilingual"]["sha256"] == ML.FROZEN_DATASET_SHA256 and res["datasets"]["abstention"]["queries"] == 21
    m = res["models"][0]
    assert set(m["results"]) == set(ML.SLICES)
    overall = m["results"]["mixed_corpus"]["overall"]
    assert set(overall) >= {"n", "mrr", "recall@1", "recall@3", "recall@5", "recall@10", "ndcg@10"} and overall["n"] == 49
    assert set(m["results"]["mixed_corpus"]["by_question_language"]) == set(ML.LANGUAGES)
    assert 0.0 <= m["cross_language_retrieval_rate@5_mixed"] <= 1.0 and len(m["mrr_ci95_mixed"]) == 2
    assert m["floor_proposal"]["applied"] is False and set(m["floor_proposal"]["by_language"]) == set(ML.LANGUAGES)
    acc = m["accounting"]
    assert acc["calls"] == N_CALLS and acc["failed_calls"] == 0 and acc["tokens"] > 0 and acc["cost_usd"] is None and acc["latency_ms"]["p50"] > 0
    assert m["identity"]["provider"] == "fake" and m["index"] == {"version": 1, "reused_existing": False, "versions": [1]}
    assert [r["key"] for r in res["comparison_informational"]] == ["m0", "m1"]
    json.dumps(res)                                                          # fully serialisable


def test_runs_are_deterministic_including_the_bootstrap_seed(tmp_path):
    a = json.dumps(_run(tmp_path / "a"), sort_keys=True)
    b = json.dumps(_run(tmp_path / "b"), sort_keys=True)
    assert a == b
    c = _run(tmp_path / "c", seed=7)
    assert json.dumps(c, sort_keys=True) != a and c["seed"] == 7              # the seed changes only the interval
    assert c["models"][0]["results"] == json.loads(a)["models"][0]["results"]


def test_second_run_reuses_the_compatible_index_without_embedding_documents(tmp_path):
    _run(tmp_path)
    factory = Factory()
    second = _run(tmp_path, factory=factory)
    assert all(m["index"]["reused_existing"] and m["index"]["version"] == 1 for m in second["models"])
    assert [e.doc_calls for e in factory.built] == [0, 0]                      # no document spend on a re-run
    assert second["models"][0]["accounting"]["calls"] == 70                    # queries only


def test_an_index_of_another_embedder_is_never_reused_or_mixed(tmp_path):
    _run(tmp_path, specs=_specs(1))

    class Other(Factory):
        def __call__(self, spec):
            e = FakeProvider(spec, 48)
            e.version = "changed"                                              # same key and model, different recorded version
            self.built.append(e)
            return e
    res = _run(tmp_path, specs=_specs(1), factory=Other())
    assert res["models"] == [] and res["failed_models"][0]["codes"] == ["mismatch"]
    assert res["failed_models"][0]["accounting"]["calls"] == 0                 # refused before any embedding call


def test_controlled_reindex_builds_a_new_version_and_rollback_restores_the_previous(tmp_path):
    _run(tmp_path, specs=_specs(1))
    re_ = _run(tmp_path, specs=_specs(1), reindex=True)
    assert re_["models"][0]["index"] == {"version": 2, "reused_existing": False, "versions": [1, 2]}
    store = EB.ModelIndexStore(tmp_path / "idx")
    assert store.current_version("m0") == 2
    assert store.rollback("m0") == 1 and store.current_version("m0") == 1
    assert (tmp_path / "idx" / "m0" / "v0002" / "manifest.json").exists()       # versions are never deleted
    with pytest.raises(IndexIncompatibleError):
        store.rollback("m0")                                                   # nothing before v1
    after = _run(tmp_path, specs=_specs(1))
    assert after["models"][0]["index"]["version"] == 1 and after["models"][0]["index"]["reused_existing"]


def test_a_failed_reindex_leaves_the_previous_version_current(tmp_path):
    _run(tmp_path, specs=_specs(1))

    class Failing(FakeProvider):
        def embed_documents(self, texts):
            raise EmbeddingProviderError("provider_error")
    res = EB.run_embedding_benchmark(_specs(1), lambda s: Failing(s, 48), store_root=tmp_path / "idx", allow_fake=True, reindex=True, clock=_ticker())
    assert res["failed_models"][0]["codes"] == ["provider_error"] and res["failed_models"][0]["accounting"]["failed_calls"] == 1
    store = EB.ModelIndexStore(tmp_path / "idx")
    assert store.current_version("m0") == 1 and store.versions("m0") == [1]


def test_one_failing_model_does_not_hide_the_others_and_its_message_never_leaks(tmp_path):
    class Boom(FakeProvider):
        def embed_documents(self, texts):
            raise RuntimeError("sk-or-v1-LEAKED-detail")

    def factory(spec):
        return Boom(spec) if spec.key == "m0" else FakeProvider(spec)
    res = EB.run_embedding_benchmark(_specs(2), factory, store_root=tmp_path / "idx", allow_fake=True, clock=_ticker())
    assert [m["key"] for m in res["models"]] == ["m1"] and res["failed_models"][0]["key"] == "m0"
    assert "LEAKED" not in json.dumps(res) and "sk-or" not in json.dumps(res)


def test_paid_models_are_bounded_by_the_call_ceiling_even_after_approval(tmp_path):
    class Chatty(Factory):
        pass
    env = {**APPROVAL, EBUD.MAX_CALLS_ENV: str(N_CALLS)}
    factory = Chatty("openai")
    specs = _specs(2, "openrouter")
    with pytest.raises(EB.BenchmarkRefused):                                    # two paid models need 2x the calls
        EB.run_embedding_benchmark(specs, factory, store_root=tmp_path / "i", env=env)
    assert factory.built == []


def test_approval_secrets_never_appear_in_the_result(tmp_path):
    res = EB.run_embedding_benchmark(_specs(1, "openrouter"), Factory("openai"), store_root=tmp_path / "i", env=APPROVAL, clock=_ticker())
    assert "test-fixture-only" not in json.dumps(res)
