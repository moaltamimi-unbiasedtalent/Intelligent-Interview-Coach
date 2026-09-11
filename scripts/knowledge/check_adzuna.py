#!/usr/bin/env python
"""Adzuna connectivity readiness check (Phase 7A.1, §33).

Validates the authorized Adzuna market-data provider WITHOUT ever exposing credentials.
Credentials are read only from ADZUNA_APP_ID / ADZUNA_APP_KEY. Germany connectivity is
validated via `/jobs/de/search/1` (and `/jobs/de/categories`) — the `/jobs/de/version`
endpoint is NOT required (it returns 404 for endpoint-specific reasons; §32).

Never prints app_id, app_key or an authenticated URL. Adzuna is an ENHANCEMENT — this
check never fails Phase 7B readiness (§41): absent credentials → NOT CONFIGURED, exit 0.

Usage:
    python scripts/knowledge/check_adzuna.py
    python scripts/knowledge/check_adzuna.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.copilot.knowledge.providers import adzuna  # noqa: E402


def run_check() -> dict:
    rep = {
        "credentials": "CONFIGURED" if adzuna.credentials_configured() else "NOT CONFIGURED",
        "germany_search": "NOT TESTED",
        "germany_categories": "NOT TESTED",
        "germany_version_endpoint": "NOT REQUIRED",
        "rate_limit": "UNKNOWN",
        "search_count": None,
        "salary_fields_present": None,
        "status": "NOT READY",
        "provider_classification": "authorized_market_api",
    }
    if not adzuna.credentials_configured():
        rep["status"] = "NOT CONFIGURED"
        return rep

    provider = adzuna.AdzunaProvider()
    # Small Germany search.
    try:
        res = provider.search_jobs(country="de", what="product manager", results_per_page=1)
        rep["germany_search"] = "PASS" if res.ok else "FAIL"
        rep["search_count"] = res.count
        jobs = (res.data or {}).get("results") or []
        if jobs:
            sal = adzuna.parse_salary(jobs[0])
            rep["salary_fields_present"] = any(v is not None for v in
                                               (sal["salary_min"], sal["salary_max"]))
        rep["rate_limit"] = "OK"
    except adzuna.AdzunaError as exc:
        rep["germany_search"] = "FAIL"
        if exc.category == "rate_limit":
            rep["rate_limit"] = "LIMITED"

    # Categories (secondary).
    try:
        cat = provider.categories(country="de")
        rep["germany_categories"] = "PASS" if cat.ok else "FAIL"
    except adzuna.AdzunaError:
        rep["germany_categories"] = "FAIL"

    if rep["germany_search"] == "PASS":
        rep["status"] = "READY" if rep["germany_categories"] in ("PASS", "NOT TESTED") else "PARTIAL"
    else:
        rep["status"] = "NOT READY"
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Adzuna connectivity readiness.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rep = run_check()
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print("ADZUNA API\n")
        print(f"credentials: {rep['credentials']}")
        print(f"Germany search: {rep['germany_search']}"
              + (f" ({rep['search_count']} results)" if rep["search_count"] is not None else ""))
        print(f"Germany categories: {rep['germany_categories']}")
        print(f"Germany version endpoint: {rep['germany_version_endpoint']}")
        print(f"salary fields present: {rep['salary_fields_present']}")
        print(f"rate limit: {rep['rate_limit']}")
        print(f"\nADZUNA: {rep['status']}")
    # Never non-zero on Adzuna alone — it must not block Phase 7B (§41).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
