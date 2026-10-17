"""GKB-0: reproducible, READ-ONLY characterization of the existing Knowledge Base (stdlib only). Opens every SQLite store with ``mode=ro&immutable=1``, hashes files, and recomputes the
recorded raw-input checksums. It copies no source content, writes nothing to any store or evaluation artifact, and its output (counts, hashes, versions, verdicts) is metadata only."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

__all__ = ["build_baseline", "reproducibility_verdict", "RAW_PATTERNS"]

STORES = ("roles.db", "compensation.db", "competencies.db", "credentials.db", "labour_market.db")
# Which recorded raw-file paths belong to which built source (substring match, case-insensitive). Stated explicitly so the mapping itself is reviewable.
RAW_PATTERNS = {"onet": ("db_31_0_excel",), "esco": ("esco dataset",), "isco08": ("isco-08",), "kldb": ("kldb",), "bls_ooh": ("ooh xml",), "bls_projections": ("occupation.xlsx",),
                "bls_oews": ("oesm", "national_m20"), "ons_ashe": ("ashe",), "cedefop_clssi": ("clssi",), "eurostat_occ_vacancy": ("jvs_a_isco3",), "nice_framework": ("nice framework",),
                "digcomp": ("digcomp",)}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro&immutable=1", uri=True)


def _table_counts(path: Path) -> dict[str, int]:
    con = _ro(path)
    try:
        names = [r[0] for r in con.execute("select name from sqlite_master where type='table' order by name")]
        return {n: con.execute(f'select count(*) from "{n}"').fetchone()[0] for n in names}
    finally:
        con.close()


def reproducibility_verdict(source_id: str, *, built: bool, version: str | None, checksums: list[dict[str, Any]], manual: bool) -> dict[str, Any]:
    """REPRODUCIBLE needs (a) the source built into the normalized layer, (b) every recorded raw checksum present AND matching, (c) a PINNED version (not 'current release'/unknown). Any gap
    makes it PARTIALLY reproducible; a source that is not built, or whose raw files are missing or altered, is NOT reproducible. Nothing is assumed."""
    pinned = bool(version) and version.strip().lower() not in ("current release", "unknown", "detect-at-acquisition")
    gaps: list[str] = []
    if not built:
        return {"source_id": source_id, "verdict": "not_reproducible", "gaps": ["not built into the normalized layer"] + (["manual acquisition required"] if manual else [])}
    if not checksums:
        gaps.append("no raw checksum recorded")
    if any(not c["present"] for c in checksums):
        return {"source_id": source_id, "verdict": "not_reproducible", "gaps": ["a recorded raw input is missing"]}
    if any(not c["match"] for c in checksums):
        return {"source_id": source_id, "verdict": "not_reproducible", "gaps": ["a recorded raw input differs from its recorded checksum"]}
    if not pinned:
        gaps.append("version is not pinned ('current release'): a re-acquisition may yield a different edition")
    return {"source_id": source_id, "verdict": "reproducible" if not gaps else "partially_reproducible", "gaps": gaps, "checksummed_inputs": len(checksums)}


def build_baseline(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root)
    data = root / "data"
    kn = data / "knowledge"
    out: dict[str, Any] = {"schema": "gkb0_baseline/1", "note": "Metadata only: counts, hashes, versions and verdicts. No source content. Produced read-only."}
    manifest = json.loads((data / "source_manifest.json").read_text(encoding="utf-8"))
    sources = manifest.get("sources", manifest)
    status = {x["source_id"]: x for x in json.loads((data / "source_status.json").read_text(encoding="utf-8")).get("sources", [])}
    origins = json.loads((kn / "data_origins.json").read_text(encoding="utf-8")).get("origins", {})
    out["source_manifest"] = {"sha256": _sha256(data / "source_manifest.json"), "count": len(sources), "by_type": _count(s.get("source_type") for s in sources),
                              "by_origin": _count(("synthetic_only" if o and all(x == "synthetic_fixture" for x in o) else ("official_local" if "official_local" in o else ("authorised_manual" if "authorised_manual" in o else "other")))
                                                  for o in (origins.get(s["source_id"], []) for s in sources))}
    out["leftover_build_directories"] = sorted(p.name for p in kn.iterdir() if p.is_dir() and p.name.startswith(".")) if kn.exists() else []
    out["runtime_stores"] = {n: {"sha256": _sha256(kn / n), "bytes": (kn / n).stat().st_size, "tables": _table_counts(kn / n)} for n in STORES if (kn / n).exists()}
    norm = data / "normalized"
    rep = json.loads((norm / "canonicalization_report.json").read_text(encoding="utf-8")) if (norm / "canonicalization_report.json").exists() else {}
    out["normalized_layer"] = {"files": {p.name: {"sha256": _sha256(p), "bytes": p.stat().st_size} for p in sorted(norm.glob("*")) if p.is_file()}, "pipeline_version": rep.get("pipeline_version"),
                               "record_counts": rep.get("record_counts"), "per_source": {k: {m: v.get(m) for m in ("occupations", "aliases", "crosswalks", "relationships", "compensation", "labour_market")}
                                                                                         for k, v in (rep.get("per_source") or {}).items()}}
    bm = json.loads((norm / "build_metadata.json").read_text(encoding="utf-8")) if (norm / "build_metadata.json").exists() else {}
    rt = json.loads((kn / "build_metadata.json").read_text(encoding="utf-8")) if (kn / "build_metadata.json").exists() else {}
    verified: list[dict[str, Any]] = []
    for c in bm.get("source_checksums", []):
        p = root / c["relative_path"]
        present = p.is_file()
        verified.append({"path": c["relative_path"], "recorded_sha256": c["hash"], "present": present, "match": present and _sha256(p) == c["hash"]})
    out["build"] = {"normalized_pipeline_version": bm.get("pipeline_version"), "normalized_built_at": bm.get("built_at"), "normalized_git_commit": bm.get("git_commit"),
                    "runtime_pipeline_version": rt.get("runtime_pipeline_version"), "runtime_built_at": rt.get("built_at"), "runtime_git_commit": rt.get("git_commit"),
                    "source_versions": bm.get("source_versions"), "recorded_raw_checksums": len(verified), "verified_present": sum(v["present"] for v in verified),
                    "verified_match": sum(v["match"] for v in verified), "checksum_verification": verified}
    verdicts = []
    built = set((bm.get("source_versions") or {}).keys())
    for s in sorted(sources, key=lambda x: x["source_id"]):
        sid = s["source_id"]
        pats = RAW_PATTERNS.get(sid, ())
        cks = [v for v in verified if any(p in v["path"].lower() for p in pats)]
        ver = (bm.get("source_versions") or {}).get(sid) or status.get(sid, {}).get("detected_version") or s.get("version")
        verdicts.append(reproducibility_verdict(sid, built=sid in built, version=ver, checksums=cks, manual=bool(s.get("manual_acquisition_required"))))
    out["reproducibility"] = {"per_source": verdicts, "summary": _count(v["verdict"] for v in verdicts),
                              "rebuild_inputs_available": {"raw_files_recorded_and_matching": f"{out['build']['verified_match']}/{out['build']['recorded_raw_checksums']}",
                                                           "pipeline_versions_recorded": bool(bm.get("pipeline_version") and rt.get("runtime_pipeline_version")),
                                                           "normalized_git_commit_recorded": bool(bm.get("git_commit")), "runtime_git_commit_recorded": bool(rt.get("git_commit"))}}
    chroma = data / "chroma" / "chroma.sqlite3"
    if chroma.exists():
        con = _ro(chroma)
        try:
            cols = dict(con.execute("select c.name, count(e.id) from collections c left join segments s on s.collection=c.id left join embeddings e on e.segment_id=s.id group by c.name").fetchall())
        finally:
            con.close()
        out["vector_store"] = {"collections": cols, "total_chunks": sum(cols.values()), "sqlite_sha256": _sha256(chroma),
                               "note": "Chunk counts read with an immutable read-only connection; the store was not opened through the Chroma client."}
    from src.copilot import constants as C

    out["configuration_defaults"] = {k: getattr(C, k, None) for k in ("DEFAULT_EMBEDDING_PROVIDER", "DEFAULT_EMBEDDING_MODEL", "DEFAULT_RETRIEVAL_MODE", "DEFAULT_CHUNKING_STRATEGY", "RERANK_TOP_K")}
    cases = root / "evaluations" / "product_coverage" / "cases.json"
    out["evaluation_fixtures"] = {"product_coverage_cases": {"sha256": _sha256(cases), "cases": len(json.loads(cases.read_text(encoding="utf-8"))["cases"])} if cases.exists() else None,
                                  "note": "The product-coverage evaluator reads the gitignored runtime stores above; its committed summary predates the 2026-09-12 build."}
    out["limitations"] = ["Runtime stores and raw inputs are gitignored: the baseline records hashes and counts, not content.",
                          "Most sources are unpinned ('current release'): a re-acquisition may yield a different edition.",
                          "Raw checksums are recorded for 13 files covering 12 built sources; supplementary sources are built from governed fixtures or the narrative corpus.",
                          "The vector store changes whenever Admin knowledge operations run; its hash is a point-in-time value."]
    return out


def _count(items) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in items:
        out[str(i)] = out.get(str(i), 0) + 1
    return dict(sorted(out.items()))
