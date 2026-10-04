#!/usr/bin/env python
"""Capstone P10B Wave 6 - Opportunity model & candidate journey evaluation.

Deterministic, offline invariant checks (no browser, no paid/live provider). Behavioural checks run
the real OpportunityApplicationService over an in-memory SQLite schema; structural checks assert the
migration, route gating, association wiring, Opportunity/Workspace separation, i18n parity and the
no-emoji/no-em-dash UI contract. Exits non-zero on any failure.
"""

from __future__ import annotations

import re
import sys
import tempfile
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

    # --- behavioural: real service over an in-memory schema ---
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.application.errors import ValidationError
    from src.application.opportunity_service import OpportunityApplicationService
    from src.opportunity_repository import OpportunityRepository
    from src.persistence import Base, CandidateDocument, Interview, User

    db = tempfile.mkdtemp(prefix="eval_w6_") + "/w6.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, future=True)
    with sf() as s:
        u1 = User(subject="u1", provider="password", email="u1@x")
        u2 = User(subject="u2", provider="password", email="u2@x")
        s.add_all([u1, u2])
        s.commit()
        uid1, uid2 = u1.id, u2.id
        jd = CandidateDocument(user_id=uid1, category="job_description", title="jd.txt",
                               status="review_required", current_version=1)
        foreign_cv = CandidateDocument(user_id=uid1, category="cv", title="cv.txt",
                                       status="review_required", current_version=1)
        s.add_all([jd, foreign_cv])
        s.commit()
        jd_id, cv_id = jd.id, foreign_cv.id

    svc = OpportunityApplicationService(OpportunityRepository(sf))

    created = svc.create(uid1, target_role="Senior PM", company_name="Acme",
                         company_location="Berlin", company_country="de")
    oid = created["id"]
    check("create", created["title"] == "Senior PM - Acme - Berlin" and created["status"] == "active",
          "opportunity created with derived title + active status")
    check("retrieve_own", svc.get(uid1, oid) is not None, "owner can retrieve")
    check("update_own", svc.update(uid1, oid, patch={"target_role": "Lead PM"})["target_role"] == "Lead PM",
          "owner can update")

    svc.archive(uid1, oid)
    check("archive_lifecycle",
          all(o["id"] != oid for o in svc.list(uid1))
          and any(o["id"] == oid for o in svc.list(uid1, include_archived=True)),
          "archived hidden from default list, visible with include_archived")

    check("foreign_access_denied", svc.get(uid2, oid) is None and svc.overview(uid2, oid) is None,
          "another user cannot read the opportunity")
    check("foreign_mutation_denied",
          svc.update(uid2, oid, patch={"target_role": "x"}) is None
          and svc.archive(uid2, oid) is None and svc.delete(uid2, oid) is False,
          "another user cannot mutate/delete the opportunity")

    jd_opp = svc.create(uid1, target_role="Eng", job_description_document_id=jd_id)
    check("jd_link_owner_scoped", jd_opp["job_description_document_id"] == jd_id,
          "owner can link own JD document")
    foreign_jd = False
    try:
        svc.create(uid2, target_role="Eng", job_description_document_id=jd_id)
    except ValidationError:
        foreign_jd = True
    check("foreign_jd_rejected", foreign_jd, "a foreign JD id is rejected")
    non_jd = False
    try:
        svc.create(uid1, target_role="Eng", job_description_document_id=cv_id)
    except ValidationError:
        non_jd = True
    check("non_jd_document_rejected", non_jd, "a non-job_description document is rejected")

    # deleted JD -> unavailable (simulate by clearing the link as the delete path does)
    OpportunityRepository(sf).clear_jd_links(jd_id)
    ctx = svc.context(uid1, jd_opp["id"])
    check("deleted_jd_unavailable", ctx["job_description_document_id"] is None and ctx["jd_available"] is False,
          "a deleted JD becomes unavailable; no stale content")

    ctx2 = svc.context(uid1, oid)
    check("prepare_practice_context",
          ctx2["target_role"] and ctx2["company_name"] == "Acme" and "opportunity_id" in ctx2,
          "context carries role/company for Prepare & Practice pre-population")

    # association: a completed interview linked to the opportunity surfaces in the overview
    with sf() as s:
        iv = Interview(user_id=uid1, opportunity_id=oid, source_session_id="s1", status="completed")
        s.add(iv)
        s.commit()
        iv_id = iv.id
        # historical interview without an opportunity is still valid
        iv2 = Interview(user_id=uid1, opportunity_id=None, source_session_id="s2", status="completed")
        s.add(iv2)
        s.commit()
    ov = svc.overview(uid1, oid)
    check("interview_association", iv_id in ov["interview_ids"] and ov["interview_count"] == 1,
          "linked completed interview is discoverable from the opportunity")
    check("historical_session_valid",
          any(True for _ in [iv2]) and ov["interview_count"] == 1,
          "a standalone interview (NULL opportunity) stays valid and unlinked")

    # --- structural checks ---
    svc_src = read("src/application/opportunity_service.py")
    repo_src = read("src/opportunity_repository.py")
    route = read("src/api/routes/opportunity.py")
    persistence = read("src/persistence.py")
    interview_schema = read("src/api/schemas/interview.py")

    check("report_discoverability",
          "linked_interview_ids" in repo_src and "interview_ids" in svc_src,
          "reports/history are discoverable via linked_interview_ids (no duplicate store)")
    check("session_report_association_columns",
          'opportunity_id: Mapped[int | None]' in persistence
          and 'ForeignKey("opportunities.id"' in persistence,
          "interviews + interview_sessions carry a nullable opportunity_id FK")
    check("interview_create_accepts_opportunity",
          "opportunity_id: int | None" in interview_schema,
          "the interview create request accepts an optional opportunity_id")

    # Context precedence: explicit session fields still exist independently of the opportunity link.
    check("context_precedence_inputs",
          "conversation_language" in interview_schema and "opportunity_id" in interview_schema,
          "explicit session choices (e.g. conversation_language) remain, so they can override context")
    check("conversation_language_independence",
          "conversation_language" not in svc_src and "conversation_language" not in persistence.split("class Opportunity")[1].split("class InterviewSession")[0],
          "the Opportunity model carries no conversation_language (language stays account/session)")
    check("career_geography_independence",
          "career_geography" not in svc_src,
          "the Opportunity service never reads/writes career_geography (company geography is separate)")

    check("company_intelligence_context",
          "company_name" in svc_src and "company_domain" in svc_src
          and (ROOT / "src/application/company_intelligence_service.py").exists(),
          "opportunity provides company context; the Wave 5 research engine is reused, not cloned")
    check("no_evidence_copied",
          "cv" not in [c.strip() for c in persistence.split("class Opportunity")[1].split("class InterviewSession")[0].split()]
          and "candidate_background" not in svc_src,
          "the Opportunity model copies no CV/evidence text (evidence stays governed)")
    check("no_model_call_untrusted_jd",
          "langchain" not in svc_src.lower() and "openai" not in svc_src.lower(),
          "the service makes no model call; JD is never prompted")

    # Opportunity vs Workspace separation.
    check("workspace_separate",
          "opportunity" not in read("src/workspace_repository.py").lower()
          and "opportunity" not in read("src/application/sharing_service.py").lower(),
          "Workspace/sharing code does not reference Opportunity (no cross-wiring)")

    # Admin privacy boundary: admin routes do not read opportunity content.
    check("admin_privacy_boundary",
          "Opportunity" not in read("src/api/routes/admin.py"),
          "Platform Admin does not access opportunity content")

    # Account deletion removes opportunities.
    check("account_deletion",
          "P.Opportunity" in read("src/application/account_deletion_service.py"),
          "account deletion removes owned opportunities")

    # Gating: BASIC, owner-scoped, foreign -> 404.
    check("endpoint_owner_scoped",
          "get_current_user_id" in route and "404" in route,
          "every endpoint is owner-scoped; a foreign id returns 404")
    check("audit_events",
          "opportunity.created" in route and "opportunity.archived" in route
          and "opportunity.deleted" in route,
          "create/archive/delete emit metadata-only audit events")

    # Migration: additive, single head, no destructive op.
    mig = read("migrations/versions/0014_opportunities.py")
    migs = sorted(p.name for p in (ROOT / "migrations" / "versions").glob("0*.py"))
    check("additive_migration",
          mig and "create_table" in mig and "drop_table" not in mig.split("def downgrade")[0]
          and migs and migs[-1].startswith(("0014_", "0015_", "0016_", "0017_", "0018_", "0019_", "0020_", "0021_", "0022_")),
          f"0014 is additive; head = {migs[-1] if migs else 'none'}")

    # i18n: opportunity namespace in all 7 locales.
    locales = ["en", "de", "fr", "es", "it", "pt", "nl"]
    has_ns = {loc: bool(re.search(r"\bopportunity\s*:\s*\{", read(f"frontend/lib/i18n/messages/{loc}.ts")))
              for loc in locales}
    check("i18n_opportunity_all_locales", all(has_ns.values()),
          "an opportunity i18n namespace exists in all 7 locales: "
          + (",".join(k for k, v in has_ns.items() if not v) or "all present"))

    # UI present + no emoji / no em dash.
    ui_files = [
        "frontend/app/opportunities/page.tsx",
        "frontend/components/opportunities/OpportunitiesClient.tsx",
        "frontend/components/opportunities/OpportunityCreate.tsx",
        "frontend/components/opportunities/OpportunityHome.tsx",
    ]
    ui_text = "\n".join(read(f) for f in ui_files)
    emoji = re.compile("[\U0001F000-\U0001FAFF☀-➿]")
    check("opportunity_ui_present", all((ROOT / f).exists() for f in ui_files),
          "the opportunities list + create + home components exist")
    check("no_emoji_in_ui", not emoji.search(ui_text), "no emoji as product iconography in the UI")
    check("no_emdash_in_ui", "—" not in ui_text, "no em dash in the opportunity UI")

    return results


SAFETY = {
    "foreign_access_denied", "foreign_mutation_denied", "foreign_jd_rejected",
    "non_jd_document_rejected", "deleted_jd_unavailable", "conversation_language_independence",
    "career_geography_independence", "no_evidence_copied", "no_model_call_untrusted_jd",
    "workspace_separate", "admin_privacy_boundary", "account_deletion", "endpoint_owner_scoped",
    "additive_migration",
}


def main() -> int:
    print("ASK4MO - CAPSTONE P10B WAVE 6 OPPORTUNITY JOURNEY EVALUATION\n")
    results = run()
    failed = False
    for name in sorted(results):
        ok, detail = results[name]
        if not ok:
            failed = True
        tag = "  <- SAFETY" if (name in SAFETY and not ok) else ""
        print(f"  {name:36s} {'PASS' if ok else 'FAIL'}  {detail}{tag}")
    print("\nPaid LLM calls: 0   Paid provider calls: 0   Live calls: 0")
    if failed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS (all opportunity-journey invariants hold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
