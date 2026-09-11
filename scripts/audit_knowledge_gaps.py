#!/usr/bin/env python
"""Ask4Mo knowledge-gap audit (Phase 7A.1, §44).

Reports per-domain readiness for the Phase 7B knowledge backbone, separating BLOCKING gaps
(the authoritative backbone must be ready) from NON-BLOCKING and FUTURE-ENRICHMENT gaps.
Reads the committed governance (source_status.json / source_manifest.json) — one governance
model, reused — plus a bounded live Adzuna check (env creds) and a Destatis config probe.

No paid calls. Adzuna/Destatis absence never flips the backbone to NOT READY (§41/§10).

Usage:
    python scripts/audit_knowledge_gaps.py
    python scripts/audit_knowledge_gaps.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.knowledge import status as status_mod  # noqa: E402

# domain -> (source_ids that satisfy it, blocking?)
_DOMAINS = {
    "role_taxonomy": (["onet", "esco", "isco08", "kldb"], True),
    "skills": (["onet", "esco", "esco_matrix"], True),
    "responsibilities": (["onet", "bls_ooh"], True),
    "compensation_us": (["bls_oews"], True),
    "compensation_uk": (["ons_ashe"], True),
    "compensation_eu": (["eurostat_earnings"], True),
    "compensation_de": (["ba_entgeltatlas", "eurostat_earnings"], False),  # Destatis handled below
    "labour_market_eu": (["cedefop_skills_forecast", "cedefop_clssi", "eurostat_occ_vacancy"], True),
    "labour_market_de": (["cedefop_skills_forecast"], False),
    "credentials": (["nice_framework"], False),
    "seniority": (["eqf"], False),
    "industry_context": ([], False),
    "emerging_roles": ([], False),
}


def _availability(statuses) -> dict[str, bool]:
    return {s.source_id: bool(getattr(s, "available_for_retrieval", False)) for s in statuses}


def _classify(sources: list[str], avail: dict[str, bool]) -> str:
    if not sources:
        return "PARTIAL"
    hits = [s for s in sources if avail.get(s)]
    if not hits:
        return "MISSING"
    return "READY" if len(hits) == len(sources) else "PARTIAL"


def run_audit() -> dict:
    try:
        statuses = status_mod.load_status()
    except Exception:  # noqa: BLE001
        statuses = []
    avail = _availability(statuses)

    domains = {}
    for name, (srcs, blocking) in _DOMAINS.items():
        domains[name] = {"status": _classify(srcs, avail), "blocking": blocking,
                         "sources": srcs}

    # German compensation: Destatis (official occupation-level) enriches Eurostat SES (DE).
    destatis_configured = bool(__import__("os").environ.get("DESTATIS_TOKEN") or
                               (__import__("os").environ.get("DESTATIS_USERNAME") and
                                __import__("os").environ.get("DESTATIS_PASSWORD")))
    de_comp = domains["compensation_de"]
    if avail.get("eurostat_earnings"):
        de_comp["status"] = "READY" if destatis_configured else "PARTIAL"
    de_comp["destatis_configured"] = destatis_configured
    de_comp["note"] = ("Eurostat SES provides German earnings; Destatis 62361-0034 adds "
                       "official occupation-level detail once an account is configured.")

    # Current market via Adzuna (bounded live check when configured).
    adzuna_status = "NOT CONFIGURED"
    try:
        from src.copilot.knowledge.providers import adzuna
        if adzuna.credentials_configured():
            res = adzuna.AdzunaProvider().search_jobs(country="de", what="product manager",
                                                      results_per_page=1)
            adzuna_status = "READY" if res.ok else "NOT READY"
    except Exception:  # noqa: BLE001
        adzuna_status = "NOT READY"
    domains["current_market"] = {"status": ("READY" if adzuna_status == "READY" else "PARTIAL"),
                                 "blocking": False, "sources": ["adzuna"],
                                 "adzuna": adzuna_status}

    # Emerging roles: best-effort probe of the built role store, if present.
    emerging = _probe_emerging_roles()
    domains["emerging_roles"]["status"] = emerging["overall"]
    domains["emerging_roles"]["detail"] = emerging["detail"]

    blocking_gaps = [n for n, d in domains.items()
                     if d["blocking"] and d["status"] in ("MISSING",)]
    nonblocking_gaps = [n for n, d in domains.items()
                        if not d["blocking"] and d["status"] in ("MISSING", "PARTIAL")]
    backbone_ready = len(blocking_gaps) == 0 and all(
        domains[n]["status"] in ("READY", "PARTIAL")
        for n, (_s, b) in _DOMAINS.items() if b
    )

    return {
        "domains": domains,
        "blocking_gaps": blocking_gaps,
        "non_blocking_gaps": nonblocking_gaps,
        "backbone_ready": backbone_ready,
    }


def _probe_emerging_roles() -> dict:
    roles = ["AI Engineer", "Machine Learning Engineer", "LLM Engineer", "AI Product Manager",
             "AI Governance Specialist", "Prompt Engineer", "Data Scientist"]
    db = "data/knowledge/roles.db"
    if not Path(db).exists():
        return {"overall": "PARTIAL", "detail": {r: "UNKNOWN (no roles.db)" for r in roles}}
    try:
        from src.copilot.knowledge.roles import RoleRepository
        repo = RoleRepository(db)
        detail = {}
        for r in roles:
            hits = repo.search(r, limit=3)
            if any(h.get("title", "").lower() == r.lower() for h in hits):
                detail[r] = "SUPPORTED"
            elif hits:
                detail[r] = "ALIAS_RESOLVABLE"
            else:
                detail[r] = "MISSING"
        supported = sum(1 for v in detail.values() if v in ("SUPPORTED", "ALIAS_RESOLVABLE"))
        overall = "READY" if supported == len(roles) else "PARTIAL"
        return {"overall": overall, "detail": detail}
    except Exception as exc:  # noqa: BLE001
        return {"overall": "PARTIAL", "detail": {"error": type(exc).__name__}}


def _print(rep: dict) -> None:
    print("ASK4MO KNOWLEDGE GAP AUDIT\n")
    labels = {
        "role_taxonomy": "ROLE TAXONOMY", "skills": "SKILLS",
        "responsibilities": "RESPONSIBILITIES", "compensation_de": "COMPENSATION — GERMANY",
        "compensation_us": "COMPENSATION — US", "compensation_uk": "COMPENSATION — UK",
        "compensation_eu": "COMPENSATION — EU", "labour_market_de": "LABOUR MARKET — GERMANY",
        "labour_market_eu": "LABOUR MARKET — EU", "credentials": "CREDENTIALS",
        "seniority": "SENIORITY", "industry_context": "INDUSTRY CONTEXT",
        "emerging_roles": "EMERGING ROLES", "current_market": "CURRENT MARKET / ADZUNA",
    }
    for key, label in labels.items():
        d = rep["domains"].get(key, {})
        tag = "blocking" if d.get("blocking") else "non-blocking"
        print(f"{label}: {d.get('status')}  [{tag}]")
    print("\n" + "-" * 50)
    print(f"BLOCKING gaps: {len(rep['blocking_gaps'])} {rep['blocking_gaps']}")
    print(f"NON-BLOCKING gaps: {len(rep['non_blocking_gaps'])} {rep['non_blocking_gaps']}")
    print("\nPHASE 7B BACKBONE:")
    print("READY" if rep["backbone_ready"] else "NOT READY")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit knowledge gaps for Phase 7B.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rep = run_audit()
    if args.json:
        print(json.dumps(rep, indent=2, default=str))
    else:
        _print(rep)
    return 0 if rep["backbone_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
