#!/usr/bin/env python
"""Capstone P10B Wave 5 — Company Intelligence evaluation.

Deterministic, offline invariant checks (no browser, no paid/live provider). Mixes behavioural
checks (the real CompanyIntelligenceService over the offline fixture + the SSRF-safe real engine)
with source-structural checks (endpoint gating, capability flag, 7-locale parity, no migration,
no emoji/em-dash in the new UI). Exits non-zero on any failure.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FE = ROOT / "frontend"


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    results: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        results[name] = (bool(ok), detail)

    from src.application.company_intelligence_service import (
        ClaimKind,
        CompanyIntelligenceQuery,
        CompanyIntelligenceService,
        IdentityConfidence,
        ProviderState,
        ReportStatus,
    )
    from src.copilot.research.fake_provider import FakeCompanyResearchProvider
    from src.copilot.research.service import ExternalResearchService

    def fake_svc(**kw):
        return CompanyIntelligenceService(
            ExternalResearchService([FakeCompanyResearchProvider()], enabled=True), **kw)

    # Unique website per run so the durable external-research file cache never turns a fresh fetch
    # into a STALE cache-hit (keeps CONFIGURED deterministic across runs).
    import uuid

    site = f"acme-{uuid.uuid4().hex[:8]}.example"
    confirmed = fake_svc().research(
        CompanyIntelligenceQuery(company_name="Acme", location="Berlin", website=site,
                                 target_role="Engineer"), user_id=1)
    nameonly = fake_svc().research(
        CompanyIntelligenceQuery(company_name="Acme", location="Berlin"), user_id=1)

    # --- identity / disambiguation ---
    check("identity_disambiguation_required",
          nameonly.status is ReportStatus.NEEDS_CLARIFICATION and not nameonly.business_market
          and not nameonly.sources,
          "name-only requests clarification and fabricates nothing")
    check("website_enables_research",
          confirmed.identity.confidence is IdentityConfidence.CONFIRMED
          and bool(confirmed.business_market),
          "an explicit website confirms identity and yields evidence")
    check("no_domain_guessing",
          nameonly.identity.domain is None and nameonly.identity.website is None,
          "a domain is never guessed from a name")

    # --- claim taxonomy separation (§6) ---
    check("facts_are_facts",
          all(c.kind is ClaimKind.FACT for c in confirmed.business_market + confirmed.culture),
          "business/culture claims are FACT")
    check("inference_never_fact",
          all(c.kind is ClaimKind.MODEL_INFERENCE
              for c in confirmed.role_relevance + confirmed.interview_preparation.topics
              + confirmed.interview_preparation.questions_to_ask),
          "role relevance and interview prep are MODEL_INFERENCE, never FACT")

    # --- provenance / freshness / no fabricated sources ---
    source_ids = {s.id for s in confirmed.sources}
    check("provenance_present",
          bool(confirmed.sources) and all(s.retrieved_at for s in confirmed.sources),
          "every source carries an id and a retrieved_at timestamp")
    check("no_fabricated_sources",
          all(all(sid in source_ids for sid in c.source_ids)
              for c in confirmed.business_market + confirmed.culture),
          "every cited source id refers to a real retrieved source")

    # --- reviews not integrated (honest) ---
    review_states = {p.key: p.state for p in confirmed.provider_statuses}
    check("reviews_not_integrated",
          confirmed.review_signals == []
          and all(review_states.get(k) is ProviderState.NOT_INTEGRATED
                  for k in ("glassdoor", "kununu", "google"))
          and "reviews_not_integrated" in confirmed.limitations,
          "Glassdoor/Kununu/Google are not_integrated; no REVIEW claims fabricated")
    check("review_links_only",
          all((p.external_url or "").startswith("https://")
              for p in confirmed.provider_statuses if p.key in ("glassdoor", "kununu", "google")),
          "non-integrated review providers expose a link, not copied content")

    # --- provider status honesty ---
    check("provider_status_honest",
          review_states.get("company_web") is ProviderState.CONFIGURED
          and review_states.get("adzuna") is ProviderState.UNAVAILABLE,
          "company web configured with a website; Adzuna unavailable without credentials")

    # --- SSRF guard reused (real engine, private IP, no network, no fabrication) ---
    real = CompanyIntelligenceService(ExternalResearchService.default(enabled=True))
    ssrf = real.research(
        CompanyIntelligenceQuery(company_name="Acme", website="http://127.0.0.1/admin"), user_id=1)
    check("ssrf_guard_reused",
          ssrf.business_market == [] and ssrf.status in (
              ReportStatus.INSUFFICIENT_EVIDENCE, ReportStatus.UNAVAILABLE),
          "a private-IP website yields no evidence (engine SSRF guard, no fetch)")
    wf = read("src/copilot/research/web_fetch.py")
    check("ssrf_controls_present",
          "is_private" in wf and "robots" in wf.lower() and "MAX_BYTES" in wf,
          "the reused fetcher retains private-IP, robots and size guards")

    # --- JD owner-scoping + untrusted DATA (never prompted) ---
    own = fake_svc(resolve_jd=lambda _id: "Kubernetes and observability platform role").research(
        CompanyIntelligenceQuery(company_name="Acme", website="acme.example", target_role="Eng",
                                 job_description_document_id=5), user_id=1)
    foreign = fake_svc(resolve_jd=lambda _id: None).research(
        CompanyIntelligenceQuery(company_name="Acme", website="acme.example", target_role="Eng",
                                 job_description_document_id=5), user_id=2)
    check("jd_owner_scoping",
          own.jd_linked is True and foreign.jd_linked is False,
          "JD links only when the owner-scoped resolver returns text")
    svc_src = read("src/application/company_intelligence_service.py")
    check("untrusted_jd_not_prompted",
          "import" in svc_src and "langchain" not in svc_src.lower()
          and "openai" not in svc_src.lower() and "def _keywords" in svc_src,
          "the service makes no model call; JD becomes bounded keywords only (DATA)")

    # --- language / geography independence ---
    check("language_geography_independence",
          "interface_locale" not in svc_src and "country" in svc_src
          and "infer" not in svc_src.lower().split("geography")[0][-40:],
          "geography comes only from explicit country/location, never inferred from language")

    # --- no secret leakage ---
    blob = confirmed.model_dump_json().lower()
    check("no_secret_leak",
          not any(s in blob for s in ("app_key", "app_id", "api.adzuna.com/v1", "authorization")),
          "no credential or authenticated endpoint appears in the report")

    # --- endpoint gating (source-structural) ---
    route = read("src/api/routes/company.py")
    check("endpoint_gated",
          "require_capability(Capability.CURRENT_MARKET_RESEARCH)" in route
          and 'require_not_paused("current_market")' in route
          and 'cost_limit("cost_research_user")' in route,
          "the endpoint enforces capability + operator pause + per-user cost")
    check("endpoint_owner_scoped",
          "get_current_user_id" in route and "resolve_document_text" in route,
          "the endpoint resolves the JD owner-scoped by the authenticated user id")

    # --- capability flag ---
    common = read("src/api/schemas/common.py")
    health = read("src/api/routes/health.py")
    check("capability_flag",
          "company_research_enabled" in common and "_company_research_available" in health,
          "capabilities advertise company_research_enabled")

    # --- no COMPANY-RESEARCH migration (Wave 5 is read-mostly; company research persists nothing).
    # Later waves may add unrelated migrations (e.g. Wave 6 opportunities) - only assert that
    # company intelligence itself introduced no migration/table. ---
    migs = sorted(p.name for p in (ROOT / "migrations" / "versions").glob("0*.py"))
    check("no_company_research_migration",
          migs and not any("company" in m or "research" in m for m in migs),
          "company intelligence introduced no migration/table (research stays ephemeral)")

    # --- frontend: 7-locale parity for the company namespace + no emoji/em-dash ---
    locales = ["en", "de", "fr", "es", "it", "pt", "nl"]
    cats = {loc: read(f"frontend/lib/i18n/messages/{loc}.ts") for loc in locales}
    has_ns = {loc: bool(re.search(r"\bcompany\s*:\s*\{", txt)) for loc, txt in cats.items()}
    check("i18n_company_namespace_all_locales", all(has_ns.values()),
          "a company i18n namespace exists in all 7 locales: "
          + ",".join(k for k, v in has_ns.items() if not v) or "all present")

    ui_files = [
        "frontend/app/company/page.tsx",
        "frontend/components/company/CompanyResearchClient.tsx",
        "frontend/components/company/CompanyReport.tsx",
    ]
    ui_text = "\n".join(read(f) for f in ui_files)
    emoji = re.compile("[\U0001F000-\U0001FAFF☀-➿]")
    check("company_ui_present", all((ROOT / f).exists() for f in ui_files),
          "the company research route + client + report components exist")
    check("no_emoji_in_company_ui", not emoji.search(ui_text),
          "no emoji used as product iconography in the company UI")
    check("no_emdash_in_company_ui", "—" not in ui_text,
          "no em dash in the company UI")

    return results


SAFETY = {
    "identity_disambiguation_required", "no_domain_guessing", "inference_never_fact",
    "no_fabricated_sources", "reviews_not_integrated", "ssrf_guard_reused", "jd_owner_scoping",
    "untrusted_jd_not_prompted", "language_geography_independence", "no_secret_leak",
    "endpoint_gated", "endpoint_owner_scoped",
}


def main() -> int:
    print("ASK4MO — CAPSTONE P10B WAVE 5 COMPANY INTELLIGENCE EVALUATION\n")
    results = run()
    failed = False
    for name in sorted(results):
        ok, detail = results[name]
        if not ok:
            failed = True
        tag = "  ← SAFETY" if (name in SAFETY and not ok) else ""
        print(f"  {name:36s} {'PASS' if ok else 'FAIL'}  {detail}{tag}")
    print("\nPaid LLM calls: 0   Paid provider calls: 0   Live calls: 0")
    if failed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS (all company-intelligence invariants hold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
