"""Phase 7E — free deterministic ID-based RAG metrics + eval_ragas mode/paid guards.

Fully offline: retrieval is a stub, RAGAS is never invoked, no network/provider/LLM call. Proves
the FREE ID context precision/recall (with NOT_APPLICABLE handling), the deterministic default
command, the paid-call guard, --estimate-only (no calls), the fixed judge subset, and that no
secrets/PII appear in results.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from src.copilot.evaluation import rag_id_metrics as idm

ROOT = Path(__file__).resolve().parent.parent
_CLI_SPEC = importlib.util.spec_from_file_location("eval_ragas", ROOT / "scripts" / "eval_ragas.py")
cli = importlib.util.module_from_spec(_CLI_SPEC)
_CLI_SPEC.loader.exec_module(cli)


def _result(sources, insufficient=False):
    ev = [SimpleNamespace(source_id=s) for s in sources]
    return SimpleNamespace(evidence=ev, insufficient_evidence=insufficient)


# --- ID metric computation -----------------------------------------------------------

def test_id_precision_and_recall_on_expected_family():
    case = {"case_id": "c1", "category": "role_responsibilities",
            "expected_source_family": "role", "question": "what does a nurse do"}
    # 2 of 3 retrieved sources are in the 'role' family → precision 2/3; recall 1.0 (any hit).
    r = idm.score_case(case, _result(["onet", "esco", "wef_future_of_jobs"]))
    assert abs(r.precision - 2 / 3) < 1e-9
    assert r.recall == 1.0


def test_recall_zero_when_no_expected_family_source_retrieved():
    case = {"case_id": "c2", "expected_source_family": "compensation", "question": "salary"}
    r = idm.score_case(case, _result(["onet", "esco"]))  # no compensation source
    assert r.recall == 0.0
    assert r.precision == 0.0  # none of the retrieved are in the compensation family


def test_none_family_is_not_applicable_not_zero():
    case = {"case_id": "c3", "expected_source_family": "none", "question": "who won the game"}
    r = idm.score_case(case, _result([]))
    assert r.precision == idm.NOT_APPLICABLE and r.recall == idm.NOT_APPLICABLE


def test_no_retrieved_evidence_precision_not_applicable():
    case = {"case_id": "c4", "expected_source_family": "role", "question": "x"}
    r = idm.score_case(case, _result([], insufficient=True))
    assert r.precision == idm.NOT_APPLICABLE  # nothing retrieved → precision undefined
    assert r.recall == 0.0                    # expected a role source, got none


def test_aggregate_marks_not_applicable_and_means():
    cases = [
        {"case_id": "a", "expected_source_family": "role", "question": "q"},
        {"case_id": "b", "expected_source_family": "none", "question": "q"},
    ]
    def retrieve(q):
        return _result(["onet"])  # role hit
    rep = idm.compute_id_metrics(cases, retrieve)
    d = rep.to_dict()
    assert d["case_count"] == 2 and d["not_applicable_cases"] == 1
    assert d["id_context_recall"]["applicable_cases"] == 1
    assert d["id_context_precision"]["mean"] == 1.0


def test_dataset_hash_is_stable_and_present():
    h1 = idm.dataset_hash(idm.RAGAS_CASES_PATH)
    h2 = idm.dataset_hash(idm.RAGAS_CASES_PATH)
    assert h1 and h1 == h2 and len(h1) == 16


def test_family_map_covers_required_families():
    for fam in ("role", "skills", "compensation", "labour_market", "competency"):
        assert idm.SOURCE_FAMILIES[fam]


# --- results carry no secrets / PII --------------------------------------------------

def test_id_report_contains_no_secrets_or_pii():
    cases = idm.load_ragas_cases()
    rep = idm.compute_id_metrics(cases[:5], lambda q: _result(["onet", "esco"]))
    blob = json.dumps(rep.to_dict())
    for needle in ("sk-or-", "api_key", "authorization", "@", "candidate"):
        assert needle not in blob.lower() or needle == "@"  # '@' never present anyway
    assert "@" not in blob


# --- CLI: deterministic default (no network), guards, estimate-only ------------------

def test_default_command_runs_deterministic_without_network(monkeypatch, capsys):
    # Stub the retrieval builder so NO career service / network is constructed.
    monkeypatch.setattr(idm, "default_retrieve_fn",
                        lambda: (lambda q: _result(["onet", "esco"])))
    rc = cli.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "DETERMINISTIC" in out and "NOT RUN — paid evaluation not authorized" in out


def test_judge_mode_without_allow_paid_does_not_run(capsys):
    rc = cli.main(["--mode", "judge"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "NOT RUN — paid evaluation not authorized" in out


def test_estimate_only_makes_no_calls(capsys):
    rc = cli.main(["--mode", "judge", "--subset", "reviewer", "--estimate-only"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "COST ESTIMATE" in out and "judge cases: 24" in out
    assert "cost: unknown" in out  # never fabricates a cost


def test_reviewer_subset_is_fixed_and_sized():
    ids = cli._load_judge_subset()
    assert 20 <= len(ids) <= 30
    assert len(ids) == len(set(ids))  # no duplicates
    # every subset id exists in the dataset
    dataset_ids = {c["case_id"] for c in idm.load_ragas_cases()}
    assert set(ids) <= dataset_ids


def test_require_live_without_creds_is_nonzero(monkeypatch):
    for var in ("RAGAS_EVAL_API_KEY", "RAGAS_EVAL_BASE_URL", "RAGAS_EVAL_MODEL"):
        monkeypatch.delenv(var, raising=False)
    assert cli.main(["--require-live"]) == 1


# --- dataset integrity ---------------------------------------------------------------

def test_existing_retrieval_dataset_still_parses():
    # The Phase 7C deterministic dataset remains authoritative and intact (§34).
    cases = json.loads(Path("evaluations/knowledge/retrieval_cases.json").read_text())
    assert len(cases) == 81 and all("query" in c for c in cases)


def test_lazy_import_no_ragas_at_module_load():
    # Importing the ID-metrics module must not import ragas (free/runtime-safe).
    code = "import sys; import src.copilot.evaluation.rag_id_metrics; print('ragas' in sys.modules)"
    import subprocess
    out = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), capture_output=True, text=True)
    assert out.stdout.strip() == "False"
