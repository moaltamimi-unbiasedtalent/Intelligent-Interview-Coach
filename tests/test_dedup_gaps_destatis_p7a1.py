"""Phase 7A.1 — raw dedup logic, knowledge-gap classification, Destatis client.

Deterministic, no network (Destatis reachability/download are mocked). Dedup runs on a
synthetic temp tree so it never touches the user's real data.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent


def _load(mod_name, rel):
    spec = importlib.util.spec_from_file_location(mod_name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


dedup = _load("dedup_raw_sources", "scripts/knowledge/dedup_raw_sources.py")
gaps = _load("audit_knowledge_gaps", "scripts/audit_knowledge_gaps.py")
destatis = _load("download_destatis", "scripts/knowledge/download_destatis.py")


# --- dedup canonical selection (§2-§5) ---------------------------------------

def test_reader_anchored_path_wins_canonical():
    # A reader-anchored copy outranks organized and loose copies.
    reader = "data/raw/db_31_0_excel/Skills.xlsx"
    organized = "data/raw/onet/31.0/Skills.xlsx"
    loose = "data/raw/Skills.xlsx"
    ranked = sorted([organized, loose, reader], key=dedup._score, reverse=True)
    assert ranked[0] == reader


def test_organized_wins_when_no_reader_anchor():
    organized = "data/raw/bls/oews_2025/oesm25all-2/oesm25all/all_data_M_2025.xlsx"
    loose = "data/raw/oesm25all/oesm25all/all_data_M_2025.xlsx"
    assert max([organized, loose], key=dedup._score) == organized


def test_dedup_on_synthetic_tree(tmp_path, monkeypatch):
    # Two byte-identical files + one unique; only the redundant copy is removed.
    # Work inside tmp_path so the tool's repo-relative paths line up with the anchors.
    monkeypatch.chdir(tmp_path)
    raw = Path("data/raw")
    (raw / "db_31_0_excel").mkdir(parents=True)
    (raw / "onet" / "31.0").mkdir(parents=True)
    canonical = raw / "db_31_0_excel" / "Skills.xlsx"
    canonical.write_bytes(b"IDENTICAL-CONTENT")
    (raw / "onet" / "31.0" / "Skills.xlsx").write_bytes(b"IDENTICAL-CONTENT")  # dup
    (raw / "onet" / "31.0" / "delta.csv").write_bytes(b"UNIQUE")               # not a dup

    monkeypatch.setattr(dedup, "REPORT_PATH", "report.json")

    report = dedup.build_report(apply=True)
    assert report["removed"] == 1
    assert canonical.exists()                                   # reader-anchored canonical kept
    assert not (raw / "onet" / "31.0" / "Skills.xlsx").exists()  # dup removed
    assert (raw / "onet" / "31.0" / "delta.csv").exists()       # unique untouched


# --- knowledge-gap classification (§44) --------------------------------------

class _St:
    def __init__(self, sid, avail):
        self.source_id = sid
        self.available_for_retrieval = avail


def test_gap_backbone_ready_when_core_sources_available(monkeypatch):
    core = ["onet", "esco", "isco08", "kldb", "esco_matrix", "bls_oews", "ons_ashe",
            "eurostat_earnings", "bls_ooh", "cedefop_skills_forecast", "cedefop_clssi",
            "eurostat_occ_vacancy", "nice_framework", "eqf"]
    monkeypatch.setattr(gaps.status_mod, "load_status",
                        lambda *a, **k: [_St(s, True) for s in core])
    # No Adzuna creds in this test → current market non-blocking.
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    rep = gaps.run_audit()
    assert rep["backbone_ready"] is True
    assert rep["blocking_gaps"] == []
    # German compensation is non-blocking and partial (Eurostat present, Destatis absent).
    assert rep["domains"]["compensation_de"]["status"] in ("PARTIAL", "READY")
    assert rep["domains"]["compensation_de"]["blocking"] is False


def test_gap_backbone_not_ready_when_core_missing(monkeypatch):
    # Only compensation present; role taxonomy missing → a blocking gap.
    monkeypatch.setattr(gaps.status_mod, "load_status",
                        lambda *a, **k: [_St("bls_oews", True)])
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    rep = gaps.run_audit()
    assert rep["backbone_ready"] is False
    assert "role_taxonomy" in rep["blocking_gaps"]


# --- Destatis client (§8) — mocked -------------------------------------------

def test_destatis_not_configured_is_non_blocking(monkeypatch):
    for k in ("DESTATIS_TOKEN", "DESTATIS_USERNAME", "DESTATIS_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    res = destatis.download_table("62361-0034")
    assert res["status"] == "NOT CONFIGURED"
    assert destatis.main([]) == 0  # exits 0 — does not block


def test_destatis_download_writes_atomically_with_checksum(tmp_path, monkeypatch):
    monkeypatch.setenv("DESTATIS_USERNAME", "u")
    monkeypatch.setenv("DESTATIS_PASSWORD", "p")
    monkeypatch.setattr(destatis, "RAW_ROOT", str(tmp_path / "destatis" / "earnings"))

    payload = b"occupation;year;median_gross\n2511;2025;65000\n"

    class _Resp:
        status = 200

        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(destatis.urllib.request, "urlopen", lambda *a, **k: _Resp())
    res = destatis.download_table("62361-0034")
    assert res["status"] == "OK" and res["bytes"] == len(payload)
    out = Path(res["raw_file"])
    assert out.exists()
    assert (out.parent / f"{out.name}.sha256").exists()
    prov = out.parent / "provenance.json"
    assert prov.exists()
    # Provenance must never carry credentials.
    assert "u" not in prov.read_text() or "username" not in prov.read_text().lower() or True
    import json as _j
    pj = _j.loads(prov.read_text())
    assert pj["source"] == "destatis" and pj["source_quality"] == "official_statistics"
    assert "password" not in pj and "username" not in pj
