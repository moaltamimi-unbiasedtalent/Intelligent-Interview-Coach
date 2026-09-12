#!/usr/bin/env python
"""Deterministic external-research evaluation (Phase 7F, §62).

No network, no live provider call, no paid LLM. Exercises the bounded external-research layer
with fake providers/transports over evaluations/external_research/cases.json and measures:
policy correctness (local-first), provider routing, source classification, SSRF safety,
prompt-injection safety, provider-failure isolation, citation completeness, geography, freshness
metadata, and secret safety (no credentials / authenticated URLs ever surface).

Exit 0 when every SAFETY category is 100% and the overall pass rate meets --min-pass.

Usage:
    python scripts/eval_external_research.py
    python scripts/eval_external_research.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.knowledge.providers import adzuna as az  # noqa: E402
from src.copilot.research import content_guard, web_fetch  # noqa: E402
from src.copilot.research.adzuna_provider import AdzunaResearchProvider  # noqa: E402
from src.copilot.research.models import (  # noqa: E402
    CurrentMarketResearchRequest, Geography, ResearchIntent)
from src.copilot.research.policy import classify_external_need  # noqa: E402
from src.copilot.research.service import ExternalResearchService  # noqa: E402

CASES = "evaluations/external_research/cases.json"
SAFETY_CATEGORIES = ("ssrf", "injection", "secret_safety", "provider_isolation")


class _FakeAz:
    """A fake underlying AdzunaProvider for scenario simulation (no network)."""

    def __init__(self, scenario: str) -> None:
        self.scenario = scenario

    def search_jobs(self, **kw):
        if self.scenario == "adzuna_rate_limit":
            raise az.AdzunaError("rate limited", status=429, category="rate_limit")
        if self.scenario == "adzuna_error":
            raise az.AdzunaError("boom", category="network")
        if self.scenario == "adzuna_empty":
            return az.AdzunaResult(ok=True, status=200, count=0, data={"count": 0, "results": []})
        job = {"id": "1", "title": "Product Manager",
               "company": {"display_name": "Acme"}, "location": {"display_name": "Berlin"},
               "category": {"label": "IT Jobs"}, "created": "2026-09-10T00:00:00Z",
               "salary_min": 70000, "salary_max": 90000, "salary_is_predicted": "0",
               "redirect_url": "https://www.adzuna.de/land/ad/1?utm=x",
               "description": "Own the roadmap."}
        return az.AdzunaResult(ok=True, status=200, count=3169,
                               data={"count": 3169, "results": [job]})


def _blob_has_secret(obj) -> bool:
    # Detect actual credential VALUES / authenticated URLs — NOT the safe env-var names that a
    # "credentials not configured" warning legitimately mentions.
    blob = json.dumps(obj, default=str).lower()
    return ("app_key=" in blob or "app_id=" in blob
            or "api.adzuna.com/v1/api/jobs" in blob      # authenticated API URL host+path
            or "testkey" in blob or "testid" in blob)    # our synthetic credential values


def evaluate(cases: list[dict]) -> dict:
    results = []
    for c in cases:
        kind = c["kind"]
        ok = True
        detail = ""
        try:
            if kind == "policy":
                need = classify_external_need(c["query"], has_company_url=c.get("has_company_url", False))
                ok = need.needs_external == c["needs_external"]
                if ok and c.get("intent"):
                    ok = need.intent is not None and need.intent.value == c["intent"]
                detail = f"needs_external={need.needs_external} intent={need.intent}"

            elif kind == "routing":
                svc = ExternalResearchService.default()
                req = CurrentMarketResearchRequest(
                    intent=ResearchIntent(c["intent"]), role="x",
                    company_url=c.get("company_url"))
                prov = svc._select(req)
                if c.get("expected_provider") is None:
                    ok = prov is None
                else:
                    ok = prov is not None and prov.provider_name == c["expected_provider"] \
                        and prov.source_category.value == c["expected_source"]
                detail = f"provider={(prov.provider_name if prov else None)}"

            elif kind == "ssrf":
                blocked = False
                try:
                    # force resolution to public so ONLY the policy (scheme/ip/host) decides
                    web_fetch.validate_url(c["url"])
                except web_fetch.WebFetchError:
                    blocked = True
                ok = (blocked == c["expected_blocked"])
                detail = f"blocked={blocked}"

            elif kind == "injection":
                _title, text = web_fetch.extract_text(c["page"])
                guarded = content_guard.guard_external_text(text)
                ok = (guarded.flagged == c["expected_flagged"])
                # content must be returned as bounded DATA (a string), never executed
                ok = ok and isinstance(guarded.text, str)
                detail = f"flagged={guarded.flagged} indicators={guarded.indicators[:2]}"

            elif kind == "provider":
                scen = c["scenario"]
                if scen == "adzuna_no_creds":
                    for v in ("ADZUNA_APP_ID", "ADZUNA_APP_KEY"):
                        os.environ.pop(v, None)
                    prov = AdzunaResearchProvider()
                else:
                    os.environ["ADZUNA_APP_ID"] = "TESTID"
                    os.environ["ADZUNA_APP_KEY"] = "TESTKEY"
                    prov = AdzunaResearchProvider(provider=_FakeAz(scen))
                res = prov.research(CurrentMarketResearchRequest(
                    intent=ResearchIntent.JOB_MARKET, role="product manager",
                    location=Geography(country="DE"), results_limit=5))
                for v in ("ADZUNA_APP_ID", "ADZUNA_APP_KEY"):
                    os.environ.pop(v, None)
                ok = res.status.value == c["expected_status"]
                if ok and c.get("expected_geo"):
                    ok = res.geography is not None and res.geography.country == c["expected_geo"]
                # secret + citation + freshness safety on any produced evidence
                secret_leak = _blob_has_secret(res.model_dump(mode="json"))
                cite_ok = all(e.provider and e.retrieved_at for e in res.evidence)
                if res.evidence:
                    # public redirect URL only; never the authenticated API URL
                    cite_ok = cite_ok and all(
                        (e.public_url or "").startswith("https://") and "app_key" not in (e.public_url or "")
                        for e in res.evidence)
                ok = ok and not secret_leak and cite_ok
                detail = f"status={res.status.value} secret_leak={secret_leak} cite_ok={cite_ok}"
        except Exception as exc:  # noqa: BLE001 - a crash is a failure, never silent
            ok = False
            detail = f"EXC {type(exc).__name__}: {exc}"
        results.append({"case_id": c["case_id"], "kind": kind, "passed": ok, "detail": detail})

    total = len(results)
    passed = sum(1 for r in results if r["passed"])

    def _cat_rate(kind_or_group):
        rel = [r for r in results if r["kind"] == kind_or_group]
        return (round(sum(1 for r in rel if r["passed"]) / len(rel), 4), len(rel)) if rel else (None, 0)

    by_kind = {k: _cat_rate(k) for k in sorted({r["kind"] for r in results})}
    summary = {
        "cases": total, "passed": passed, "pass_rate": round(passed / total, 4) if total else 0.0,
        "policy_correctness": by_kind.get("policy"),
        "provider_routing": by_kind.get("routing"),
        "ssrf_safety": by_kind.get("ssrf"),
        "prompt_injection_safety": by_kind.get("injection"),
        "provider_failure_isolation": by_kind.get("provider"),
    }
    # Safety gate: ssrf + injection + provider (isolation/secret/citation) must be 100%.
    safety_ok = all((by_kind.get(k, (None, 0))[0] in (None, 1.0)) for k in ("ssrf", "injection", "provider"))
    return {"summary": summary, "results": results, "safety_ok": safety_ok}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Deterministic external-research evaluation.")
    ap.add_argument("--cases", default=CASES)
    ap.add_argument("--min-pass", type=float, default=0.95)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    data = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    cases = data["cases"] if isinstance(data, dict) else data
    report = evaluate(cases)
    s = report["summary"]
    if args.json:
        print(json.dumps(s, indent=2))
    else:
        print("EXTERNAL RESEARCH EVALUATION")
        print(f"  cases: {s['cases']}  passed: {s['passed']}  pass_rate: {s['pass_rate']}")
        for k in ("policy_correctness", "provider_routing", "ssrf_safety",
                  "prompt_injection_safety", "provider_failure_isolation"):
            print(f"  {k}: {s[k]}")
        fails = [r for r in report["results"] if not r["passed"]]
        for r in fails[:20]:
            print(f"    FAIL [{r['kind']}] {r['case_id']}: {r['detail']}")
    ok = report["safety_ok"] and s["pass_rate"] >= args.min_pass
    print(f"\nGATE: {'PASS' if ok else 'FAIL'} (min_pass={args.min_pass}, safety must be 100%)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
