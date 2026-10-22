"""02B: the seven-language benchmark harness: frozen dataset, determinism, honest labelling, estimate and the paid-call refusal. Offline."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.copilot import embedding_budget as EB
from src.copilot.embeddings import BaseEmbedder, LocalHashEmbedder
from src.copilot.evaluation import multilingual_retrieval as ML

ROOT = Path(__file__).resolve().parents[1]
FULL_APPROVAL = {EB.PAID_FLAG_ENV: "1", EB.BUDGET_MARKER_ENV: "OD-BUDGET:test-fixture-only", EB.MAX_CALLS_ENV: "100"}


class FakePaid(BaseEmbedder):
    """A paid-provider stand-in: counts calls, never touches a network."""
    provider, model, version, dimensions = "openai", "fake-paid", "t-1", 64
    calls = 0

    def __init__(self):
        self._h = LocalHashEmbedder(64)

    def embed_documents(self, texts):
        FakePaid.calls += 1
        return self._h.embed_documents(texts)

    def embed_query(self, text):
        FakePaid.calls += 1
        return self._h.embed_query(text)


# ------------------------------------------------------------------ frozen dataset
def test_dataset_is_frozen_with_a_recorded_hash_and_the_expected_shape():
    assert ML.dataset_sha256() == ML.FROZEN_DATASET_SHA256
    ds = ML.load_dataset()
    assert ds["frozen"] is True and tuple(ds["languages"]) == ("en", "de", "fr", "es", "it", "pt", "nl")
    assert len(ds["topics"]) == 7 and len(ds["passages"]) == 49 and len(ds["queries"]) == 49
    for lang in ds["languages"]:
        assert sum(p["language"] == lang for p in ds["passages"]) == 7 and sum(q["language"] == lang for q in ds["queries"]) == 7
    assert len({p["id"] for p in ds["passages"]}) == 49 and "ru" not in {p["language"] for p in ds["passages"]}
    assert "NOT native-reviewed" in ds["description"] and "Not source evidence" in ds["description"]


def test_a_changed_dataset_is_refused(tmp_path):
    changed = tmp_path / "ds.json"
    changed.write_bytes(ML.DATASET_PATH.read_bytes().replace(b"salary", b"wage", 1))
    with pytest.raises(ML.DatasetIntegrityError):
        ML.load_dataset(changed)
    assert ML.load_dataset(changed, expected_sha256=None)["name"] == "multilingual_retrieval_v1"          # only an explicit opt-out reads a modified file


# ------------------------------------------------------------------ determinism and shape
def test_the_local_run_is_deterministic():
    a = ML.run_benchmark(LocalHashEmbedder())
    b = ML.run_benchmark(LocalHashEmbedder())
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_result_covers_every_mode_slice_k_and_language_with_valid_metrics():
    r = ML.run_benchmark(LocalHashEmbedder())
    assert set(r["results"]) == {"vector", "bm25", "rrf"}
    for mode in ML.MODES:
        assert set(r["results"][mode]) == set(ML.SLICES)
        for s in ML.SLICES:
            o = r["results"][mode][s]["overall"]
            assert o["n"] == 49 and all(0.0 <= o[k] <= 1.0 for k in ("recall@1", "recall@3", "recall@5", "recall@10", "mrr"))
            assert o["recall@1"] <= o["recall@3"] <= o["recall@5"] <= o["recall@10"]
            assert set(r["results"][mode][s]["by_question_language"]) == set(ML.LANGUAGES)
    same = r["results"]["bm25"]["same_language"]["overall"]
    cross = r["results"]["bm25"]["cross_language"]["overall"]
    assert same["mrr"] > cross["mrr"]                                                                     # a lexical method cannot bridge languages: the harness shows it


def test_cross_language_cases_never_contain_the_question_language_in_the_corpus():
    ds = ML.load_dataset()
    for lang in ML.LANGUAGES:
        corpus = ML._corpus_for("cross_language", lang, ds["passages"])
        assert corpus and all(p["language"] != lang for p in corpus) and len(corpus) == 42
        assert all(p["language"] == lang for p in ML._corpus_for("same_language", lang, ds["passages"]))


def test_metrics_functions_are_exact():
    assert ML._metrics(["a", "b", "c"], {"b"}, (1, 3))["mrr"] == 0.5
    m = ML._metrics(["x", "a", "y", "b"], {"a", "b"}, (1, 3, 5))
    assert (m["recall@1"], m["recall@3"], m["recall@5"], m["mrr"]) == (0.0, 0.5, 1.0, 0.5)
    assert ML._metrics([], {"a"}, (1,))["mrr"] == 0.0


# ------------------------------------------------------------------ honest labelling
def test_local_results_are_labelled_not_production_evidence_and_never_claim_semantic_pass():
    r = ML.run_benchmark(LocalHashEmbedder())
    assert r["label"] == "local embedder, NOT production quality evidence" == ML.LOCAL_LABEL
    assert r["production_quality_evidence"] is False and r["semantic_retrieval_passed"] is False
    assert "OD-BUDGET" in r["pending"] and "NOT been run" in r["pending"]
    assert r["embedder"]["lexical_only"] is True and r["embedder"]["provider"] == "local"
    text = json.dumps(r).lower()
    assert "semantic retrieval passed" not in text and "production quality: passed" not in text
    assert r["limitations"] and r["real_run_estimate"]["embedding_calls"] == 50


def test_estimate_gives_calls_tokens_and_a_cost_class_without_embedding():
    ds = ML.load_dataset()
    est = EB.estimate_embedding_run(document_texts=[p["text"] for p in ds["passages"]], query_texts=[q["text"] for q in ds["queries"]])
    assert est["document_calls"] == 1 and est["query_calls"] == 49 and est["embedding_calls"] == 50
    assert est["approx_tokens"] > 0 and est["cost_class"].startswith("negligible")
    big = EB.estimate_rebuild(chunk_count=14_087)
    assert big["embedding_calls"] == 221 and "cost_class" in big and "assumptions" in big
    assert EB.estimate_rebuild(chunk_count=0)["embedding_calls"] == 0
    assert EB.cost_class(10**9).startswith("high")


# ------------------------------------------------------------------ the paid-call refusal
@pytest.mark.parametrize("env,expected", [
    ({}, {"paid_flag_missing", "budget_marker_missing", "max_calls_missing"}),
    ({EB.PAID_FLAG_ENV: "1"}, {"budget_marker_missing", "max_calls_missing"}),
    ({EB.BUDGET_MARKER_ENV: "OD-BUDGET:test-fixture-only", EB.MAX_CALLS_ENV: "5"}, {"paid_flag_missing"}),
    ({EB.PAID_FLAG_ENV: "1", EB.BUDGET_MARKER_ENV: "approved!", EB.MAX_CALLS_ENV: "5"}, {"budget_marker_invalid"}),
    ({EB.PAID_FLAG_ENV: "1", EB.BUDGET_MARKER_ENV: "OD-BUDGET:test-fixture-only", EB.MAX_CALLS_ENV: "0"}, {"max_calls_invalid"}),
    ({EB.PAID_FLAG_ENV: "no", EB.BUDGET_MARKER_ENV: "OD-BUDGET:test-fixture-only", EB.MAX_CALLS_ENV: "x"}, {"paid_flag_missing", "max_calls_invalid"}),
])
def test_paid_embedder_is_refused_without_the_flag_and_the_budget_marker_and_makes_no_call(monkeypatch, env, expected):
    for k in (EB.PAID_FLAG_ENV, EB.BUDGET_MARKER_ENV, EB.MAX_CALLS_ENV):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    FakePaid.calls = 0
    with pytest.raises(EB.PaidEmbeddingRefused) as e:
        ML.run_benchmark(FakePaid())
    assert set(e.value.codes) == expected and FakePaid.calls == 0
    assert "OD-BUDGET:test" not in str(e.value)                                                           # the marker value is never echoed


def test_the_repository_environment_never_carries_the_approval(monkeypatch):
    import os
    for k in (EB.PAID_FLAG_ENV, EB.BUDGET_MARKER_ENV, EB.MAX_CALLS_ENV):
        assert k not in os.environ, k + " must never be set by the repository, tests or CI"
        assert k not in (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def test_an_approved_paid_run_is_bounded_by_the_ceiling(monkeypatch):
    for k, v in FULL_APPROVAL.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv(EB.MAX_CALLS_ENV, "10")
    FakePaid.calls = 0
    with pytest.raises(EB.PaidEmbeddingRefused) as e:
        ML.run_benchmark(FakePaid())                                                                     # needs 50 calls, ceiling is 10
    assert e.value.codes == ["budget_exhausted"] and FakePaid.calls == 10
    monkeypatch.setenv(EB.MAX_CALLS_ENV, "50")
    FakePaid.calls = 0
    r = ML.run_benchmark(FakePaid())
    assert FakePaid.calls == 50 and r["embedder"]["provider"] == "openai" and r["embedder"]["lexical_only"] is False
    assert r["semantic_retrieval_passed"] is False and r["production_quality_evidence"] is False and "OD-BUDGET" in r["pending"]
    assert "local embedder" not in r["label"]                                                            # a paid run is never mislabelled as the local one


def test_free_embedders_never_need_approval():
    e = LocalHashEmbedder()
    assert EB.guard_embedder(e, {}) is e and EB.is_free(e)


# ------------------------------------------------------------------ the script
def run_script(*args, env=None):
    import os
    clean = {k: v for k, v in os.environ.items() if k not in (EB.PAID_FLAG_ENV, EB.BUDGET_MARKER_ENV, EB.MAX_CALLS_ENV)}
    clean.update(env or {})
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "eval_multilingual_retrieval.py"), *args], cwd=ROOT, capture_output=True, text=True, env=clean)


def test_script_default_is_offline_labelled_and_writes_only_where_told(tmp_path):
    out = tmp_path / "r.json"
    p = run_script("--write", str(out))
    assert p.returncode == 0, p.stderr
    assert "local embedder, NOT production quality evidence" in p.stdout and "OD-BUDGET" in p.stdout
    assert json.loads(out.read_text())["label"] == ML.LOCAL_LABEL


def test_script_estimate_only_embeds_nothing():
    p = run_script("--estimate-only")
    assert p.returncode == 0 and '"embedding_calls": 50' in p.stdout and "ASK4MO_EMBEDDING_BUDGET_MARKER" in p.stdout and "awaits OD-BUDGET" in p.stdout


def test_script_refuses_a_configured_paid_embedder_without_approval(tmp_path):
    p = run_script("--embedder", "configured", env={"COPILOT_EMBEDDING_PROVIDER": "openai", "COPILOT_EMBEDDING_API_KEY": "sk-not-a-real-key-test",
                                                    "COPILOT_EMBEDDING_BASE_URL": "http://127.0.0.1:9/v1", "API_ENV": "development"})
    assert p.returncode == 2 and "REFUSED" in p.stderr and "paid_flag_missing" in p.stderr
    assert "sk-not-a-real-key-test" not in p.stdout + p.stderr


def test_script_refuses_a_configuration_a_hosted_environment_would_not_accept():
    p = run_script("--embedder", "configured", env={"COPILOT_EMBEDDING_PROVIDER": "local", "API_ENV": "production"})
    assert p.returncode == 2 and "hash_embedder_not_allowed" in p.stderr
