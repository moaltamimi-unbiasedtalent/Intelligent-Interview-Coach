#!/usr/bin/env python
"""P10D source availability matrix: what the current candidate knowledge base actually contains, per knowledge category, in THIS environment.

READ-ONLY. It reads the tracked source manifest, the (git-ignored) local origin file and the (git-ignored) local stores through read-only SQLite connections, plus
two tracked P10C documents, and writes a Markdown/JSON matrix to the paths given (never inside a protected location). It opens no network connection, writes no store and
approves, qualifies or promotes nothing. A configured adapter is NOT an acquired dataset and an isolated engineering-checked dataset is NOT operationally qualified evidence;
the matrix keeps those facts in separate columns. The result depends on the environment (a clean checkout has none of the generated stores): the environment is recorded in the output.

    python scripts/p10d_source_matrix.py [--root DIR] [--md PATH] [--json PATH]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.knowledge_foundation.pathsafe import output_is_protected  # noqa: E402

STORE_FILES = {"roles": "data/knowledge/roles.db", "compensation": "data/knowledge/compensation.db", "labour_market": "data/knowledge/labour_market.db",
               "competencies": "data/knowledge/competencies.db", "credentials": "data/knowledge/credentials.db", "vector": "data/chroma/chroma.sqlite3"}
# store -> (table, source column)
STRUCTURED_TABLES = {"roles": [("occupations", "source_id")], "compensation": [("compensation_records", "source_id")],
                     "labour_market": [("labour_market_forecasts", "source_id"), ("labour_market_openings", "source_id"), ("labour_shortages", "source_id"), ("labour_vacancies", "source_id")],
                     "competencies": [("competencies", "source_id")], "credentials": [("certifications", "source_id"), ("occupational_licences", "source_id")]}
CATEGORY = {"occupations": "Occupation definitions", "skills": "Skills", "specialist": "Skills (specialist frameworks)", "job_architecture": "Career progression and job architecture",
            "compensation": "Compensation", "labour_market": "Employment outlook and labour market", "narrative": "Narrative guidance (interview preparation and labour-market context)"}


def _ro(path: Path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def local_counts(root: Path) -> dict:
    """{store: {source_id: records}} for every local store that exists (read-only); a missing store contributes nothing."""
    out: dict[str, dict[str, int]] = {}
    for store, tables in STRUCTURED_TABLES.items():
        p = root / STORE_FILES[store]
        if not p.exists():
            continue
        c = _ro(p)
        try:
            agg: dict[str, int] = {}
            for table, col in tables:
                try:
                    for sid, n in c.execute(f"select {col}, count(*) from {table} group by 1"):
                        agg[sid] = agg.get(sid, 0) + n
                except sqlite3.Error:
                    continue
            out[store] = agg
        finally:
            c.close()
    p = root / STORE_FILES["vector"]
    if p.exists():
        c = _ro(p)
        try:
            out["vector"] = {sid: n for sid, n in c.execute("select string_value, count(*) from embedding_metadata where key='manifest_source_id' group by 1")}
            out["_vector_total"] = {"chunks": c.execute("select count(*) from embeddings").fetchone()[0],
                                    "with_source_url": c.execute("select count(distinct id) from embedding_metadata where key='source_url' and string_value<>''").fetchone()[0]}
        finally:
            c.close()
    return out


def origins(root: Path) -> dict:
    p = root / "data/knowledge/data_origins.json"
    return json.loads(p.read_text())["origins"] if p.exists() else {}


def build(root: Path) -> dict:
    manifest = json.loads((root / "data/source_manifest.json").read_text())["sources"]
    counts = local_counts(root)
    orig = origins(root)
    env_stores = {k: (root / v).exists() for k, v in STORE_FILES.items()}
    profile = "developer_local" if all(env_stores.values()) else ("clean_checkout" if not any(env_stores.values()) else "partial (ambiguous)")
    rows = []
    for s in manifest:
        sid = s["source_id"]
        target = s.get("storage_target", "")
        store = {"structured_role": "roles", "compensation": "compensation", "competency": "competencies", "labour_market": "labour_market", "vector": "vector", "structured": "labour_market"}.get(target)
        n = (counts.get(store, {}).get(sid, 0) if store else 0)
        # compensation sources keep their narrative form in the vector store too (counted separately)
        n_vec = counts.get("vector", {}).get(sid, 0)
        origin = orig.get(sid) if orig else None
        if s.get("manual_acquisition_required") and not (n or n_vec):
            ingestion = "NOT ACQUIRED (manual acquisition required)"
        elif s.get("licence_review_required") and not (n or n_vec):
            ingestion = "NOT ACQUIRED (licence review required)"
        elif n or n_vec:
            ingestion = ", ".join(x for x in (f"{n} records in {store}" if n else "", f"{n_vec} narrative chunks in vector" if n_vec else "") if x)
        else:
            ingestion = "NOT PRESENT in this environment" + ("" if not env_stores.get(store or "vector") else " (store present, no records for this source)")
        if not (n or n_vec):
            elig = "NOT ELIGIBLE (no records in this environment)"
        elif origin and "synthetic_fixture" in origin:
            elig = "SERVING (legacy path) but FLAGGED synthetic fixture: not production evidence"
        else:
            elig = "SERVING (legacy pre-P10C path; origin and provenance recorded); not qualified under the P10C evidence policy"
        rows.append({"category": CATEGORY.get(s.get("group"), s.get("group", "")), "source_id": sid, "title": s.get("title"), "edition": s.get("version"), "country": s.get("country"), "language": s.get("language"),
                     "authority": s.get("authority_level"), "licence": s.get("licence"), "availability": "configured in the manifest" + ("; manual acquisition required" if s.get("manual_acquisition_required") else "")
                     + ("; licence review required" if s.get("licence_review_required") else ""), "ingestion": ingestion, "origin": origin or "unknown (no local origin file)",
                     "qualification": "legacy source; 0 human-qualified; no P10C qualification", "runtime_eligibility": elig, "retrieval": f"lane via {target or 'n/a'}", "citation": "manifest title, publisher and URL" if s.get("source_url") else "NO URL",
                     "limitations": s.get("licence_notes") or ""})
    extra = [
        {"category": "Company research", "source_id": "adzuna (research provider)", "title": "Adzuna current-market jobs (research layer)", "edition": "live API", "country": "multi", "language": "en",
         "availability": "adapter CONFIGURED; needs credentials; not an acquired dataset", "ingestion": "not ingested (live, TTL-cached)", "qualification": "not applicable (time-sensitive research, labelled as such)",
         "runtime_eligibility": "OFF without credentials; research is a separate labelled lane and never enters structured retrieval", "retrieval": "ExternalResearchService (separate from the KB)", "citation": "provider result labelled",
         "limitations": "Third-party; current-market only; never merged into the knowledge base."},
        {"category": "Company research", "source_id": "company web provider", "title": "Official company website (SSRF/robots-guarded fetch)", "edition": "live", "country": "company-specific", "language": "any",
         "availability": "adapter CONFIGURED; explicit website required", "ingestion": "not ingested (live, TTL-cached)", "qualification": "FACT only from the official site; reviews are link-out",
         "runtime_eligibility": "ON by default behind the research safety layer; separate lane", "retrieval": "ExternalResearchService", "citation": "page URL", "limitations": "Glassdoor, Kununu, Google and LinkedIn are NOT integrated."},
        {"category": "Compensation (governed German dataset K1)", "source_id": "k1_de_compensation", "title": "Governed German occupation compensation (K1)", "edition": "see file", "country": "DE", "language": "de/en",
         "availability": "committed governed JSON", "ingestion": "governed dataset (abstention-first access)", "qualification": "reviewed governed dataset; not P10C-qualified", "runtime_eligibility": "SERVING through governed access (abstains when absent)",
         "retrieval": "governed_datasets", "citation": "provenance + pay unit + reference year", "limitations": "Bounded; never invents a salary."},
        {"category": "Credentials and licences", "source_id": "k2_credentials", "title": "Governed credentials and regulated-professions matrix (K2)", "edition": "see file", "country": "multi", "language": "en/de",
         "availability": "committed governed JSON", "ingestion": "governed dataset", "qualification": "reviewed governed dataset", "runtime_eligibility": "SERVING through governed access", "retrieval": "governed_datasets", "citation": "authority lineage",
         "limitations": "Bounded."},
    ]
    p10c = {}
    pk = root / "docs/capstone/p10/p10c_f2a/human_review_packet.json"
    if pk.exists():
        d = json.loads(pk.read_text())
        p10c = {"us_records_engineering_checked": d["baseline"]["record_states"].get("engineering_checked", 0), "us_records_qualified": d["baseline"]["record_states"].get("qualified", 0),
                "us_aliases_engineering_checked": d["baseline"]["alias_states"].get("engineering_checked", 0), "us_aliases_qualified": d["baseline"]["alias_states"].get("qualified", 0)}
    return {"environment_profile": profile, "stores_present": env_stores, "rows": rows + extra, "vector_total": counts.get("_vector_total"), "p10c_isolated_us": p10c,
            "p10c_status": {"us_official": "isolated database only; engineering-checked; 0 human-qualified; 0 runtime-approved; NOT used by the candidate runtime (no import path)", "uk": "preparation complete; acquisition deferred",
                            "other_countries": "deferred", "rb_lic_1": "OPEN", "compensation_v2": "DISABLED"}}


def render(d: dict) -> str:
    lines = ["# P10D source availability matrix (generated)", "", f"Environment profile: **{d['environment_profile']}**. Stores present: " + ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in d["stores_present"].items()) + ".", "",
             "Read-only generation from the tracked manifest, the local origin file and read-only SQLite connections. A configured adapter is not an acquired dataset, and an isolated engineering-checked dataset is not operationally qualified evidence.", ""]
    if d["vector_total"]:
        lines += [f"Vector store: {d['vector_total']['chunks']} chunks, {d['vector_total']['with_source_url']} with a source URL.", ""]
    lines += ["| Category | Source | Edition | Country | Language | Availability | Ingestion | Origin | Qualification | Runtime eligibility | Retrieval | Citation |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(d["rows"], key=lambda x: (x["category"], x["source_id"])):
        lines.append("| " + " | ".join(str(r.get(k, "")) for k in ("category", "source_id", "edition", "country", "language", "availability", "ingestion", "origin", "qualification", "runtime_eligibility", "retrieval", "citation")).replace("\n", " ") + " |")
    lines += ["", "## P10C foundation (isolated; not part of the candidate runtime)", ""]
    for k, v in d["p10c_status"].items():
        lines.append(f"- {k}: {v}")
    if d["p10c_isolated_us"]:
        lines.append(f"- US isolated counts (from the tracked packet): {d['p10c_isolated_us']}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--md", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    for out in (a.md, a.json):
        if out and output_is_protected(out, ROOT):
            raise SystemExit("refusing to write inside a protected location")
    d = build(Path(a.root))
    if a.json:
        Path(a.json).write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
    if a.md:
        Path(a.md).write_text(render(d), encoding="utf-8")
    print(f"source matrix [{d['environment_profile']}]: {len(d['rows'])} rows; stores present: {sum(d['stores_present'].values())}/6")
    return 0


if __name__ == "__main__":
    sys.exit(main())
