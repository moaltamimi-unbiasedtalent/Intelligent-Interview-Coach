#!/usr/bin/env python
"""Build the canonical NORMALIZED knowledge layer from the real raw sources (Phase 7B).

One orchestrated, reproducible command that turns the acquired raw datasets under
``data/raw`` into provenance-aware canonical records (``src/copilot/knowledge/canonical.py``)
and writes them to ``data/normalized/`` as Parquet (JSONL fallback if pyarrow is absent).

Reuse-first: parsing is done by the proven ``local_readers`` (O*NET / ESCO / ISCO / KldB /
BLS OOH / BLS EP / OEWS / ONS ASHE / Cedefop / Eurostat / NICE / DigComp). This script only
ORCHESTRATES those readers through the canonical mappers in ``knowledge/normalize.py``,
assigns stable canonical occupation ids via a single ``CanonicalIdRegistry``, partitions the
facts into the normalized outputs, and emits reproducibility + quality reports.

It MUST NOT touch the runtime knowledge DBs or Chroma (that is Phase 7C). Outputs are
git-ignored (``data/normalized/*``).

Determinism (§4): record ids derive from source identity (never row/file/timestamp order);
every output list is sorted by a stable key before writing; ``retrieved_at`` is not stamped
at normalize time. Rebuilding from the same raw inputs yields equivalent records.

Usage:
    python scripts/knowledge/build_normalized_knowledge.py --all
    python scripts/knowledge/build_normalized_knowledge.py --source onet --source esco
    python scripts/knowledge/build_normalized_knowledge.py --all --validate-only
    python scripts/knowledge/build_normalized_knowledge.py --all --json-report
    python scripts/knowledge/build_normalized_knowledge.py --all --output-dir data/normalized
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# Make the repo root importable when run as a script from anywhere (scripts/knowledge/*).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.copilot.knowledge import canonical as C  # noqa: E402
from src.copilot.knowledge import local_readers as lr  # noqa: E402
from src.copilot.knowledge import normalize as N  # noqa: E402
from src.copilot.knowledge.manifest import load_manifest  # noqa: E402

PIPELINE_VERSION = "7B.1"
DEFAULT_OUTPUT_DIR = "data/normalized"

# KnowledgeFact.fact_type -> normalized output file name (§2). Only non-empty files are
# written. SKILL relations land in `occupation_skills` (the occupation↔skill relation IS the
# real normalized data; a deduplicated standalone skills vocabulary is a Phase 7C concern).
_FACT_OUTPUT = {
    C.FactType.SKILL: "occupation_skills",
    C.FactType.TECHNOLOGY_SKILL: "technology_skills",
    C.FactType.KNOWLEDGE: "knowledge_areas",
    C.FactType.TASK: "tasks",
    C.FactType.RESPONSIBILITY: "responsibilities",
    C.FactType.WORK_ACTIVITY: "work_activities",
    C.FactType.WORK_CONTEXT: "work_context",
    C.FactType.ABILITY: "abilities",
    C.FactType.EDUCATION: "education_training",
    C.FactType.TRAINING: "education_training",
    C.FactType.QUALIFICATION: "qualifications",
    C.FactType.CREDENTIAL: "credentials",
    C.FactType.COMPETENCY: "competencies_facts",
}


@dataclass
class SourceSpec:
    """One logical source: its reader, the record kind it yields, and its primary raw path."""

    name: str
    kind: str  # occupation | compensation | labour_market | competency
    reader: Callable
    raw_path: str  # repo-relative primary input (for raw_file + fingerprint)


def _sources() -> list[SourceSpec]:
    """The Phase 7B source registry (readers + their canonical raw paths)."""
    return [
        # Occupations / taxonomy / crosswalks / facts.
        SourceSpec("onet", "occupation", lr.read_onet, "data/raw/db_31_0_excel/Occupation Data.xlsx"),
        SourceSpec("esco", "occupation", lr.read_esco,
                   "data/raw/ESCO dataset - v1.2.1 - classification - en - csv/occupations_en.csv"),
        SourceSpec("isco08", "occupation", lr.read_isco,
                   "data/raw/ISCO-08 EN Structure and definitions.xlsx"),
        SourceSpec("kldb", "occupation", lr.read_kldb,
                   "data/raw/Systematisches-Verzeichnis-KldB-2020.xlsx"),
        SourceSpec("bls_ooh", "occupation", lr.read_ooh, "data/raw/OOH xml-compilation.xml"),
        SourceSpec("bls_projections", "occupation", lr.read_bls_ep_characteristics,
                   "data/raw/occupation.xlsx"),
        # Compensation.
        SourceSpec("bls_oews", "compensation", lr.read_oews,
                   "data/raw/oesm25nat/oesm25nat/national_M2025_dl.xlsx"),
        SourceSpec("ons_ashe", "compensation", lr.read_ashe,
                   "data/raw/ashetable142025provisional/"
                   "PROV - Occupation SOC20 (4) Table 14.1a   Weekly pay - Gross 2025.xlsx"),
        # Labour market.
        SourceSpec("bls_projections_lm", "labour_market", lr.read_bls_projections,
                   "data/raw/occupation.xlsx"),
        SourceSpec("cedefop_clssi", "labour_market", lr.read_cedefop_clssi,
                   "data/raw/2026_cedefop_labour_skills_shortage_index_clssi_dataset.xlsx"),
        SourceSpec("eurostat_occ_vacancy", "labour_market", lr.read_eurostat_vacancy,
                   "data/raw/jvs_a_isco3_r1$defaultview_spreadsheet.xlsx"),
        # Competency frameworks (kept separate from occupations; §28–31).
        SourceSpec("nice_framework", "competency", lr.read_nice_structured,
                   "data/raw/NICE Framework Components v2.2.0.xlsx"),
        SourceSpec("digcomp", "competency", lr.read_digcomp_structured,
                   "data/raw/DigComp 2.2 ESCO Skills Mapping.xlsx"),
    ]


# Map a logical source name to its manifest source_id (for governed provenance metadata).
_MANIFEST_ID = {"bls_projections_lm": "bls_projections"}


@dataclass
class BuildResult:
    counts: dict[str, int] = field(default_factory=dict)
    rejections: list[dict] = field(default_factory=list)
    source_versions: dict[str, str] = field(default_factory=dict)
    fingerprints: list[C.SourceFingerprint] = field(default_factory=list)
    per_source: dict[str, dict] = field(default_factory=dict)
    output_format: str = "parquet"
    unresolved_compensation: int = 0
    resolved_compensation: int = 0


def _manifest_meta() -> dict[str, dict]:
    out: dict[str, dict] = {}
    try:
        for e in load_manifest():
            out[e.source_id] = N.source_meta_from_manifest(e)
            out[f"_version:{e.source_id}"] = e.version
    except Exception:  # noqa: BLE001 - manifest is optional enrichment, never fatal
        pass
    return out


def _fingerprint(raw_path: str) -> C.SourceFingerprint | None:
    p = Path(raw_path)
    if not p.is_file():
        return None
    return C.SourceFingerprint(relative_path=raw_path, hash=C.sha256_file(p))


def build(selected: list[str], *, output_dir: str, validate_only: bool) -> BuildResult:
    """Run the readers, map to canonical records, and (unless validate-only) write outputs."""
    meta_by_id = _manifest_meta()
    registry = C.CanonicalIdRegistry()
    result = BuildResult()

    occupations: list[C.CanonicalOccupation] = []
    aliases: list[C.OccupationAlias] = []
    crosswalks: list[C.OccupationCrosswalk] = []
    source_records: list[C.SourceRecord] = []
    facts: list[C.KnowledgeFact] = []
    compensation: list[C.CompensationRecord] = []
    labour_market: list[C.LabourMarketRecord] = []
    competencies: list = []  # source Competency rows (framework-level)

    for spec in _sources():
        if selected and spec.name not in selected:
            continue
        manifest_id = _MANIFEST_ID.get(spec.name, spec.name)
        smeta = meta_by_id.get(manifest_id, {})
        version = meta_by_id.get(f"_version:{manifest_id}")
        raw_present = Path(spec.raw_path).is_file()
        fp = _fingerprint(spec.raw_path)
        if fp:
            result.fingerprints.append(fp)
        if version:
            result.source_versions[manifest_id] = version
        counts = {"occupations": 0, "aliases": 0, "crosswalks": 0, "facts": 0,
                  "compensation": 0, "labour_market": 0, "competencies": 0, "rejected": 0}

        try:
            produced = spec.reader()
        except Exception as exc:  # noqa: BLE001 - a bad source is reported, never crashes the build
            result.rejections.append({"source": spec.name, "severity": "critical",
                                      "reason": f"reader_failed:{type(exc).__name__}",
                                      "raw_file": spec.raw_path})
            counts["rejected"] += 1
            result.per_source[spec.name] = {"raw_present": raw_present, **counts}
            continue

        if spec.kind == "occupation":
            for occ in produced:
                try:
                    can, al, fa, xw, sr = N.occupation_to_canonical(
                        occ, registry, raw_file=spec.raw_path, source_meta=smeta)
                except Exception as exc:  # noqa: BLE001
                    result.rejections.append({"source": spec.name, "severity": "warning",
                                              "reason": f"map_failed:{type(exc).__name__}",
                                              "identifier": getattr(occ, "occupation_code", None)})
                    counts["rejected"] += 1
                    continue
                occupations.append(can); aliases.extend(al); facts.extend(fa)
                crosswalks.extend(xw); source_records.append(sr)
                counts["occupations"] += 1
                counts["aliases"] += len(al); counts["crosswalks"] += len(xw)
                counts["facts"] += len(fa)

        elif spec.kind == "compensation":
            for rec in produced:
                crec, rej = N.compensation_to_canonical(rec, registry, source_meta=smeta)
                if rej:
                    result.rejections.append({"source": spec.name, "severity": "warning",
                                              "reason": rej,
                                              "identifier": getattr(rec, "occupation_code", None)})
                    counts["rejected"] += 1
                    continue
                compensation.append(crec)
                counts["compensation"] += 1

        elif spec.kind == "labour_market":
            if spec.name == "bls_projections_lm":
                forecasts, openings = produced
                for f in forecasts:
                    labour_market.append(N.labour_forecast_to_canonical(f, source_meta=smeta))
                for o in openings:
                    labour_market.append(N.labour_openings_to_canonical(o, source_meta=smeta))
                counts["labour_market"] += len(forecasts) + len(openings)
            elif spec.name == "cedefop_clssi":
                for s in produced:
                    labour_market.append(N.labour_shortage_to_canonical(s, source_meta=smeta))
                counts["labour_market"] += len(produced)
            elif spec.name == "eurostat_occ_vacancy":
                for v in produced:
                    labour_market.append(N.labour_vacancy_to_canonical(v, source_meta=smeta))
                counts["labour_market"] += len(produced)

        elif spec.kind == "competency":
            for comp in produced:
                competencies.append(comp)
                source_records.append(N.competency_source_record(
                    comp, raw_file=spec.raw_path, source_meta=smeta))
                counts["competencies"] += 1

        result.per_source[spec.name] = {"raw_present": raw_present, **counts}

    # --- Deterministic dedup + ordering (§4/§50) --------------------------------------
    occupations = N.dedupe(sorted(occupations, key=lambda r: (r.occupation_id, r.source)),
                           key=lambda r: (r.occupation_id, r.source, r.source_occupation_id))
    aliases = N.dedupe(sorted(aliases, key=lambda r: (r.canonical_occupation_id, r.normalized_alias, r.source)),
                       key=lambda r: (r.canonical_occupation_id, r.normalized_alias, r.source))
    crosswalks = N.dedupe(sorted(crosswalks, key=lambda r: r.crosswalk_id), key=lambda r: r.crosswalk_id)
    facts = N.dedupe(sorted(facts, key=lambda r: r.fact_id), key=lambda r: r.fact_id)
    source_records = N.dedupe(sorted(source_records, key=lambda r: (r.record_type, r.source_record_id)),
                              key=lambda r: r.source_record_id)
    compensation = N.dedupe(sorted(compensation, key=lambda r: r.compensation_id),
                            key=lambda r: r.compensation_id)
    labour_market = N.dedupe(sorted(labour_market, key=lambda r: r.labour_market_id),
                             key=lambda r: r.labour_market_id)
    competencies = N.dedupe(sorted(competencies, key=lambda c: (c.source_id, c.framework, c.area, c.name)),
                            key=lambda c: (c.source_id, c.framework, c.area, c.name))

    # Linkage counted on the final (deduped) compensation set so reports match the outputs.
    result.resolved_compensation = sum(1 for r in compensation if r.occupation_id)
    result.unresolved_compensation = sum(1 for r in compensation if not r.occupation_id)

    # Partition facts by output file.
    fact_files: dict[str, list] = {}
    for f in facts:
        fact_files.setdefault(_FACT_OUTPUT.get(f.fact_type, "facts_other"), []).append(f)

    # --- Assemble the output plan -----------------------------------------------------
    outputs: dict[str, list] = {
        "occupations": occupations,
        "occupation_aliases": aliases,
        "occupation_crosswalks": crosswalks,
        "compensation": compensation,
        "labour_market": labour_market,
        "competencies": competencies,
        "source_records": source_records,
    }
    outputs.update(fact_files)

    for name, recs in outputs.items():
        result.counts[name] = len(recs)

    if validate_only:
        _validate_roundtrip(outputs)
        return result

    # --- Write outputs ----------------------------------------------------------------
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result.output_format = _write_outputs(outputs, out_dir)
    _validate_roundtrip(outputs)  # round-trip guard after writing (§51)

    # Registry + reports.
    registry.save(out_dir / "canonical_registry.json")
    _write_reports(result, registry, out_dir, selected)
    return result


def _write_outputs(outputs: dict[str, list], out_dir: Path) -> str:
    """Write each non-empty output as Parquet, falling back to JSONL if pyarrow is absent."""
    fmt = "parquet"
    for name, recs in outputs.items():
        if not recs:
            continue  # §2: no empty placeholders
        try:
            C.write_parquet(recs, out_dir / f"{name}.parquet")
        except C.ParquetUnavailableError:
            fmt = "jsonl"
            C.write_jsonl(recs, out_dir / f"{name}.jsonl")
    return fmt


def _validate_roundtrip(outputs: dict[str, list]) -> None:
    """Parquet round-trip validation on a bounded sample of each output (§51).

    Serializes a sample to an in-memory-equivalent temp file and reads it back, asserting the
    model re-validates. Skipped silently if pyarrow is unavailable (JSONL path is lossless)."""
    import tempfile

    model_of = {
        "occupations": C.CanonicalOccupation, "occupation_aliases": C.OccupationAlias,
        "occupation_crosswalks": C.OccupationCrosswalk, "compensation": C.CompensationRecord,
        "labour_market": C.LabourMarketRecord, "source_records": C.SourceRecord,
    }
    with tempfile.TemporaryDirectory() as d:
        for name, recs in outputs.items():
            model = model_of.get(name)
            if not recs or model is None:
                continue
            sample = recs[: min(50, len(recs))]
            p = Path(d) / f"{name}.parquet"
            try:
                C.write_parquet(sample, p)
            except C.ParquetUnavailableError:
                return
            back = C.read_parquet(p, model)
            if len(back) != len(sample):
                raise RuntimeError(f"round-trip row mismatch for {name}")


def _write_reports(result: BuildResult, registry: C.CanonicalIdRegistry,
                   out_dir: Path, selected: list[str]) -> None:
    meta = C.BuildMetadata(
        pipeline_version=PIPELINE_VERSION,
        source_versions=result.source_versions,
        source_checksums=result.fingerprints,
        record_counts=result.counts,
        normalized_dir=str(out_dir),
    )
    (out_dir / "build_metadata.json").write_text(meta.to_json(), encoding="utf-8")

    total = result.resolved_compensation + result.unresolved_compensation
    canon_report = {
        "pipeline_version": PIPELINE_VERSION,
        "sources_selected": selected or "all",
        "record_counts": result.counts,
        "per_source": result.per_source,
        "canonical_occupations": result.counts.get("occupations", 0),
        "registry_keys": len(registry.as_dict()),
        "compensation_occupation_linkage": {
            "resolved": result.resolved_compensation,
            "unresolved": result.unresolved_compensation,
            "unresolved_rate": round(result.unresolved_compensation / total, 4) if total else 0.0,
            "note": "Unresolved = no official code crosswalk to a canonical occupation yet "
                    "(no fuzzy title matching by design; cross-source linkage is 7B/7C).",
        },
        "output_format": result.output_format,
    }
    (out_dir / "canonicalization_report.json").write_text(
        json.dumps(canon_report, indent=2), encoding="utf-8")

    critical = [r for r in result.rejections if r.get("severity") == "critical"]
    warnings = [r for r in result.rejections if r.get("severity") != "critical"]
    rejections = {"total": len(result.rejections), "critical": len(critical),
                  "warning": len(warnings), "records": result.rejections}
    (out_dir / "normalization_rejections.json").write_text(
        json.dumps(rejections, indent=2), encoding="utf-8")
    if result.rejections:
        rej_dir = out_dir / "rejected_records"
        rej_dir.mkdir(parents=True, exist_ok=True)
        (rej_dir / "rejections.jsonl").write_text(
            "\n".join(json.dumps(r) for r in result.rejections) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the canonical normalized knowledge layer.")
    ap.add_argument("--source", action="append", default=[],
                    help="Logical source name (repeatable). Omit with --all for every source.")
    ap.add_argument("--all", action="store_true", help="Build every configured source.")
    ap.add_argument("--validate-only", action="store_true",
                    help="Parse+map+validate (round-trip) without writing outputs.")
    ap.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    ap.add_argument("--json-report", action="store_true",
                    help="Print the build report as JSON to stdout.")
    args = ap.parse_args(argv)

    all_names = [s.name for s in _sources()]
    if args.all or not args.source:
        selected: list[str] = []  # empty = all
    else:
        selected = args.source
        unknown = [s for s in selected if s not in all_names]
        if unknown:
            print(f"ERROR: unknown source(s): {unknown}", file=sys.stderr)
            print(f"       known: {all_names}", file=sys.stderr)
            return 2

    result = build(selected, output_dir=args.output_dir, validate_only=args.validate_only)

    report = {
        "mode": "validate-only" if args.validate_only else "build",
        "output_dir": args.output_dir,
        "output_format": result.output_format,
        "record_counts": result.counts,
        "per_source": result.per_source,
        "source_versions": result.source_versions,
        "rejections": {"total": len(result.rejections)},
        "compensation_linkage": {"resolved": result.resolved_compensation,
                                 "unresolved": result.unresolved_compensation},
    }
    if args.json_report:
        print(json.dumps(report, indent=2))
    else:
        print(f"NORMALIZED KNOWLEDGE BUILD ({report['mode']}) -> {args.output_dir}")
        print(f"  format: {result.output_format}")
        for name in sorted(result.counts):
            if result.counts[name]:
                print(f"  {name:<24} {result.counts[name]:>8}")
        print(f"  compensation linkage: resolved={result.resolved_compensation} "
              f"unresolved={result.unresolved_compensation}")
        print(f"  rejections: {len(result.rejections)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
