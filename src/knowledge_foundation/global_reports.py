"""Global coverage report and source-approval register (P10C-E). Pure and deterministic over COMMITTED artifacts only (registry baseline, taxonomy catalogue, coverage matrix, candidate lists, country
profiles and the P10C-D readiness report): they read no local store, acquire nothing and approve nothing.

* ``coverage_report``: for every relevant market, nine statuses kept SEPARATE (taxonomy acquired, taxonomy edition known, occupation nodes available, crosswalk available, licence verified, approved
  for ingestion, data imported, evidence qualified, runtime use approved) next to the coverage-matrix levels and the adapter that exists. An adapter is not operational coverage.
* ``approval_register``: the actionable register P10C-F inherits. Every entry is PROPOSED (never approved) and names the owner decisions required; the US and UK linkage blockers are entries too."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.knowledge_foundation import readiness
from src.knowledge_foundation.compensation.countries import PROFILES, WIDER_SA_PROFILES

__all__ = ["coverage_report", "approval_register", "MARKETS"]

DATA = Path(__file__).parent / "data"
MARKETS = ("US", "GB", "CA", "MX", "BR", *WIDER_SA_PROFILES.keys())
_ADAPTER = {"US": "oews_records (P10C-C contract)", "GB": "ashe_records (P10C-C contract)", "CA": "canada_records (P10C-D)", "MX": "mexico_records (P10C-D)", "BR": "brazil_records (P10C-D)"}


def _load(name: str) -> Any:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def coverage_report(root: Path | None = None) -> dict[str, Any]:
    rd = readiness.assess(root)["countries"]
    cov = {g["code"]: g for g in _load("coverage_matrix.json")["geographies"]}
    cands = {c["country"]: [] for c in _load("global_source_candidates.json")["candidates"]}
    for c in _load("global_source_candidates.json")["candidates"]:
        cands[c["country"]].append(c["candidate_id"])
    out: dict[str, Any] = {}
    for m in MARKETS:
        prof = PROFILES.get(m) or WIDER_SA_PROFILES.get(m)
        base = rd.get(m)
        row = cov.get(m, {})
        src = (base or {}).get("registry_sources", {})
        out[m] = {
            "name": prof.name if prof else row.get("label"),
            "taxonomy_scheme": prof.taxonomy_scheme if prof else (base or {}).get("taxonomy_scheme"),
            "statuses": {
                "taxonomy_acquired": False, "taxonomy_edition_known": False, "occupation_nodes_available": 0, "crosswalk_available": False,
                "licence_verified": any(s["licence_status"] == "verified" for s in src.values()), "approved_for_ingestion": any(s["approval_status"] in ("approved_for_ingestion", "approved_for_runtime_use") for s in src.values()),
                "data_imported": 0, "evidence_qualified": False, "runtime_use_approved": False},
            "local_v1_records": (base or {}).get("local_v1_records", 0),
            "coverage_levels": {k: row.get(k) for k in ("taxonomy_level", "crosswalk_level", "compensation_level", "outlook_level")},
            "adapter": _ADAPTER.get(m, "south_america_records (P10C-E, synthetic fixtures only)"), "adapter_is_operational_coverage": False, "operational_today": False,
            "region_vocabulary_recorded": len(prof.regions) if prof else 0, "candidate_source_ids": cands.get(m, []) + (base or {}).get("candidate_source_ids", []),
            "source_languages_from_evidence": row.get("source_languages", []),
        }
        if m in WIDER_SA_PROFILES:                                    # the only occupation namespace usable today is the international one; no national classification is identified
            out[m]["isco08_structure_held_locally"] = True
            out[m]["national_occupation_classification"] = "UNKNOWN (none identified)"
    out["INTL"] = {"name": "International (ILOSTAT-style)", "taxonomy_scheme": "isco", "statuses": {"taxonomy_acquired": True, "taxonomy_edition_known": True, "occupation_nodes_available": "ISCO-08 nodes exist only as a P10C-B local import; none is committed",
                                                                                                           "crosswalk_available": False, "licence_verified": False, "approved_for_ingestion": False, "data_imported": 0, "evidence_qualified": False, "runtime_use_approved": False},
                   "adapter": "ilostat_records (P10C-E contract)", "adapter_is_operational_coverage": False, "operational_today": False, "precedence_decision": "PENDING OWNER DECISION D-16",
                   "candidate_source_ids": cands.get("INTL", [])}
    return {"schema": "p10ce_global_coverage/1", "note": "Derived from committed artifacts only. Nine statuses are kept separate; an adapter is not operational coverage; no market is qualified and global coverage is not claimed.",
            "markets": out, "operational_markets": [m for m, v in out.items() if v["operational_today"]], "qualified_markets": [m for m, v in out.items() if v.get("statuses", {}).get("evidence_qualified")]}


def _entry(rid, kind, **kw) -> dict[str, Any]:
    base = {"register_id": rid, "kind": kind, "source_id": None, "publisher": "UNKNOWN", "dataset": "UNKNOWN", "edition": "UNKNOWN", "geography": "UNKNOWN", "taxonomy": "UNKNOWN", "licence": "UNKNOWN",
            "attribution": "UNKNOWN", "redistribution": "UNKNOWN", "commercial_use": "UNKNOWN", "proposed_evidence_class": "UNKNOWN", "proposed_precedence_category": "UNKNOWN",
            "proposed_import_method": "UNKNOWN", "proposed_operational_use": "UNKNOWN", "current_lifecycle_state": "SOURCE_IDENTIFIED", "status": "PROPOSED", "decisions_required": [], "linked_blockers": []}
    base.update(kw)
    return base


def approval_register(root: Path | None = None) -> dict[str, Any]:
    reg = {s["source_id"]: s for s in _load("source_registry_baseline.json")["sources"]}
    rd = readiness.assess(root)["countries"]
    entries: list[dict[str, Any]] = []
    method_comp = "manual acquisition of a named extract, then the registry-gated importer (production mode) with the matching adapter; synthetic fixtures never"
    for sid, geo, tax in (("bls_oews", "US", "soc"), ("ons_ashe", "GB", "uk_soc"), ("eurostat_earnings", "EU", "isco"), ("ba_entgeltatlas", "DE", "unknown"), ("destatis", "DE", "unknown")):
        s = reg[sid]
        entries.append(_entry(f"reg:{sid}", "compensation_source", source_id=sid, publisher=s["publisher"], dataset=s["dataset_name"], edition=s["dataset_version"] or "UNKNOWN", geography=geo, taxonomy=tax,
                              licence=f"{s['licence_id'] or 'UNKNOWN'} ({s['licence_status']})", attribution=s["attribution_required"], redistribution=s["redistribution"],
                              proposed_evidence_class=s["evidence_class"] or "UNKNOWN", proposed_precedence_category=s["precedence_category"], proposed_import_method=method_comp,
                              proposed_operational_use="internal Compensation V2 resolver only after runtime approval and measurement qualification; no candidate-facing activation proposed here",
                              current_lifecycle_state=s["approval_status"].upper(), decisions_required=[{"id": "D-04", "question": "verify the licence and approve ingestion, then runtime use"}, {"id": "D-12", "question": "select and record the official source edition"}],
                              linked_blockers=[b["id"] for c in ("US", "GB") for b in rd[c]["blockers"] if sid in rd[c]["registry_sources"] or c == geo]))
    for sid, kind in (("onet", "taxonomy_source"), ("esco", "taxonomy_source"), ("isco08", "taxonomy_source")):
        s = reg[sid]
        entries.append(_entry(f"reg:{sid}", kind, source_id=sid, publisher=s["publisher"], dataset=s["dataset_name"], edition=s["dataset_version"] or "UNKNOWN", geography=",".join(s["geographies"]) or "UNKNOWN",
                              taxonomy=s["taxonomy"] or sid, licence=f"{s['licence_id'] or 'UNKNOWN'} ({s['licence_status']})", attribution=s["attribution_required"], redistribution=s["redistribution"],
                              proposed_import_method="registry-gated taxonomy import (production mode)", proposed_operational_use="occupation identity and crosswalk evidence for the internal resolver",
                              current_lifecycle_state=s["approval_status"].upper(), decisions_required=[{"id": "D-04", "question": "verify the licence and approve ingestion"}, {"id": "D-12", "question": "record the edition"}]))
    for c in _load("country_source_candidates.json")["candidates"]:
        entries.append(_entry(f"cand:{c['candidate_id']}", "compensation_source" if c["kind"] == "compensation" else "taxonomy_structure", publisher=c["publisher"], dataset=c["dataset"], geography=c["country"], taxonomy=c["taxonomy"],
                              proposed_evidence_class="UNKNOWN until the dataset is identified", proposed_precedence_category=c.get("precedence_category_if_approved", "not applicable (taxonomy)"),
                              proposed_import_method=method_comp if c["kind"] == "compensation" else "manual acquisition of the taxonomy structure, then the registry-gated taxonomy importer",
                              proposed_operational_use="internal resolver only after approval" if c["kind"] == "compensation" else "canonical occupation nodes for the internal resolver",
                              decisions_required=[{"id": "D-04", "question": "verify the licence and terms; authorise acquisition and ingestion"}, {"id": "D-12", "question": "record the edition"}, {"id": "D-13", "question": "authorise taxonomy acquisition"}],
                              linked_blockers=[b["id"] for b in rd[c["country"]]["blockers"]]))
    for c in _load("global_source_candidates.json")["candidates"]:
        intl = c["country"] == "INTL"
        entries.append(_entry(f"cand:{c['candidate_id']}", "international_compensation" if intl else "national_statistics_office", publisher=c["publisher"], dataset=c["dataset"] or "UNKNOWN", geography=c["country"],
                              taxonomy="isco" if intl else "UNKNOWN (no national classification identified)", proposed_evidence_class=c["proposed_evidence_class"],
                              proposed_precedence_category="UNDECIDED (D-16): the registry vocabulary has no category for a non-Eurostat international harmonised source" if intl else "national_official_occupation_statistics (if approved)",
                              proposed_import_method="manual acquisition of a specific named extract, then the registry-gated importer with " + ("the ILOSTAT-style international adapter" if intl else "the wider South America adapter"),
                              proposed_operational_use="none until D-16 and runtime approval; never operational while the precedence decision is pending" if intl else "internal resolver only after approval and qualification",
                              decisions_required=[{"id": "D-04", "question": "identify the dataset, verify the licence, authorise acquisition and ingestion"}, {"id": "D-12", "question": "record the dataset edition and ISCO edition"}] + ([{"id": "D-16", "question": "decide the precedence category"}] if intl else [{"id": "D-13", "question": "identify any national occupation classification"}])))
    for rid, label, geo, tax, bl in (("link:us_soc_structure", "US Standard Occupational Classification structure (candidate)", "US", "soc", [b["id"] for b in rd["US"]["blockers"] if b["id"] in ("US-T1", "US-T2", "US-G1", "US-D1", "US-D2")]),
                                     ("link:uk_soc_2020_structure", "UK Standard Occupational Classification 2020 structure (candidate)", "GB", "uk_soc", [b["id"] for b in rd["GB"]["blockers"] if b["id"] in ("GB-T1", "GB-T2", "GB-G1", "GB-D1", "GB-D2")]),
                                     ("link:us_soc_crosswalk", "Official SOC to ISCO-08 crosswalk (candidate; existence and provenance UNVERIFIED)", "US", "soc", ["US-X1"]),
                                     ("link:uk_soc_crosswalk", "Official UK SOC 2020 to ISCO-08 crosswalk (candidate; existence and provenance UNVERIFIED)", "GB", "uk_soc", ["GB-X1"])):
        entries.append(_entry(rid, "crosswalk" if "crosswalk" in rid else "taxonomy_structure", dataset=label, geography=geo, taxonomy=tax,
                              proposed_import_method="registry-gated taxonomy import" if "structure" in rid else "registry-gated crosswalk import (source-provided rows only; nothing manufactured)",
                              proposed_operational_use="makes existing V1 records linkable to canonical occupations after re-reading the source files", linked_blockers=bl,
                              decisions_required=[{"id": "D-03" if geo == "GB" else "D-13", "question": "adopt and authorise acquisition"}, {"id": "D-04", "question": "verify licence and approve ingestion"}, {"id": "D-12", "question": "record the edition"}]))
    return {"schema": "p10ce_source_approval_register/1", "note": "PROPOSED entries only. No entry is approved; every entry names the owner decisions required before P10C-F can act. Unknown facts stay UNKNOWN.",
            "entries": entries, "approved_entries": [e["register_id"] for e in entries if e["status"] != "PROPOSED"]}
