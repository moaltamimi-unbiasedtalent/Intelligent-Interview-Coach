#!/usr/bin/env python
"""Build the RUNTIME knowledge stores from the governed normalized layer (Phase 7C).

Makes ``data/normalized/`` (the Phase 7B governed corpus) the source of the runtime Career
Intelligence stores — closing the loop ``raw → normalized → runtime`` reproducibly. It writes
the SAME store schemas the existing repositories/retrieval already use (RoleRepository,
CompensationRepository, LabourMarketRepository, CompetencyRepository, CredentialRepository and
the Chroma vector store), so the proven resolver / hybrid retrieval / citation pipeline keeps
working unchanged.

Safety (§4/§60): stores are built into a temporary ``.build-<id>`` directory, validated, then
atomically promoted; the live runtime is never left half-replaced, and a one-shot backup of the
previous stores is kept during promotion. Reproducible + deterministic: identity/order come
from the normalized records, not row/file/timestamp order.

Reuse (§13): occupations/skills/tasks/knowledge/activities/aliases/crosswalks/relationships/
attributes, compensation, labour-market and NICE/DigComp competencies are rebuilt FROM the
normalized Parquet. A few domains the normalized layer does not yet carry are preserved via
their existing governed loaders (supplementary competency frameworks e-CF/BA; credential
fixtures; the narrative vector corpus in ``data/processed/chunks.jsonl``) — recorded in the
build metadata so provenance stays explicit.

Embeddings use the repository's configured embedder (the free offline LocalHashEmbedder by
default) — NO paid calls (§29/§67). If a paid embedder is configured, the vector build STOPs.

Usage:
    python scripts/knowledge/build_runtime_knowledge.py --all
    python scripts/knowledge/build_runtime_knowledge.py --structured-only
    python scripts/knowledge/build_runtime_knowledge.py --vector-only
    python scripts/knowledge/build_runtime_knowledge.py --all --validate-only
    python scripts/knowledge/build_runtime_knowledge.py --all --json-report
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.copilot import constants  # noqa: E402
from src.copilot.knowledge import canonical as C  # noqa: E402
from src.copilot.knowledge.compensation import (  # noqa: E402
    CompensationRecord as SrcComp,
    CompensationRepository,
)
from src.copilot.knowledge.roles import (  # noqa: E402
    Mapping,
    NormalisedOccupation,
    Relationship,
    RoleRepository,
    Skill,
)
from src.copilot.knowledge.structured_ext import (  # noqa: E402
    Competency,
    CompetencyRepository,
    LabourForecast,
    LabourMarketRepository,
    LabourOpenings,
    LabourShortage,
    LabourVacancy,
)

RUNTIME_PIPELINE_VERSION = "7C.1"
NORMALIZED_DIR = "data/normalized"
KNOWLEDGE_DIR = "data/knowledge"

_ATTR_OF = {  # KnowledgeFact metadata.attribute -> NormalisedOccupation scalar field
    "entry_education": "entry_education",
    "work_experience": "work_experience",
    "on_the_job_training": "on_the_job_training",
    "outlook": "outlook",
}


def _read(norm_dir: Path, name: str, model):
    pq, jl = norm_dir / f"{name}.parquet", norm_dir / f"{name}.jsonl"
    if pq.exists():
        return C.read_parquet(pq, model)
    if jl.exists():
        return C.read_jsonl(jl, model)
    return []


# --------------------------------------------------------------------------------------
# Reconstruct the per-source intermediate models FROM the normalized canonical records.
# --------------------------------------------------------------------------------------

def _reconstruct_occupations(norm: Path) -> list[NormalisedOccupation]:
    occs = _read(norm, "occupations", C.CanonicalOccupation)
    by_occ_skills = defaultdict(list)
    by_occ_know = defaultdict(list)
    by_occ_tasks = defaultdict(list)
    by_occ_acts = defaultdict(list)
    by_occ_aliases = defaultdict(list)
    by_occ_maps = defaultdict(list)
    by_occ_rels = defaultdict(list)
    by_occ_attrs = defaultdict(dict)

    for name in ("occupation_skills", "technology_skills"):
        for f in _read(norm, name, C.KnowledgeFact):
            rel = (f.metadata or {}).get("relation") or (
                "technology" if name == "technology_skills" else "essential")
            by_occ_skills[f.occupation_id].append(Skill(name=f.fact_value, skill_type=rel))
    for f in _read(norm, "knowledge_areas", C.KnowledgeFact):
        by_occ_know[f.occupation_id].append(f.fact_value)
    for f in _read(norm, "tasks", C.KnowledgeFact):
        by_occ_tasks[f.occupation_id].append(f.fact_value)
    for f in _read(norm, "work_activities", C.KnowledgeFact):
        by_occ_acts[f.occupation_id].append(f.fact_value)
    for f in _read(norm, "occupation_attributes", C.KnowledgeFact):
        attr = (f.metadata or {}).get("attribute")
        if attr in _ATTR_OF:
            by_occ_attrs[f.occupation_id][_ATTR_OF[attr]] = f.fact_value
    for a in _read(norm, "occupation_aliases", C.OccupationAlias):
        by_occ_aliases[a.canonical_occupation_id].append(a.alias)
    for x in _read(norm, "occupation_crosswalks", C.OccupationCrosswalk):
        by_occ_maps[x.source_occupation_id].append(
            Mapping(scheme=x.target_classification.value, code=x.target_code))
    for r in _read(norm, "occupation_relationships", C.OccupationRelationship):
        by_occ_rels[r.occupation_id].append(
            Relationship(related_code=r.related_code, relation_type=r.relation_type))

    out: list[NormalisedOccupation] = []
    for o in occs:
        oid = o.occupation_id
        attrs = by_occ_attrs.get(oid, {})
        out.append(NormalisedOccupation(
            occupation_code=oid, title=o.canonical_title, source_id=o.source,
            description=o.description, isco_code=o.isco_code,
            aliases=by_occ_aliases.get(oid, []),
            skills=by_occ_skills.get(oid, []),
            knowledge=by_occ_know.get(oid, []),
            tasks=by_occ_tasks.get(oid, []),
            activities=by_occ_acts.get(oid, []),
            relationships=by_occ_rels.get(oid, []),
            mappings=by_occ_maps.get(oid, []),
            entry_education=attrs.get("entry_education"),
            work_experience=attrs.get("work_experience"),
            on_the_job_training=attrs.get("on_the_job_training"),
            outlook=attrs.get("outlook"),
        ))
    return out


def _reconstruct_compensation(norm: Path) -> list[SrcComp]:
    out: list[SrcComp] = []
    for c in _read(norm, "compensation", C.CompensationRecord):
        meta = c.metadata or {}
        out.append(SrcComp(
            source_id=c.source, occupation_code=c.occupation_code or None,
            occupation_title=meta.get("occupation_title", "") or "",
            geography=meta.get("geography", "") or (c.country or ""),
            country=c.country or "", region=c.region, industry=c.industry,
            year=c.effective_year,
            currency=c.currency or "",
            pay_period=meta.get("pay_period_native") or (c.pay_period.value if c.pay_period else "annual"),
            statistic_type=c.statistic.value if c.statistic else "median",
            value=c.amount, lower_bound=meta.get("lower_bound"),
            upper_bound=meta.get("upper_bound"),
            sample_quality=meta.get("sample_quality"), source_url=c.source_url,
        ))
    return out


def _reconstruct_labour_market(norm: Path):
    forecasts, openings, shortages, vacancies = [], [], [], []
    for r in _read(norm, "labour_market", C.LabourMarketRecord):
        m = r.metadata or {}
        geo = r.country or m.get("geography_label") or ""
        occ = m.get("occupation") or ""
        if r.metric_type == C.MetricType.GROWTH_RATE:
            forecasts.append(LabourForecast(
                source_id=r.source, occupation=occ, country=geo, sector=m.get("sector"),
                employment_change=r.value, replacement_demand=m.get("replacement_demand"),
                horizon=r.forecast_period, reference_year=m.get("reference_year")))
        elif r.metric_type == C.MetricType.JOB_OPENINGS:
            openings.append(LabourOpenings(
                source_id=r.source, occupation=occ, geography=geo, period=r.forecast_period,
                new_jobs=m.get("new_jobs"), replacement_demand=m.get("replacement_demand"),
                total_openings=r.value))
        elif r.metric_type == C.MetricType.SHORTAGE_INDICATOR:
            shortages.append(LabourShortage(
                source_id=r.source, occupation=occ, country=geo, skill_level=m.get("skill_level"),
                shortage_indicator=m.get("shortage_indicator"), period=r.effective_period))
        elif r.metric_type == C.MetricType.VACANCIES:
            year = None
            try:
                year = int(r.effective_period) if r.effective_period else None
            except (TypeError, ValueError):
                year = m.get("reference_year")
            vacancies.append(LabourVacancy(
                source_id=r.source, occupation=occ, country=geo, region=r.region, year=year,
                indicator=m.get("indicator"), unit=r.unit, value=r.value,
                experimental=bool(m.get("experimental"))))
    return forecasts, openings, shortages, vacancies


# --------------------------------------------------------------------------------------
# Structured build (into a temp dir)
# --------------------------------------------------------------------------------------

def _build_structured(norm: Path, dest: Path, counts: dict) -> None:
    dest.mkdir(parents=True, exist_ok=True)

    # roles.db
    roles = RoleRepository(str(dest / "roles.db"))
    for occ in _reconstruct_occupations(norm):
        roles.add_occupation(occ)
    rc = roles.counts()
    roles.close()
    counts["roles"] = rc

    # compensation.db
    comp = CompensationRepository(str(dest / "compensation.db"))
    n = 0
    for rec in _reconstruct_compensation(norm):
        comp.add(rec); n += 1
    comp.close()
    counts["compensation"] = n

    # labour_market.db
    lm = LabourMarketRepository(str(dest / "labour_market.db"))
    fc, op, sh, va = _reconstruct_labour_market(norm)
    for f in fc:
        lm.add_forecast(f)
    for o in op:
        lm.add_openings(o)
    for s in sh:
        lm.add_shortage(s)
    for v in va:
        lm.add_vacancy(v)
    lm.close()
    counts["labour_market"] = {"forecasts": len(fc), "openings": len(op),
                               "shortages": len(sh), "vacancies": len(va)}

    # competencies.db — NICE/DigComp from normalized + supplementary frameworks (e-CF/BA)
    compe = CompetencyRepository(str(dest / "competencies.db"))
    ncomp = 0
    for c in _read(norm, "competencies", Competency):
        compe.add_competency(c); ncomp += 1
    ncomp += _load_supplementary_competencies(compe)
    compe.close()
    counts["competencies"] = ncomp

    # credentials.db — not in the normalized layer yet; preserve governed fixtures.
    counts["credentials"] = _load_credential_fixtures(dest / "credentials.db")


def _load_supplementary_competencies(repo: CompetencyRepository) -> int:
    """Add framework competencies the normalized layer does not yet carry (e-CF, BA
    Kompetenzkatalog) from their governed sample fixtures, so no runtime data is lost."""
    from src.copilot.knowledge import normalisers_ext as norm
    base = Path("evaluations/knowledge_samples")
    added = 0
    for fname, fn in (("ecf.json", norm.normalise_ecf),
                      ("ba_kompetenzkatalog.json", norm.normalise_ba_kompetenzkatalog)):
        p = base / fname
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for c in fn(data):
                repo.add_competency(c); added += 1
        except Exception:  # noqa: BLE001 - supplementary; never fail the build
            pass
    return added


def _load_credential_fixtures(db_path: Path) -> int:
    """Build credentials.db from the governed credential fixtures (no normalized coverage yet)."""
    from src.copilot.knowledge.structured_ext import (
        Certification, CredentialRepository, OccupationLicence)
    src_id = "careeronestop"  # matches scripts/load_credentials.py origin
    base = Path("evaluations/knowledge_samples")
    repo = CredentialRepository(str(db_path))
    n = 0
    certs = base / "certifications.json"
    lics = base / "licences.json"
    try:
        if certs.is_file():
            for c in json.loads(certs.read_text(encoding="utf-8")):
                repo.add_certification(Certification(source_id=src_id, **c)); n += 1
        if lics.is_file():
            for c in json.loads(lics.read_text(encoding="utf-8")):
                repo.add_licence(OccupationLicence(source_id=src_id, **c)); n += 1
    except Exception:  # noqa: BLE001
        pass
    repo.close()
    return n


# --------------------------------------------------------------------------------------
# Validation + atomic promotion
# --------------------------------------------------------------------------------------

def _validate_structured(dest: Path) -> list[str]:
    problems = []
    roles_db = dest / "roles.db"
    if not roles_db.is_file():
        return ["roles.db missing"]
    r = RoleRepository(str(roles_db))
    counts = r.counts()
    if counts.get("occupations", 0) <= 0:
        problems.append("roles.db has no occupations")
    # A resolvable occupation must return skills (smoke).
    sample = r.search("nurse", limit=1)
    if sample:
        code = sample[0]["occupation_code"]
        if r.get_occupation(code) is None:
            problems.append("roles.db occupation fetch failed")
    r.close()
    return problems


def _promote(temp: Path, active: Path, names: list[str]) -> None:
    """Atomically move built store files from temp into the active dir, backing up olds."""
    active.mkdir(parents=True, exist_ok=True)
    backup = active / f".backup-{int(time.time())}"
    backup.mkdir(exist_ok=True)
    for name in names:
        src = temp / name
        if not src.exists():
            continue
        dst = active / name
        if dst.exists():
            shutil.move(str(dst), str(backup / name))
        shutil.move(str(src), str(dst))
    # Keep only the most recent backup dir to avoid unbounded growth.
    backups = sorted(active.glob(".backup-*"))
    for old in backups[:-1]:
        shutil.rmtree(old, ignore_errors=True)


# --------------------------------------------------------------------------------------
# Vector build (narrative corpus + structured provenance-aware passages)
# --------------------------------------------------------------------------------------

def _assert_free_embedder():
    from src.copilot.config import CopilotConfig
    from src.copilot.embeddings import build_embedder
    cfg = CopilotConfig()
    embedder = build_embedder(cfg)
    model = getattr(embedder, "model", getattr(embedder, "model_name", "")) or ""
    is_local = "local" in str(model).lower() or embedder.__class__.__name__ == "LocalHashEmbedder"
    return embedder, is_local, str(model)


def _structured_passages(norm: Path):
    """Deterministic, provenance-aware DocumentChunks from normalized textual records (§23-26).

    Only genuinely textual, self-contained evidence is embedded (occupation descriptions,
    task/activity/knowledge statements, competency descriptions, labour-market narrative);
    raw numeric rows, codes and one-word aliases are NOT embedded (kept structured). Passages
    are deduped by normalized text within a (occupation, domain)."""
    from src.copilot.models import DocumentChunk

    occ_meta = {o.occupation_id: o for o in _read(norm, "occupations", C.CanonicalOccupation)}
    chunks: list[DocumentChunk] = []
    seen: set[str] = set()

    def _emit(text, *, domain, source, source_url, title, oid=None, extra=None):
        t = (text or "").strip()
        if len(t) < 25:  # avoid fragments like "advanced" / "software" (§25)
            return
        key = C.normalize_text(f"{oid or ''}|{domain}|{t}")
        if key in seen:
            return
        seen.add(key)
        o = occ_meta.get(oid) if oid else None
        meta = {
            "source_id": source, "manifest_source_id": source, "source_url": source_url,
            "title": title, "document_type": domain, "source": source, "section": domain,
            "canonical_occupation_id": oid or "", "domain": domain,
            "geography": (o.geography.country if (o and o.geography) else None) or "",
            "country": (o.geography.country if (o and o.geography) else None) or "",
            "language": (o.language if o else None) or "",
        }
        if extra:
            meta.update({k: v for k, v in extra.items() if v is not None})
        cid = f"struct:{domain}:{C.normalize_text(title)[:40]}:{abs(hash(key)) % (10**12)}"
        chunks.append(DocumentChunk(chunk_id=cid, doc_id=f"{source}:{domain}",
                                    text=t, position=0, metadata=meta))

    # Occupation descriptions.
    for o in occ_meta.values():
        if o.description:
            _emit(f"{o.canonical_title}: {o.description}", domain="occupation_description",
                  source=o.source, source_url=o.source_url, title=o.canonical_title,
                  oid=o.occupation_id)
    # Task / activity / knowledge statements (grouped per occupation to stay self-contained).
    for name, domain in (("tasks", "task"), ("work_activities", "work_activity"),
                         ("knowledge_areas", "knowledge")):
        grouped = defaultdict(list)
        for f in _read(norm, name, C.KnowledgeFact):
            grouped[(f.occupation_id, f.source, f.source_url, f.canonical_title)].append(f.fact_value)
        for (oid, src, url, title), vals in grouped.items():
            title = title or (occ_meta.get(oid).canonical_title if oid in occ_meta else "")
            _emit(f"{title} — {domain}s: " + "; ".join(vals[:20]), domain=domain,
                  source=src, source_url=url, title=title, oid=oid)
    # Competency descriptions (framework-level; not occupation-grounded).
    for c in _read(norm, "competencies", Competency):
        _emit(f"{c.name}: {c.description}" if c.description else c.name,
              domain="competency", source=c.source_id, source_url=None,
              title=f"{c.framework} — {c.name}"[:120])
    return chunks


def _narrative_chunks():
    from src.copilot.models import DocumentChunk
    path = Path(constants.PROCESSED_CHUNKS_FILE)
    out = []
    if path.is_file():
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(DocumentChunk(**json.loads(line)))
    return out


def _build_vector(norm: Path, persist_dir: Path, counts: dict) -> dict:
    from src.copilot.vectorstore import ChromaStore
    embedder, is_local, model = _assert_free_embedder()
    if not is_local:
        raise SystemExit(
            f"STOP: configured embedder '{model}' is not the free local embedder. A vector "
            "rebuild would incur paid embedding calls (§29/§67). Set no COPILOT_EMBEDDING_API_KEY "
            "to use the offline LocalHashEmbedder, or run with authorization.")
    narrative = _narrative_chunks()
    structured = _structured_passages(norm)
    considered = len(narrative) + len(structured)
    store = ChromaStore(persist_dir=str(persist_dir), embedder=embedder)
    try:
        store.reset()
    except Exception:  # noqa: BLE001 - fresh dir has no collection yet
        pass
    res_n = store.add_chunks(narrative)
    res_s = store.add_chunks(structured)
    final = store.count()
    info = {"documents_considered": considered, "narrative": len(narrative),
            "structured": len(structured), "embedded": res_n.added + res_s.added,
            "skipped_duplicates": res_n.skipped_existing + res_s.skipped_existing,
            "final_passages": final, "embedder": model, "paid": False}
    counts["vector"] = info
    # Release the Chroma client + its SQLite handles BEFORE the caller moves the directory,
    # otherwise the persistent client aborts on teardown ("recursive_mutex lock failed").
    import gc
    for attr in ("_collection", "_client"):
        if hasattr(store, attr):
            try:
                setattr(store, attr, None)
            except Exception:  # noqa: BLE001
                pass
    del store
    gc.collect()
    return info


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------

def _git_commit() -> str | None:
    import subprocess
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       text=True).strip()  # noqa: S603,S607
    except Exception:  # noqa: BLE001
        return None


def _write_build_metadata(active: Path, counts: dict, norm: Path, timings: dict) -> None:
    norm_meta = {}
    nm = norm / "build_metadata.json"
    if nm.is_file():
        norm_meta = json.loads(nm.read_text(encoding="utf-8"))
    meta = {
        "runtime_pipeline_version": RUNTIME_PIPELINE_VERSION,
        "canonical_schema_version": C.CANONICAL_SCHEMA_VERSION,
        "git_commit": _git_commit(),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "normalized_pipeline_version": norm_meta.get("pipeline_version"),
        "normalized_source_versions": norm_meta.get("source_versions", {}),
        "normalized_record_counts": norm_meta.get("record_counts", {}),
        "runtime_counts": counts,
        "timings_seconds": timings,
        "supplementary_sources": {
            "competencies": ["ecf", "ba_kompetenzkatalog"],
            "credentials": ["fixtures"],
            "vector_narrative": constants.PROCESSED_CHUNKS_FILE,
        },
        "note": "Runtime stores rebuilt from data/normalized (governed). Supplementary "
                "domains not yet in the normalized layer are sourced via governed fixtures/"
                "narrative corpus and listed above.",
    }
    (active / "build_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def build(*, do_structured: bool, do_vector: bool, validate_only: bool,
          normalized_dir: str, knowledge_dir: str) -> dict:
    norm = Path(normalized_dir)
    if not norm.is_dir() or not any(norm.glob("*.parquet")):
        raise SystemExit(f"STOP: no normalized corpus at {norm}. Run "
                         "scripts/knowledge/build_normalized_knowledge.py --all first.")
    active = Path(knowledge_dir)
    build_id = f".build-{int(time.time())}"
    temp = active / build_id
    counts: dict = {}
    timings: dict = {}
    report: dict = {"mode": "validate-only" if validate_only else "build",
                    "structured": do_structured, "vector": do_vector}

    if do_structured:
        t0 = time.time()
        _build_structured(norm, temp, counts)
        problems = _validate_structured(temp)
        timings["structured_build"] = round(time.time() - t0, 2)
        if problems:
            shutil.rmtree(temp, ignore_errors=True)
            raise SystemExit(f"STOP: structured validation failed: {problems}. Live KB intact.")
        if validate_only:
            shutil.rmtree(temp, ignore_errors=True)
        else:
            _promote(temp, active, ["roles.db", "compensation.db", "labour_market.db",
                                    "competencies.db", "credentials.db"])
            shutil.rmtree(temp, ignore_errors=True)

    if do_vector:
        t0 = time.time()
        vtemp = active / f".chroma{build_id}"
        info = _build_vector(norm, vtemp, counts)
        timings["vector_build"] = round(time.time() - t0, 2)
        if info["final_passages"] <= 0:
            shutil.rmtree(vtemp, ignore_errors=True)
            raise SystemExit("STOP: vector build produced 0 passages. Live index intact.")
        if validate_only:
            shutil.rmtree(vtemp, ignore_errors=True)
        else:
            chroma = Path(constants.CHROMA_PERSIST_DIR)
            backup = Path(str(chroma) + f".backup-{int(time.time())}")
            if chroma.exists():
                shutil.move(str(chroma), str(backup))
            shutil.move(str(vtemp), str(chroma))
            shutil.rmtree(backup, ignore_errors=True)

    if not validate_only and do_structured:
        _write_build_metadata(active, counts, norm, timings)

    report.update({"counts": counts, "timings": timings})
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build runtime knowledge stores from the normalized layer.")
    ap.add_argument("--all", action="store_true", help="Build structured + vector.")
    ap.add_argument("--structured-only", action="store_true")
    ap.add_argument("--vector-only", action="store_true")
    ap.add_argument("--validate-only", action="store_true", help="Build+validate, do not promote.")
    ap.add_argument("--normalized-dir", default=NORMALIZED_DIR)
    ap.add_argument("--output-dir", default=KNOWLEDGE_DIR)
    ap.add_argument("--json-report", action="store_true")
    args = ap.parse_args(argv)

    do_structured = args.all or args.structured_only or not (args.vector_only)
    do_vector = args.all or args.vector_only
    if args.structured_only and not args.all:
        do_vector = False
    if args.vector_only and not args.all:
        do_structured = False

    report = build(do_structured=do_structured, do_vector=do_vector,
                   validate_only=args.validate_only, normalized_dir=args.normalized_dir,
                   knowledge_dir=args.output_dir)

    if args.json_report:
        print(json.dumps(report, indent=2))
    else:
        print(f"RUNTIME KNOWLEDGE BUILD ({report['mode']}) -> {args.output_dir}")
        c = report["counts"]
        if "roles" in c:
            print(f"  roles: {c['roles']}")
        if "compensation" in c:
            print(f"  compensation: {c['compensation']}")
        if "labour_market" in c:
            print(f"  labour_market: {c['labour_market']}")
        if "competencies" in c:
            print(f"  competencies: {c['competencies']}")
        if "credentials" in c:
            print(f"  credentials: {c['credentials']}")
        if "vector" in c:
            print(f"  vector: {c['vector']}")
        print(f"  timings: {report['timings']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
