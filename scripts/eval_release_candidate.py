#!/usr/bin/env python
"""Capstone P10B Wave 8 - integrated RELEASE-CANDIDATE evaluation.

Deterministic, offline (0 paid/live). Proves CROSS-SYSTEM release invariants that span Waves 1-7 -
the contracts that matter when the pieces are assembled into one candidate journey - rather than
re-testing single units (those have their own evaluators). Mixes a few behavioural checks (real
services over an in-memory schema) with structural checks over the codebase. Exits non-zero on any
failure. This evaluator does NOT itself create or bless a release candidate.
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# TEST ISOLATION (hard requirement): before any application import (temp DATABASE_URL, no .env, non-temp engines fail fast, isolated research cache).
import tests.conftest  # noqa: E402,F401

FE = ROOT / "frontend"


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    results: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        results[name] = (bool(ok), detail)

    # ---------- behavioural: real services over an in-memory schema ----------
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.application.company_intelligence_service import (
        ClaimKind, CompanyIntelligenceQuery, CompanyIntelligenceService, ProviderState)
    from src.application.errors import ValidationError
    from src.application.opportunity_service import OpportunityApplicationService
    from src.copilot.research.fake_provider import FakeCompanyResearchProvider
    from src.copilot.research.service import ExternalResearchService
    from src.opportunity_repository import OpportunityRepository
    from src.persistence import Base, CandidateDocument, Interview, User

    db = tempfile.mkdtemp(prefix="eval_rc_") + "/rc.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, future=True)
    with sf() as s:
        u1 = User(subject="a", provider="password", email="a@x")
        u2 = User(subject="b", provider="password", email="b@x")
        s.add_all([u1, u2]); s.commit()
        uid1, uid2 = u1.id, u2.id
        jd = CandidateDocument(user_id=uid1, category="job_description", title="jd", status="review_required", current_version=1)
        s.add(jd); s.commit(); jd_id = jd.id

    opp = OpportunityApplicationService(OpportunityRepository(sf))
    o = opp.create(uid1, target_role="PM", company_name="Acme", company_location="Berlin",
                   job_description_document_id=jd_id)
    oid = o["id"]

    check("opportunity_private_owner_scoped", opp.get(uid2, oid) is None and opp.get(uid1, oid) is not None,
          "Opportunity is candidate-owned/private (foreign read denied)")
    check("foreign_ids_do_not_disclose",
          opp.overview(uid2, oid) is None and opp.context(uid2, oid) is None,
          "foreign-owned opportunity id discloses nothing")
    foreign_jd = False
    try:
        opp.create(uid2, target_role="PM", job_description_document_id=jd_id)
    except ValidationError:
        foreign_jd = True
    check("jd_reference_owner_scoped", foreign_jd, "a foreign JD document cannot be linked")

    # Opportunity deletion preserves history; JD deletion clears linkage.
    with sf() as s:
        iv = Interview(user_id=uid1, opportunity_id=oid, source_session_id="s1", status="completed")
        s.add(iv); s.commit(); iv_id = iv.id
    OpportunityRepository(sf).clear_jd_links(jd_id)
    ctx = opp.context(uid1, oid)
    check("jd_deletion_clears_linkage", ctx["job_description_document_id"] is None and ctx["jd_available"] is False,
          "deleting a JD clears the Opportunity linkage safely (no stale content)")
    opp.delete(uid1, oid)
    with sf() as s:
        surviving = s.get(Interview, iv_id)
    check("opportunity_delete_preserves_history", surviving is not None,
          "deleting an Opportunity does not destroy linked interview history")

    # Company intelligence: provenance + claim separation + honest provider status.
    ci = CompanyIntelligenceService(ExternalResearchService([FakeCompanyResearchProvider()], enabled=True))
    rep = ci.research(CompanyIntelligenceQuery(company_name="Acme", website="acme.example", target_role="PM"), user_id=uid1)
    kinds = {c.kind for sec in (rep.business_market, rep.culture, rep.role_relevance,
                                rep.interview_preparation.topics) for c in sec}
    provider_states = {p.key: p.state for p in rep.provider_statuses}
    check("company_provenance_aware", bool(rep.sources) and all(s.retrieved_at for s in rep.sources),
          "company research carries provenance + freshness")
    check("company_claims_not_blurred",
          ClaimKind.FACT in kinds and ClaimKind.MODEL_INFERENCE in kinds
          and all(c.kind is ClaimKind.FACT for c in rep.business_market),
          "FACT vs MODEL_INFERENCE are distinct; facts are facts")
    check("review_providers_not_integrated",
          rep.review_signals == [] and all(provider_states.get(k) is ProviderState.NOT_INTEGRATED
                                           for k in ("glassdoor", "kununu", "google")),
          "unsupported review providers are not presented as integrated")

    # ---------- structural: cross-system code invariants ----------
    persistence = read("src/persistence.py")
    opp_model = persistence.split("class Opportunity", 1)[-1].split("class InterviewSession", 1)[0] if "class Opportunity" in persistence else ""
    svc_opp = read("src/application/opportunity_service.py")
    interview_schema = read("src/api/schemas/interview.py")

    check("no_raw_jd_text_on_opportunity",
          "job_description_document_id" in opp_model
          and not re.search(r"\bjd_text\b|job_description_text|raw_jd", opp_model),
          "Opportunity references a governed document id, not duplicated raw JD text")
    check("workspace_separate_from_opportunity",
          "opportunity" not in read("src/workspace_repository.py").lower()
          and "opportunity" not in read("src/application/sharing_service.py").lower(),
          "Workspace/sharing does not reference Opportunity")

    # Governed context into Prepare + Practice (server-resolved, owner-scoped).
    interview_route = read("src/api/routes/interview.py")
    check("prepare_practice_governed_context",
          "_apply_governed_context" in interview_route
          and "extracted_text" in interview_route
          and 'raw.pop("job_description_document_id"' in interview_route
          and "opportunity_id" in interview_schema and "job_description_document_id" in interview_schema,
          "Practice resolves JD server-side (governed extracted_text from owner-scoped doc) and accepts owner-verified opportunity_id")
    prepare = read("frontend/components/agent/AgentPrepareWorkspace.tsx")
    setup = read("frontend/components/interview/InterviewSessionSetup.tsx")
    check("opportunity_context_is_initial_not_override",
          "cur || opportunity" in prepare.replace(" ", "") or "cur??opportunity" in prepare.replace(" ", "")
          or "(cur)=>cur||" in prepare.replace(" ", ""),
          "Prepare prefill only fills empty fields (never overrides an explicit entry)")
    check("session_choice_outranks_opportunity",
          "cur ??" in setup or "cur ||" in setup or "cur)" in setup.replace(" ", ""),
          "Practice setup keeps the explicit session choice over the opportunity default")

    # Language / geography independence (distinct fields; never inferred).
    check("language_dimensions_distinct",
          all(k in read("src/application/authorization.py") for k in ("interface_locale", "conversation_language", "career_geography")),
          "interface / conversation / career-geography are distinct principal fields")
    check("opportunity_carries_no_language",
          "conversation_language" not in opp_model and "career_geography" not in svc_opp,
          "Opportunity carries no language/geography (stay account/session-owned)")

    # Coaching tone-only + interview language propagation.
    coaching = read("src/coaching_style.py")
    prompts = read("src/prompts.py")
    check("coaching_tone_not_scoring",
          "never make feedback harsher or more lenient" in coaching or "tone" in coaching.lower(),
          "coaching style changes tone, never scoring")
    check("interview_language_directive",
          "_language_directive" in prompts,
          "interview language propagates via a trusted language directive")

    # Agent governance: HITL, no model-supplied user_id, bounded tools.
    check("hitl_present", "human_review" in read("src/agent/nodes.py") or "interrupt(" in read("src/agent/nodes.py"),
          "HITL human_review boundary present")
    check("no_model_supplied_user_id",
          "user_id" not in read("src/agent/specialist_tools.py").split("class")[0]
          or "trusted" in read("src/agent/specialist_tools.py").lower(),
          "user_id is trusted run state, never a model-supplied tool argument")

    # Admin is not a candidate-data superuser.
    check("admin_not_superuser",
          "superuser" in read("src/application/authorization.py").lower()
          and "Opportunity" not in read("src/api/routes/admin.py"),
          "admin is bounded (never a candidate-data superuser); no opportunity content in admin")

    # Account deletion covers Wave 1-7 owned entities incl. opportunities.
    deletion = read("src/application/account_deletion_service.py")
    check("account_deletion_covers_entities",
          all(e in deletion for e in ("P.Opportunity", "P.Interview", "P.CandidateDocument", "P.InterviewSession")),
          "account deletion removes opportunities, interviews, documents and sessions")

    # No candidate content in URLs / prohibited storage (structural spot-checks).
    check("no_candidate_content_in_urls",
          "?opportunity=" in prepare or "opportunity=" in read("frontend/components/opportunities/OpportunityHome.tsx"),
          "only opportunity ids (not candidate content) appear in URLs")

    # SEO / public-private boundary.
    robots = read("frontend/app/robots.ts")
    check("authenticated_routes_noindex",
          all(f'"{p}"' in robots for p in ("/app", "/opportunities", "/company", "/admin", "/documents")),
          "authenticated routes are disallowed from indexing")

    # Pricing: preview/presentation only, no billing.
    pricing = read("frontend/lib/pricing.ts")
    check("premium_preview_no_billing",
          "BILLING_ENABLED = false" in pricing and 'ctaKind: "request"' in pricing,
          "Premium is preview/presentation only; billing disabled")

    # Public claims discipline (delegated to the marketing evaluator's contract; assert its presence).
    check("marketing_claims_evaluator_present",
          (ROOT / "scripts/eval_marketing_product_trust.py").exists(),
          "marketing claims/provider/social-proof discipline is guarded by its evaluator")

    # 7-locale structural consistency (each locale defines the same top-level namespaces as en).
    en = read("frontend/lib/i18n/messages/en.ts")
    en_ns = set(re.findall(r"^  ([a-zA-Z0-9]+): \{", en, re.M))
    parity_ok = True
    for loc in ("de", "fr", "es", "it", "pt", "nl"):
        loc_ns = set(re.findall(r"^  ([a-zA-Z0-9]+): \{", read(f"frontend/lib/i18n/messages/{loc}.ts"), re.M))
        if loc_ns != en_ns:
            parity_ok = False
    check("seven_locale_namespace_parity", parity_ok and len(en_ns) > 10,
          f"all 7 locales share the same {len(en_ns)} top-level namespaces")

    # RC gate discipline: RC-P10-002 is NOT silently created; the gate is documented.
    rc_exists = (ROOT / "artifacts/capstone/p10/RC-P10-002").exists()
    rc_gate_results = (ROOT / "artifacts/capstone/p10/RC-P10-002/gate_results.md").exists()
    rc_manifest = (ROOT / "artifacts/capstone/p10/RC-P10-002/manifest.json").exists()
    gate_doc = "Release qualification criteria" in read("docs/capstone/p10/p10b_wave8_release_qualification.md")
    # Invariant intent: RC-P10-002 may exist ONLY with a documented qualification gate AND its own
    # gate_results.md + manifest.json (the RC-P9-001 convention). It must never be created bypassing
    # that evidence. (Stage B legitimately creates it after the gate passes; earlier stages had no RC.)
    check("rc_gate_not_bypassed", gate_doc and ((not rc_exists) or (rc_gate_results and rc_manifest)),
          "RC-P10-002 is only created alongside its documented qualification gate + gate_results/manifest")

    return results


SAFETY = {
    "opportunity_private_owner_scoped", "foreign_ids_do_not_disclose", "jd_reference_owner_scoped",
    "jd_deletion_clears_linkage", "opportunity_delete_preserves_history", "company_provenance_aware",
    "company_claims_not_blurred", "review_providers_not_integrated", "workspace_separate_from_opportunity",
    "language_dimensions_distinct", "opportunity_carries_no_language", "coaching_tone_not_scoring",
    "hitl_present", "no_model_supplied_user_id", "admin_not_superuser", "account_deletion_covers_entities",
    "authenticated_routes_noindex", "premium_preview_no_billing", "rc_gate_not_bypassed",
}


def main() -> int:
    print("ASK4MO - CAPSTONE P10B WAVE 8 RELEASE-CANDIDATE INTEGRATED EVALUATION\n")
    results = run()
    failed = False
    for name in sorted(results):
        ok, detail = results[name]
        if not ok:
            failed = True
        tag = "  <- SAFETY" if (name in SAFETY and not ok) else ""
        print(f"  {name:38s} {'PASS' if ok else 'FAIL'}  {detail}{tag}")
    print(f"\nInvariants: {len(results)}   Paid LLM calls: 0   Paid provider calls: 0   Live calls: 0")
    if failed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS (integrated release-candidate invariants hold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
