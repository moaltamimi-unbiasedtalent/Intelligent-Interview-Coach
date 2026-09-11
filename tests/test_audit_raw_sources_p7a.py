"""Raw-source readiness audit (Phase 7A).

Exercises ``scripts/audit_raw_sources.py`` against a SYNTHETIC manifest + inventory (never
the user's downloaded datasets), covering the READY state, the missing-backbone NOT-READY
state, machine-readable output and repo-relative path handling.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


from src.copilot.knowledge.manifest import SourceEntry

_AUDIT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "audit_raw_sources.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("audit_raw_sources", _AUDIT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["audit_raw_sources"] = mod
    spec.loader.exec_module(mod)
    return mod


audit = _load_audit_module()


def _entry(source_id, target, **kw):
    return SourceEntry(source_id=source_id, title=kw.pop("title", source_id.upper()),
                       publisher=kw.pop("publisher", "Pub"), storage_target=target,
                       coverage_areas=kw.pop("coverage_areas", ["occupations"]), **kw)


def _file(source_id, name, *, parseable=True, ready=True, sha="a" * 16, licence="CC BY 4.0"):
    return {
        "relative_path": f"data/raw/{name}", "filename": name, "source_id": source_id,
        "sha256": sha, "parseable": parseable,
        "ingestion_readiness": "ready" if ready else "review",
        "licensing_status": licence,
    }


def _patch(monkeypatch, entries, files):
    monkeypatch.setattr(audit.manifest_mod, "load_manifest", lambda *a, **k: entries)
    monkeypatch.setattr(audit, "_load_inventory", lambda *a, **k: {"files": files})
    monkeypatch.setattr(audit.status_mod, "load_status", lambda *a, **k: [])


def test_audit_ready_when_backbone_and_required_present(monkeypatch):
    entries = [
        _entry("onet", "structured_role"),
        _entry("bls_oews", "compensation", licence="Public domain"),
        _entry("wef_future_of_jobs", "vector"),          # optional narrative
        _entry("berufenet", "structured_role"),           # required target, NOT acquired
    ]
    files = [
        _file("onet", "onet/Occupation Data.xlsx"),
        _file("onet", "onet/Skills.xlsx"),
        _file("bls_oews", "bls/national.xlsx", licence="Public domain"),
        _file("wef_future_of_jobs", "WEF.pdf"),
    ]
    _patch(monkeypatch, entries, files)
    rep = audit.run_audit()

    assert rep["foundation_ready"] is True
    assert rep["backbone_ready"] is True
    assert rep["schema_validation"] == "PASS"
    assert rep["provenance_metadata"] == "PASS"
    # berufenet has a structured target but no files → optional/not-acquired, not a failure.
    assert "berufenet" not in rep["required_failed"]
    assert audit.main(["--json"]) == 0  # exits 0


def test_bespoke_reader_file_is_warn_not_fail(monkeypatch):
    # A present, fingerprinted file the generic heuristic marks not-parseable (e.g. OOH XML)
    # is WARN (needs a bespoke reader), and does NOT make the foundation NOT READY.
    entries = [_entry("onet", "structured_role"),
               _entry("bls_ooh", "structured_role", licence="Public domain")]
    files = [_file("onet", "onet/Occupation Data.xlsx"),
             _file("bls_ooh", "OOH.xml", parseable=False, ready=False)]
    _patch(monkeypatch, entries, files)
    rep = audit.run_audit()
    ooh = next(s for s in rep["sources"] if s["source_id"] == "bls_ooh")
    assert ooh["verdict"] == "WARN"
    assert not rep["required_failed"]
    assert rep["foundation_ready"] is True


def test_not_ready_when_occupation_backbone_missing(monkeypatch):
    # No onet/esco files at all → backbone missing → NOT READY, non-zero exit.
    entries = [_entry("bls_oews", "compensation", licence="Public domain"),
               _entry("onet", "structured_role")]
    files = [_file("bls_oews", "bls/national.xlsx", licence="Public domain")]  # onet absent
    _patch(monkeypatch, entries, files)
    rep = audit.run_audit()
    assert rep["backbone_ready"] is False
    assert rep["foundation_ready"] is False
    assert audit.main([]) == 1  # non-zero exit


def test_fail_when_required_file_has_no_checksum(monkeypatch):
    # Acquired but nothing present/fingerprinted → genuinely unusable → FAIL.
    entries = [_entry("onet", "structured_role"),
               _entry("esco", "structured_role")]
    files = [_file("onet", "onet/Occupation Data.xlsx"),
             _file("esco", "esco/occupations.csv", sha="")]  # no sha256
    _patch(monkeypatch, entries, files)
    rep = audit.run_audit()
    esco = next(s for s in rep["sources"] if s["source_id"] == "esco")
    assert esco["verdict"] == "FAIL"
    assert "esco" in rep["required_failed"]
    assert rep["foundation_ready"] is False


def test_licence_review_is_flagged_not_fatal(monkeypatch):
    entries = [_entry("onet", "structured_role"),
               _entry("kldb", "structured_role", licence_review_required=True, licence=None)]
    files = [_file("onet", "onet/Occupation Data.xlsx"),
             _file("kldb", "kldb/index.xlsx", licence="review required")]
    _patch(monkeypatch, entries, files)
    rep = audit.run_audit()
    assert "kldb" in rep["licence_review_needed"]
    assert rep["foundation_ready"] is True  # licence review is a flag, not a data blocker


def test_json_output_paths_are_repo_relative(monkeypatch):
    entries = [_entry("onet", "structured_role")]
    files = [_file("onet", "onet/Occupation Data.xlsx")]
    _patch(monkeypatch, entries, files)
    rep = audit.run_audit()
    # The audit never surfaces machine-absolute paths.
    import json
    blob = json.dumps(rep, default=str)
    assert "/Users/" not in blob and "C:\\" not in blob
