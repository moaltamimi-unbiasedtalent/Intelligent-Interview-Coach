"""Phase 7E provenance hotfix — worktree-aware, reproducible evaluation baseline.

Offline/deterministic: git is mocked, no network, no RAGAS judge, no paid call. Proves the
deterministic run records the FULL git SHA + git_dirty truthfully, degrades safely when git is
unavailable, and that the audit accepts a clean reviewed baseline but rejects a dirty one.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cli = _load("eval_ragas", "scripts/eval_ragas.py")
audit = _load("audit_ragas_evaluation", "scripts/audit_ragas_evaluation.py")

_FULL_SHA = "a" * 40


# --- provenance recording ------------------------------------------------------------

def test_clean_worktree_records_dirty_false(monkeypatch):
    def fake_git(*args):
        if args[:2] == ("rev-parse", "HEAD"):
            return _FULL_SHA
        if args[:2] == ("status", "--porcelain"):
            return ""  # clean
        return None
    monkeypatch.setattr(cli, "_git", fake_git)
    prov = cli._run_provenance()
    assert prov["git_sha"] == _FULL_SHA and len(prov["git_sha"]) == 40
    assert prov["git_sha_short"] == "aaaaaaa"
    assert prov["git_dirty"] is False
    assert prov["generated_at"] and prov["mode"] == "deterministic"


def test_dirty_worktree_records_dirty_true(monkeypatch):
    def fake_git(*args):
        if args[:2] == ("rev-parse", "HEAD"):
            return _FULL_SHA
        if args[:2] == ("status", "--porcelain"):
            return " M scripts/eval_ragas.py"  # dirty
        return None
    monkeypatch.setattr(cli, "_git", fake_git)
    assert cli._run_provenance()["git_dirty"] is True


def test_missing_git_is_handled_safely(monkeypatch):
    monkeypatch.setattr(cli, "_git", lambda *a: None)  # no git / not a repo
    prov = cli._run_provenance()
    assert prov["git_sha"] is None and prov["git_sha_short"] is None
    assert prov["git_dirty"] is None  # unknown, not False


# --- audit of the reviewed baseline --------------------------------------------------

def _write_baseline(tmp_path, *, dirty, sha=_FULL_SHA, dataset_hash="hash123"):
    p = tmp_path / "deterministic_baseline.json"
    p.write_text(json.dumps({
        "git_sha": sha, "git_sha_short": (sha[:7] if sha else None), "git_dirty": dirty,
        "ragas_version": "0.2.15", "generated_at": "2026-09-12T00:00:00Z",
        "dataset_hash": dataset_hash, "mode": "deterministic",
        "id_context_precision": {"mean": 0.676}, "id_context_recall": {"mean": 0.516},
    }), encoding="utf-8")
    return p


def test_audit_accepts_clean_reviewed_baseline(tmp_path, monkeypatch):
    p = _write_baseline(tmp_path, dirty=False)
    # Ancestry check will be UNKNOWN for a synthetic sha (tolerated).
    monkeypatch.setattr(audit, "_is_ancestor", lambda sha: "UNKNOWN")
    res = audit._reviewed_baseline_provenance("hash123", path=p)
    assert res["status"] == "PASS"
    assert res["git_dirty_false"] and res["full_git_sha"] and res["dataset_hash_matches_current"]


def test_audit_rejects_dirty_reviewed_baseline(tmp_path, monkeypatch):
    p = _write_baseline(tmp_path, dirty=True)
    monkeypatch.setattr(audit, "_is_ancestor", lambda sha: "UNKNOWN")
    res = audit._reviewed_baseline_provenance("hash123", path=p)
    assert res["status"] == "FAIL" and res["git_dirty_false"] is False


def test_audit_rejects_short_sha(tmp_path, monkeypatch):
    p = _write_baseline(tmp_path, dirty=False, sha="d892acc")  # short, pre-hotfix style
    monkeypatch.setattr(audit, "_is_ancestor", lambda sha: "UNKNOWN")
    res = audit._reviewed_baseline_provenance("hash123", path=p)
    assert res["status"] == "FAIL" and res["full_git_sha"] is False


def test_audit_rejects_dataset_hash_mismatch(tmp_path, monkeypatch):
    p = _write_baseline(tmp_path, dirty=False, dataset_hash="stalehash")
    monkeypatch.setattr(audit, "_is_ancestor", lambda sha: "UNKNOWN")
    res = audit._reviewed_baseline_provenance("hash123", path=p)
    assert res["status"] == "FAIL" and res["dataset_hash_matches_current"] is False


def test_audit_rejects_non_ancestor(tmp_path, monkeypatch):
    p = _write_baseline(tmp_path, dirty=False)
    monkeypatch.setattr(audit, "_is_ancestor", lambda sha: "FAIL")
    res = audit._reviewed_baseline_provenance("hash123", path=p)
    assert res["status"] == "FAIL"


def test_audit_missing_baseline(tmp_path):
    res = audit._reviewed_baseline_provenance("hash123", path=tmp_path / "nope.json")
    assert res["status"] == "MISSING" and res["present"] is False
