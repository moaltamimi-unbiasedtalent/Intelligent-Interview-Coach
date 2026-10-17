"""Registry seed (GKB-1): transforms the EXISTING source manifest, status snapshot and data-origin metadata into registry entries. Pure and deterministic. Unknown facts stay
unknown. Registry entries start ``licensing_pending`` (or ``restricted`` for synthetic fixtures): official and locally present are NOT approval, and existing local runtime use predates
this registry and is not retroactively approved."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.knowledge_foundation import enums as E

__all__ = ["build_registry_entries", "load_registry_baseline", "BASELINE_PATH", "SOURCE_TAXONOMY", "PRECEDENCE_BY_SOURCE", "CLASS_BY_SOURCE"]

BASELINE_PATH = Path(__file__).parent / "data" / "source_registry_baseline.json"

# Taxonomy a source publishes occupation codes in (only where the repository evidence states it).
SOURCE_TAXONOMY = {"onet": "onet_soc", "esco": "esco", "isco08": "isco", "kldb": "kldb", "bls_ooh": "soc", "bls_projections": "soc", "bls_oews": "soc", "ons_ashe": "uk_soc"}
# Recovered six-level precedence category (P10C-0 Addendum A3) for the compensation and labour-market sources only; every other source stays 'unknown'.
PRECEDENCE_BY_SOURCE = {"bls_oews": "national_official_occupation_statistics", "bls_projections": "national_official_occupation_statistics", "bls_ooh": "national_official_occupation_statistics",
                        "ons_ashe": "national_official_occupation_statistics", "ba_entgeltatlas": "national_public_employment_service", "destatis": "national_official_occupation_statistics",
                        "eurostat_earnings": "eurostat_harmonised", "eurostat_occ_vacancy": "eurostat_harmonised", "cedefop_skills_forecast": "cedefop_intelligence",
                        "cedefop_future_job_openings": "cedefop_intelligence", "cedefop_shortage_index": "cedefop_intelligence", "cedefop_stas": "cedefop_intelligence",
                        "cedefop_clssi": "cedefop_intelligence", "adzuna": "authorized_secondary", "wef_future_of_jobs": "authorized_secondary"}
# C-class only where the recovered specification NAMES the example (BLS OEWS and the German Entgeltatlas as C1); everything else is unknown, not guessed.
CLASS_BY_SOURCE = {"bls_oews": "C1", "ba_entgeltatlas": "C1"}


def _tri(value: Any) -> str:
    return "unknown" if value is None else ("yes" if value else "no")


def build_registry_entries(manifest: dict | list, status: dict | None = None, origins: dict | None = None) -> list[dict[str, Any]]:
    sources = manifest.get("sources", manifest) if isinstance(manifest, dict) else manifest
    st = {x["source_id"]: x for x in (status or {}).get("sources", [])}
    org = (origins or {}).get("origins", origins or {})
    out: list[dict[str, Any]] = []
    for e in sorted(sources, key=lambda x: x["source_id"]):
        sid = e["source_id"]
        s = st.get(sid, {})
        o = org.get(sid) or []
        synthetic_only = bool(o) and all(x == "synthetic_fixture" for x in o)
        if synthetic_only:
            origin = "synthetic_fixture"
        elif "official_local" in o:
            origin = "official_local"
        elif "authorised_manual" in o:
            origin = "authorised_manual"
        elif e.get("acquisition_type") in ("official_api", "authorized_api"):
            origin = e["acquisition_type"]
        else:
            origin = "unknown"
        licence = (e.get("licence") or "").strip() or None
        conflicts: list[str] = []
        # The manifest serializes ``redistribution_allowed: false`` as the model DEFAULT, indistinguishable from a decision: only an explicit true is a declaration; false is "not declared
        # permitted" and is recorded as unknown (it is still never treated as permission).
        redistribution = "yes" if e.get("redistribution_allowed") is True else "unknown"
        if redistribution == "yes" and not licence:
            conflicts.append("redistribution_declared_without_a_stated_licence")
            redistribution = "unknown"                                   # a declaration without a licence is not trusted
        version = e.get("version")
        if version in (None, "", "current release") and s.get("detected_version"):
            version = str(s["detected_version"])
        approval = "restricted" if origin == "synthetic_fixture" else "licensing_pending"
        notes = (e.get("licence_notes") or "")
        entry = {
            "source_id": sid, "publisher": e.get("publisher"), "dataset_name": e.get("title"), "dataset_version": version, "source_url": e.get("source_url"),
            "geographies": [e["country"]] if e.get("country") else [], "languages": [e["language"]] if e.get("language") else [],
            "taxonomy": SOURCE_TAXONOMY.get(sid), "evidence_category": e.get("source_type"), "publication_date": e.get("publication_date"), "reference_period": None,
            "update_cadence": e.get("refresh_frequency"), "precedence_category": PRECEDENCE_BY_SOURCE.get(sid, "unknown"), "evidence_class": CLASS_BY_SOURCE.get(sid),
            "licence_id": licence, "licence_status": "stated_unverified" if licence else "unknown",
            "attribution_required": "yes" if "attribution" in notes.lower() else "unknown", "redistribution": redistribution, "origin": origin, "approval_status": approval,
            "operational_status": (s.get("lifecycle") or "unknown").lower(), "validation_status": "engineering_draft" if origin == "synthetic_fixture" else "unknown",
            "provenance": {"manifest": True, "authority": e.get("authority"), "authority_level": e.get("authority_level"), "storage_target": e.get("storage_target"),
                           "licence_review_required": bool(e.get("licence_review_required")), "manual_acquisition_required": bool(e.get("manual_acquisition_required")),
                           "licence_notes": notes or None, "origins": list(o), "conflicts": conflicts,
                           "status_snapshot": {k: s.get(k) for k in ("detected_version", "detected_reference_year", "freshness", "record_count", "production_ready", "fixture_only", "lifecycle")} if s else None},
        }
        assert entry["origin"] in E.ORIGINS and entry["precedence_category"] in E.PRECEDENCE
        out.append(entry)
    return out


def load_registry_baseline(registry, path: Path = BASELINE_PATH) -> int:
    """Register the committed baseline into a registry. Idempotent; never approves anything; performs no download or ingestion."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for e in data["sources"]:
        fields = {k: v for k, v in e.items() if k != "source_id"}
        registry.register(e["source_id"], **fields)
    return len(data["sources"])
