#!/usr/bin/env python
"""GKB-3 existing-alias inventory (P10C-B). READ-ONLY and metadata-only: opens the local legacy store immutably, prints counts and verdicts (no alias text), writes nothing to any store.
``--out`` is validated BEFORE any data is read (never inside data/ or evaluations/, exit 2); missing local data is a controlled exit 3. With ``--esco-plan`` it additionally assesses the
local ESCO English labels against an ISOLATED throwaway graph (planning only: nothing is imported, no source is approved)."""

from __future__ import annotations

import argparse
import collections
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.knowledge_foundation.pathsafe import output_is_protected  # noqa: E402


def inventory(root: Path) -> dict:
    from src.knowledge_foundation.normalize import detect_script, fold_label, normalize_label

    db = root / "data/knowledge/roles.db"
    manifest = json.loads((root / "data/source_manifest.json").read_text(encoding="utf-8"))
    manifest = manifest.get("sources", manifest)
    declared = {s["source_id"]: s.get("language") for s in manifest}
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro&immutable=1", uri=True)
    try:
        aliases = con.execute("select occupation_code, alias, source_id from occupation_aliases").fetchall()
        occ = {r[0]: (r[1], r[2]) for r in con.execute("select occupation_code, title, source_id from occupations")}
        cols = {t: [c[1] for c in con.execute(f"pragma table_info({t})")] for t in ("occupations", "occupation_aliases", "occupation_mappings")}
    finally:
        con.close()
    by_norm: dict[str, set] = collections.defaultdict(set)
    by_fold: dict[str, set] = collections.defaultdict(set)
    scripts: collections.Counter = collections.Counter()
    for code, alias, _src in aliases:
        n = normalize_label(alias)
        by_norm[n].add(code)
        by_fold[fold_label(n)].add(code)
        scripts[detect_script(alias) or "none"] += 1
    titles: dict[str, set] = collections.defaultdict(set)
    for code, (title, _s) in occ.items():
        titles[normalize_label(title)].add(code)
    shared = [len(v) for v in by_norm.values() if len(v) > 1]
    build = {}
    p = root / "data/normalized/build_metadata.json"
    if p.exists():
        build = json.loads(p.read_text(encoding="utf-8"))
    esco_files = sorted({c["relative_path"] for c in build.get("source_checksums", []) if "occupations_" in c.get("relative_path", "")})
    src_counts = collections.Counter(s for _c, _a, s in aliases)
    return {
        "schema": "gkb3_alias_inventory/1", "note": "Metadata only: counts and verdicts. No alias text. Produced read-only.",
        "legacy_tables": cols, "occupations": len(occ), "aliases": len(aliases), "alias_sources": dict(sorted(src_counts.items())),
        "occupations_by_source": dict(sorted(collections.Counter(s for _t, s in occ.values()).items())),
        "occupations_with_aliases": len({c for c, _a, _s in aliases}), "aliases_whose_occupation_is_missing": sum(1 for c, _a, _s in aliases if c not in occ),
        "exact_duplicate_rows": len(aliases) - len(set(aliases)), "distinct_raw_labels": len({a for _c, a, _s in aliases}), "distinct_normalized_labels_n1": len(by_norm),
        "distinct_folded_labels": len(by_fold), "normalized_labels_shared_by_several_occupations": len(shared), "max_occupations_sharing_one_label": max(shared) if shared else 0,
        "folded_labels_shared_by_several_occupations": sum(1 for v in by_fold.values() if len(v) > 1),
        "labels_empty_after_normalization": sum(1 for _c, a, _s in aliases if not normalize_label(a)), "aliases_equal_to_their_occupation_title": sum(
            1 for c, a, _s in aliases if c in occ and normalize_label(a) == normalize_label(occ[c][0])),
        "script_distribution": dict(sorted(scripts.items())), "non_ascii_labels": sum(1 for _c, a, _s in aliases if any(ord(ch) > 127 for ch in a)),
        "occupation_titles_shared_normalized": sum(1 for v in titles.values() if len(v) > 1), "occupations_sharing_a_normalized_title": sum(len(v) for v in titles.values() if len(v) > 1),
        "metadata_available_per_alias": {"language": False, "alias_type": False, "source_edition": False, "provenance": "source id only", "taxonomy_edition": False,
                                         "relationship": "occupation code (legacy canonical id)", "validity_dates": False},
        "language_attribution": {
            "method": "language is attributed ONLY where reliable source evidence exists; otherwise it stays UNKNOWN",
            "per_source": {s: {"aliases": n, "manifest_declared_language": declared.get(s), "evidence_files": esco_files if s == "esco" else [],
                               "attributable": "en by source file name (occupations_en.csv)" if s == "esco" and any(f.endswith("occupations_en.csv") for f in esco_files) else "unknown"}
                           for s, n in sorted(src_counts.items())},
            "aliases_attributable_to_a_language": sum(n for s, n in src_counts.items() if s == "esco" and any(f.endswith("occupations_en.csv") for f in esco_files)),
            "aliases_with_insufficient_language_information": sum(n for s, n in src_counts.items() if not (s == "esco" and any(f.endswith("occupations_en.csv") for f in esco_files))),
            "aliases_lacking_alias_type_source_edition_and_validity_information": len(aliases),
            "evidence_strength": "language is attributable to the SOURCE FILE the build consumed (a recorded raw input), not to each alias; alias type is not recorded (the legacy table cannot distinguish preferred, alternative and hidden labels)"},
    }


def esco_plan(root: Path) -> dict:
    import tests.conftest  # noqa: F401  (isolation: temporary database only)
    from src.knowledge_foundation.esco_adapter import plan_esco_labels, read_esco_labels_csv
    from src.knowledge_foundation.graph import OccupationGraph
    from src.knowledge_foundation.importers import read_esco_occupations_csv, read_isco_structure_csv, register_esco_isco
    from src.knowledge_foundation.registry import SourceRegistry
    from src.knowledge_foundation.seed import load_registry_baseline
    from src.knowledge_foundation.taxonomy import TaxonomyCatalogue
    from src.persistence import init_db, make_engine, make_session_factory

    raw = root / "data/raw"
    labels = raw / "ESCO dataset - v1.2.1 - classification - en - csv/occupations_en.csv"
    isco = raw / "ISCO-08 EN.csv"
    with tempfile.TemporaryDirectory() as d:
        sf = make_session_factory(make_engine(f"sqlite:///{d}/plan.db"))
        init_db(make_engine(f"sqlite:///{d}/plan.db"))
        TaxonomyCatalogue(sf).seed()
        reg = SourceRegistry(sf)
        load_registry_baseline(reg)
        g = OccupationGraph(sf)
        register_esco_isco(g, read_esco_occupations_csv(labels), read_isco_structure_csv(isco))
        rep = plan_esco_labels(g, read_esco_labels_csv(labels))
        return {"language": "en", "esco_edition": "1.2.1", "mode": "plan (nothing imported)", "rows": rep.rows, "occupations_matched": rep.occupations_matched,
                "skipped_unknown_occupation": rep.skipped_unknown_occupation, "labels_seen": rep.labels_seen,
                "source_state": {"esco": reg.get("esco")["approval_status"], "can_ingest": reg.can_ingest("esco")}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--esco-plan", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if args.out and output_is_protected(args.out, root):
        print("refusing to write inside data/ or evaluations/", file=sys.stderr)
        return 2
    try:
        out = inventory(root)
        if args.esco_plan:
            out["esco_english_label_plan"] = esco_plan(root)
    except (FileNotFoundError, sqlite3.OperationalError) as exc:
        print(f"inventory unavailable: required local knowledge data is missing ({Path(getattr(exc, 'filename', None) or 'unknown').name}); nothing was written", file=sys.stderr)
        return 3
    text = json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if args.out:
        dest = Path(args.out).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
