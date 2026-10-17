"""Source-readiness assessment (P10C-D). Pure and deterministic over COMMITTED artifacts only (registry baseline, taxonomy catalogue, coverage matrix, the compensation inventory and the
country candidate list): it states, per country, whether evidence could become operational today and lists the exact dependencies that prevent it, with a bounded remediation plan. It
acquires nothing, reads no local store and approves nothing. A source adapter without qualified occupation linkage is NOT completed country coverage, and this report says so per country."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = ["assess", "COUNTRIES"]

DATA = Path(__file__).parent / "data"
COUNTRIES = ("US", "GB", "CA", "MX", "BR")
_TAXONOMY = {"US": "soc", "GB": "uk_soc", "CA": "noc", "MX": "sinco", "BR": "cbo"}
_SOURCES = {"US": ("bls_oews", "onet"), "GB": ("ons_ashe",), "CA": (), "MX": (), "BR": ()}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def assess(root: Path | None = None) -> dict[str, Any]:
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    registry = {s["source_id"]: s for s in _load(DATA / "source_registry_baseline.json")["sources"]}
    catalogue = {t["scheme"]: t for t in _load(DATA / "taxonomy_catalogue.json")["taxonomies"] if t["edition"] in ("unknown", "2020", "08")}
    coverage = {g["code"]: g for g in _load(DATA / "coverage_matrix.json")["geographies"]}
    candidates = _load(DATA / "country_source_candidates.json")["candidates"]
    inv_path = root / "docs/capstone/p10/p10c_c/COMPENSATION_INVENTORY.json"
    inventory = _load(inv_path) if inv_path.exists() else {}
    local_records = {"US": inventory.get("per_source", {}).get("bls_oews", {}).get("records", 0), "GB": inventory.get("per_source", {}).get("ons_ashe", {}).get("records", 0)}
    out: dict[str, Any] = {}
    for c in COUNTRIES:
        scheme = _TAXONOMY[c]
        tax = catalogue.get(scheme, {})
        srcs = {sid: {k: registry[sid][k] for k in ("licence_status", "licence_id", "approval_status", "origin", "dataset_version")} for sid in _SOURCES[c] if sid in registry}
        cand = [x["candidate_id"] for x in candidates if x["country"] == c]
        blockers = [
            {"id": f"{c}-T1", "dependency": f"national taxonomy ({scheme}) structure not acquired: {tax.get('acquisition_status', 'unknown')}", "kind": "taxonomy_acquisition", "decision": "D-13"},
            {"id": f"{c}-T2", "dependency": "no taxonomy edition is recorded as known; an unknown edition matches nothing and a production import refuses it", "kind": "edition", "decision": "D-12"},
            {"id": f"{c}-G1", "dependency": f"no {scheme} nodes exist in the occupation graph, so no compensation row can link to a canonical occupation", "kind": "graph", "decision": "D-13"},
            {"id": f"{c}-X1", "dependency": f"no official {scheme} to ISCO-08 (or ESCO) crosswalk is held; none may be manufactured", "kind": "crosswalk", "decision": "D-13"},
            {"id": f"{c}-L1", "dependency": "no source of this country has a verified licence", "kind": "licensing", "decision": "D-04"},
            {"id": f"{c}-A1", "dependency": "no source of this country is approved for ingestion or runtime use", "kind": "approval", "decision": "D-04"},
        ]
        if c == "US":
            blockers += [{"id": "US-D1", "dependency": "the V1 store does not keep the OEWS occupation level (detailed or broad), so C1 versus C2 requires re-reading the source file", "kind": "data", "decision": "D-12"},
                         {"id": "US-D2", "dependency": "OEWS pay basis (gross or net) and the SOC edition are not recorded", "kind": "data", "decision": "D-12"}]
        if c == "GB":
            blockers += [{"id": "GB-D1", "dependency": "one of 527 ASHE rows has no native code and cannot be linked", "kind": "data", "decision": "D-12"},
                         {"id": "GB-D2", "dependency": "UK SOC 2020 is not adopted as a first-class taxonomy or acquired", "kind": "taxonomy_acquisition", "decision": "D-03"}]
        if c in ("CA", "MX", "BR"):
            blockers.append({"id": f"{c}-S1", "dependency": "no compensation source is acquired; candidates are names only (definitions, units, coverage and licence unknown)", "kind": "source", "decision": "D-04"})
        cov = coverage.get(c, {})
        out[c] = {
            "taxonomy_scheme": scheme, "taxonomy_acquisition_status": tax.get("acquisition_status"), "taxonomy_edition_known": False, "graph_nodes_for_taxonomy": 0, "crosswalk_held": False,
            "local_v1_records": local_records.get(c, 0), "registry_sources": srcs, "candidate_source_ids": cand,
            "coverage": {k: cov.get(k) for k in ("taxonomy_level", "crosswalk_level", "compensation_level", "outlook_level")},
            "compensation_v2_records_linkable_today": 0, "approved_compensation_v2_sources": 0, "operational_today": False, "blockers": blockers,
            "adapter_without_linkage_is_not_coverage": True,
        }
    out["_remediation_plan"] = [
        {"step": 1, "action": "owner verifies the licence and terms of each candidate source and records the source edition", "owner_decision": "D-04, D-12", "engineering_possible_now": False},
        {"step": 2, "action": "owner authorises acquisition of the national taxonomy structure (SOC, UK SOC 2020, NOC, SINCO, CBO) and of any official crosswalk", "owner_decision": "D-03, D-13", "engineering_possible_now": False},
        {"step": 3, "action": "register taxonomy editions and import taxonomy nodes through the registry-gated importer (production mode)", "owner_decision": "after 1 and 2", "engineering_possible_now": "contract implemented in P10C-D"},
        {"step": 4, "action": "import the official crosswalk rows through the registry-gated importer; unverified or related rows stay as stated", "owner_decision": "after 2", "engineering_possible_now": "contract implemented in P10C-D"},
        {"step": 5, "action": "re-read source files with the country adapter (level, concept, population, method, edition) and import compensation rows (production mode)", "owner_decision": "after 1", "engineering_possible_now": "contract implemented in P10C-C and P10C-D"},
        {"step": 6, "action": "named human review qualifies measurements; owner approves runtime use per source; only then can a response become operational", "owner_decision": "D-04, D-11", "engineering_possible_now": False},
    ]
    return {"schema": "gkb8_source_readiness/1", "note": "Derived from committed artifacts only. Nothing acquired, assessed or approved. A source adapter without qualified occupation linkage is not completed country coverage.", "countries": {k: v for k, v in out.items() if not k.startswith("_")},
            "remediation_plan": out["_remediation_plan"]}
