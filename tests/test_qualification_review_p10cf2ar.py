# ruff: noqa: F811  (pytest fixtures are imported from the sibling P10C-F2A-Q test module and used by name)
"""P10C-F2A-R: the human review and approval workflow (reviewer authority, validated batch decisions, alias decisions, audit, revocation), the alias evidence review and the packet logic.
FULLY OFFLINE: synthetic data, throwaway SQLite databases and SYNTHETIC test accounts (test fixtures only; no identity of any real environment is created or used)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import select

from src.application import admin_audit as A
from src.knowledge_foundation import us_alias_review as AR
from src.knowledge_foundation import us_sources as U
from src.knowledge_foundation.aliases import AliasError, AliasStore
from src.knowledge_foundation.compensation.resolver import CompensationRequest
from src.knowledge_foundation.compensation.store import CompensationStoreV2
from src.knowledge_foundation.occupation_resolver import MultilingualRequest, ResolutionOutcome
from src.knowledge_foundation.qualification_review import (REVIEWER_ROLES, BatchScope, QualificationReviewService, ReviewAuthorityError, ReviewValidationError, appointment_readiness,
                                                           assert_separation_of_duties, reviewer_authority, reviewer_check_for)
from src.persistence import AuditEvent, CompensationRecordV2Row as R, GraphOccupationAlias, User
from tests.test_us_qualification_p10cf2aq import _alias, _ask, files, sf, world  # noqa: F401  (fixtures)

ROOT = Path(__file__).resolve().parents[1]
SCOPE = BatchScope("bls_oews", "May 2025", "detailed", "annual", "median")


def _user(sf, role, status="active", n=[0]):
    n[0] += 1
    with sf() as s:
        u = User(subject=f"synthetic-test-{n[0]}", provider="synthetic-test", platform_role=role, status=status, display_name="synthetic test fixture")
        s.add(u)
        s.commit()
        return u.id


@pytest.fixture()
def svc(world):
    levels = {n.code: n.level for n in world.st}
    now = iter(f"2026-10-18T12:00:{i:02d}+00:00" for i in range(60))
    from datetime import datetime
    return QualificationReviewService(world.sf, world.reg, lambda: levels, lambda: True, now=lambda: datetime.fromisoformat(next(now)))


@pytest.fixture()
def checked(world):
    for r in world.store.records_for([i for i in range(1, 40)], "US"):
        world.store.set_qualification(r["record_key"], "engineering_checked", actor_user_id=None)
    return world


# ------------------------------------------------------------------------------------------------------------------------------------------ authority
def test_authority_is_the_current_database_state_of_an_active_account_with_the_knowledge_approval_permission(world):
    ok_ka, ok_pa = _user(world.sf, "knowledge_admin"), _user(world.sf, "platform_admin")
    deny = {"support": _user(world.sf, "support_operator"), "candidate": _user(world.sf, "user"), "inactive": _user(world.sf, "knowledge_admin", status="deactivated")}
    with world.sf() as s:
        assert reviewer_authority(s, ok_ka, "measurement_reviewer").id == ok_ka and reviewer_authority(s, ok_pa, "release_approver").id == ok_pa
        for uid in deny.values():
            with pytest.raises(ReviewAuthorityError):
                reviewer_authority(s, uid, "measurement_reviewer")
        for bad in (None, 999999):
            with pytest.raises(ReviewAuthorityError):
                reviewer_authority(s, bad, "alias_reviewer")                                  # no invented identity is accepted
        with pytest.raises(ReviewAuthorityError):
            reviewer_authority(s, ok_ka, "release_approver")                                  # knowledge_admin lacks releases.read
        with pytest.raises(ReviewAuthorityError):
            reviewer_authority(s, ok_ka, "unknown_role")
    assert set(REVIEWER_ROLES) == {"measurement_reviewer", "alias_reviewer", "release_approver"}
    with pytest.raises(ReviewAuthorityError):
        assert_separation_of_duties(ok_pa, ok_pa)
    assert_separation_of_duties(ok_ka, ok_pa)


def test_a_role_downgrade_takes_effect_on_the_next_call(world):
    uid = _user(world.sf, "knowledge_admin")
    with world.sf() as s:
        assert reviewer_authority(s, uid, "alias_reviewer")
        s.get(User, uid).platform_role = "support_operator"
        s.commit()
        with pytest.raises(ReviewAuthorityError):
            reviewer_authority(s, uid, "alias_reviewer")


def test_appointment_readiness_counts_without_identities(world):
    with world.sf() as s:
        assert appointment_readiness(s)["eligible_by_role"] == {"measurement_reviewer": 0, "alias_reviewer": 0, "release_approver": 0}
    _user(world.sf, "knowledge_admin")
    _user(world.sf, "platform_admin")
    with world.sf() as s:
        r = appointment_readiness(s)
    assert r["eligible_by_role"] == {"measurement_reviewer": 2, "alias_reviewer": 2, "release_approver": 1} and "email" not in str(r)


def test_low_level_qualified_transition_can_demand_a_verified_reviewer(world):
    store = CompensationStoreV2(world.sf, world.reg, world.g, reviewer_check=reviewer_check_for(world.sf, "measurement_reviewer"))
    key = store.records_for([1], "US")[0]["record_key"]
    store.set_qualification(key, "engineering_checked", actor_user_id=None)
    with pytest.raises(ValueError):
        store.set_qualification(key, "qualified", actor_user_id=424242)                        # an arbitrary integer is not a reviewer
    uid = _user(world.sf, "knowledge_admin")
    assert store.set_qualification(key, "qualified", actor_user_id=uid)["qualification_status"] == "qualified"
    aliases = AliasStore(world.sf, reviewer_check=reviewer_check_for(world.sf, "alias_reviewer"))
    a = _alias(world, "11-1011", "Syn Checked Worker")
    with pytest.raises(AliasError):
        aliases.set_qualification(a["id"], "qualified", actor_user_id=424242)


# --------------------------------------------------------------------------------------------------------------------------------------- batch decisions
def test_batch_validation_is_reproducible_and_lists_exceptions(checked, svc):
    v1, v2 = svc.validate_batch(SCOPE), svc.validate_batch(SCOPE)
    assert v1["digest"] == v2["digest"] and v1["records"] == v1["eligible_records"] and v1["exceptions"] == [] and v1["source"]["approval_status"] == "approved_for_ingestion"
    other = svc.validate_batch(BatchScope("bls_oews", "May 2025", "detailed", "annual", "mean"))
    assert other["digest"] != v1["digest"]


def test_nothing_is_decided_without_a_verified_reviewer_digest_and_exception_acknowledgement(checked, svc):
    v = svc.validate_batch(SCOPE)
    kw = dict(scope=SCOPE, validation_digest=v["digest"], decision="approve", reason="reviewed", acknowledged_exceptions=0)
    for bad in (None, 31337, _user(checked.sf, "support_operator")):
        with pytest.raises(ReviewAuthorityError):
            svc.decide_batch(reviewer_user_id=bad, **kw)
    rid = _user(checked.sf, "knowledge_admin")
    with pytest.raises(ReviewValidationError):
        svc.decide_batch(reviewer_user_id=rid, **{**kw, "validation_digest": "0" * 64})              # stale or wrong digest
    with pytest.raises(ReviewValidationError):
        svc.decide_batch(reviewer_user_id=rid, **{**kw, "acknowledged_exceptions": 3})
    with pytest.raises(ReviewValidationError):
        svc.decide_batch(reviewer_user_id=rid, **{**kw, "reason": " "})
    with pytest.raises(ReviewValidationError):
        svc.decide_batch(reviewer_user_id=rid, **{**kw, "decision": "auto"})
    with checked.sf() as s:
        assert {r.qualification_status for r in s.scalars(select(R))} == {"engineering_checked"}        # still nothing qualified


def test_an_explicit_approval_qualifies_only_the_scope_and_is_audited_per_record(checked, svc):
    rid = _user(checked.sf, "knowledge_admin")
    v = svc.validate_batch(SCOPE)
    out = svc.decide_batch(reviewer_user_id=rid, scope=SCOPE, validation_digest=v["digest"], decision="approve", reason="batch reviewed against the criteria", acknowledged_exceptions=0, request_id="req-1")
    assert out["qualified"] == v["records"] > 0
    with checked.sf() as s:
        ev = s.get(AuditEvent, out["audit_ref"])
        assert ev.event_type == A.ADMIN_FOUNDATION_QUALIFICATION_DECIDED and ev.actor_user_id == rid and ev.context["decision"] == "approve" and ev.context["validation_digest"] == v["digest"]
        q = list(s.scalars(select(R).where(R.qualification_status == "qualified")))
        assert len(q) == v["records"] and all(r.occupation_level == "detailed" and r.pay_period == "annual" and r.measure == "median" for r in q)      # nothing outside the scope
        hist = q[0].provenance["qualification_history"][-1]
        assert hist["actor_user_id"] == rid and hist["audit_ref"] == ev.id and hist["to"] == "qualified" and hist["at"].startswith("2026-10-18")
        assert {r.qualification_status for r in s.scalars(select(R).where(R.measure == "mean"))} <= {"engineering_checked", "unqualified"}
    # qualified evidence is still NOT operational: the source has no runtime approval
    r = _ask(checked, code="11-1011")
    assert r.operational is False and r.candidate_presentable is False and not checked.reg.can_serve_as_evidence("bls_oews")


def test_a_rejection_changes_no_state_and_is_still_audited(checked, svc):
    rid = _user(checked.sf, "knowledge_admin")
    v = svc.validate_batch(SCOPE)
    out = svc.decide_batch(reviewer_user_id=rid, scope=SCOPE, validation_digest=v["digest"], decision="reject", reason="criteria not met", acknowledged_exceptions=0)
    assert out["qualified"] == 0
    with checked.sf() as s:
        assert s.get(AuditEvent, out["audit_ref"]).context["decision"] == "reject" and not list(s.scalars(select(R).where(R.qualification_status == "qualified")))


def test_exceptions_are_excluded_inventoried_and_left_unchanged(checked, svc):
    with checked.sf() as s:
        r = s.scalars(select(R).where(R.measure == "median", R.pay_period == "annual", R.occupation_level == "detailed")).first()
        r.provenance = {**r.provenance, "archive_sha256": "bad"}                                      # incomplete provenance -> an exception
        bad_key = r.record_key
        s.commit()
    v = svc.validate_batch(SCOPE)
    assert [e["record_key"] for e in v["exceptions"]] == [bad_key] and v["eligible_records"] == v["records"] - 1
    rid = _user(checked.sf, "knowledge_admin")
    with pytest.raises(ReviewValidationError):
        svc.decide_batch(reviewer_user_id=rid, scope=SCOPE, validation_digest=v["digest"], decision="approve", reason="x", acknowledged_exceptions=0)     # must acknowledge the real number
    out = svc.decide_batch(reviewer_user_id=rid, scope=SCOPE, validation_digest=v["digest"], decision="approve", reason="x", acknowledged_exceptions=1)
    assert out["exceptions_left_unchanged"] == 1
    with checked.sf() as s:
        assert s.scalar(select(R.qualification_status).where(R.record_key == bad_key)) == "engineering_checked"


def test_revocation_returns_the_batch_to_engineering_checked_and_keeps_history(checked, svc):
    rid = _user(checked.sf, "knowledge_admin")
    v = svc.validate_batch(SCOPE)
    ap = svc.decide_batch(reviewer_user_id=rid, scope=SCOPE, validation_digest=v["digest"], decision="approve", reason="ok", acknowledged_exceptions=0)
    with pytest.raises(ReviewAuthorityError):
        svc.revoke_batch(reviewer_user_id=_user(checked.sf, "user"), audit_ref=ap["audit_ref"], reason="x")
    with pytest.raises(ReviewValidationError):
        svc.revoke_batch(reviewer_user_id=rid, audit_ref=999999, reason="x")
    rv = svc.revoke_batch(reviewer_user_id=rid, audit_ref=ap["audit_ref"], reason="correction")
    assert rv["revoked_records"] == ap["qualified"]
    with checked.sf() as s:
        assert not list(s.scalars(select(R).where(R.qualification_status == "qualified")))
        h = s.scalars(select(R).where(R.record_key.in_(svc.validate_batch(SCOPE)["eligible_keys"][:1]))).first().provenance["qualification_history"]
        assert [x["to"] for x in h][-2:] == ["qualified", "engineering_checked"] and h[-1]["revokes"] == ap["audit_ref"]
        assert s.get(AuditEvent, rv["audit_ref"]).event_type == A.ADMIN_FOUNDATION_QUALIFICATION_REVOKED


def test_an_unapproved_or_revoked_source_blocks_approval(checked, svc):
    rid = _user(checked.sf, "knowledge_admin")
    v = svc.validate_batch(SCOPE)
    checked.reg.transition("bls_oews", "restricted", reason="synthetic revocation")
    v2 = svc.validate_batch(SCOPE)
    assert v2["outcomes"].get("INSUFFICIENT") == v["records"] and v2["digest"] != v["digest"]
    with pytest.raises(ReviewValidationError):
        svc.decide_batch(reviewer_user_id=rid, scope=SCOPE, validation_digest=v2["digest"], decision="approve", reason="x", acknowledged_exceptions=len(v2["exceptions"]))


def test_audit_events_are_registered_and_carry_no_record_values(checked, svc):
    assert {A.ADMIN_FOUNDATION_QUALIFICATION_DECIDED, A.ADMIN_FOUNDATION_QUALIFICATION_REVOKED, A.ADMIN_FOUNDATION_ALIAS_DECIDED, A.ADMIN_FOUNDATION_ALIAS_REVOKED} <= A.ADMIN_EVENT_NAMES
    rid = _user(checked.sf, "knowledge_admin")
    v = svc.validate_batch(SCOPE)
    out = svc.decide_batch(reviewer_user_id=rid, scope=SCOPE, validation_digest=v["digest"], decision="approve", reason="ok", acknowledged_exceptions=0)
    with checked.sf() as s:
        ctx = s.get(AuditEvent, out["audit_ref"]).context
    assert not any(k in ctx for k in ("value", "values", "title", "email", "records_detail")) and "41392" not in str(ctx)


# ------------------------------------------------------------------------------------------------------------------------------------------ alias decisions
def test_alias_decision_needs_a_verified_alias_reviewer_an_attestation_and_an_engineering_checked_alias(world, svc):
    a = _alias(world, "11-1011", "Syn Reviewed Worker")
    rid = _user(world.sf, "knowledge_admin")
    with pytest.raises(ReviewValidationError):
        svc.decide_alias(reviewer_user_id=rid, alias_id=a["id"], decision="approve", reason="ok", evidence_reviewed=True)              # still unqualified: not engineering-checked
    world.aliases.set_qualification(a["id"], "engineering_checked", actor_user_id=None)
    for bad in (None, 777, _user(world.sf, "support_operator")):
        with pytest.raises(ReviewAuthorityError):
            svc.decide_alias(reviewer_user_id=bad, alias_id=a["id"], decision="approve", reason="ok", evidence_reviewed=True)
    with pytest.raises(ReviewValidationError):
        svc.decide_alias(reviewer_user_id=rid, alias_id=a["id"], decision="approve", reason="ok", evidence_reviewed=False)
    out = svc.decide_alias(reviewer_user_id=rid, alias_id=a["id"], decision="approve", reason="definition and scope reviewed", evidence_reviewed=True)
    assert out["qualification_status"] == "qualified"
    with world.sf() as s:
        row = s.get(GraphOccupationAlias, a["id"])
        h = row.provenance["qualification_history"][-1]
        assert h["actor_user_id"] == rid and h["audit_ref"] == out["audit_ref"] and s.get(AuditEvent, out["audit_ref"]).event_type == A.ADMIN_FOUNDATION_ALIAS_DECIDED
    rv = svc.revoke_alias(reviewer_user_id=rid, alias_id=a["id"], reason="correction")
    assert rv["status"] == "deprecated" and rv["qualification_status"] == "engineering_checked"
    assert world.occ.resolve(MultilingualRequest(title="Syn Reviewed Worker", title_language="en", country="US")).outcome is ResolutionOutcome.NOT_FOUND


def test_a_rejected_alias_stops_resolving(world, svc):
    a = _alias(world, "11-1011", "Syn Rejected Worker")
    world.aliases.set_qualification(a["id"], "engineering_checked", actor_user_id=None)
    rid = _user(world.sf, "knowledge_admin")
    assert world.occ.resolve(MultilingualRequest(title="Syn Rejected Worker", title_language="en", country="US")).outcome is ResolutionOutcome.RESOLVED
    assert svc.decide_alias(reviewer_user_id=rid, alias_id=a["id"], decision="reject", reason="scope too broad", evidence_reviewed=True)["status"] == "deprecated"
    assert world.occ.resolve(MultilingualRequest(title="Syn Rejected Worker", title_language="en", country="US")).outcome is ResolutionOutcome.NOT_FOUND


# ------------------------------------------------------------------------------------------------------------------- alias relationship kinds and safety
def test_the_alias_architecture_distinguishes_exact_context_dependent_ambiguous_and_unsupported(world):
    a1 = _alias(world, "11-1011", "Syn Exact Title", provenance={"country_applicability": ["US"], "relationship": "exact"})
    assert a1["relationship"] == "exact"
    r = world.occ.resolve(MultilingualRequest(title="Syn Exact Title", title_language="en", country="US"))
    assert r.outcome is ResolutionOutcome.RESOLVED and r.candidates[0].evidence["alias_relationship"] == "exact"
    node2 = world.g.find_by_identifier("soc", "11-1012", "2018")[0]["occupation_key"]
    _alias(world, "11-1011", "Syn Shared Title", context_terms=["alpha"], provenance={"country_applicability": ["US"], "relationship": "context_dependent"})
    world.aliases.add_alias(node2, "Syn Shared Title", language="en", language_basis="curated_manual", alias_type="recognized_title", source_ref=U.SOC_SOURCE, taxonomy=("soc", "2018"),
                            context_terms=["beta"], provenance={"country_applicability": ["US"], "relationship": "context_dependent"})
    amb = world.occ.resolve(MultilingualRequest(title="Syn Shared Title", title_language="en", country="US"))
    assert amb.outcome is ResolutionOutcome.AMBIGUOUS and len(amb.candidates) == 2                                       # ambiguous without context
    ctx = world.occ.resolve(MultilingualRequest(title="Syn Shared Title", title_language="en", country="US", role_context="alpha team"))
    alpha_key = world.g.find_by_identifier("soc", "11-1011", "2018")[0]["occupation_key"]
    assert ctx.outcome is ResolutionOutcome.RESOLVED and ctx.candidates[0].occupation_key == alpha_key        # curated context narrows deterministically to the matching occupation
    none_ctx = world.occ.resolve(MultilingualRequest(title="Syn Shared Title", title_language="en", country="US", role_context="gamma team"))
    assert none_ctx.outcome is ResolutionOutcome.AMBIGUOUS                                                   # context that matches no candidate never picks one
    assert world.occ.resolve(MultilingualRequest(title="Syn Totally Unknown", title_language="en", country="US")).outcome is ResolutionOutcome.NOT_FOUND


def test_a_scope_caveat_travels_with_the_compensation_answer(world):
    a = _alias(world, "11-1011", "Syn Narrow Title", provenance={"country_applicability": ["US"], "relationship": "narrower", "limitation": "figure covers the wider official occupation"})
    assert a["limitation"]
    r = world.res.resolve(CompensationRequest(occupation=MultilingualRequest(title="Syn Narrow Title", title_language="en"), country="US", require_operational=False, pay_period="annual", measure="median"))
    assert r.value == "41392" and any("figure covers the wider official occupation" in x for x in r.coverage_limitations)


# --------------------------------------------------------------------------------------------------------------------------------- alias evidence review
def test_alias_review_vocabulary_and_codes_validate_against_the_structure(files):  # noqa: F811
    st = U.parse_soc_structure(files[0])
    defs = U.parse_soc_definitions(files[1])
    with pytest.raises(ValueError):
        AR.build_alias_reviews(st, defs)                                                                                     # the synthetic structure lacks the real SOC codes: unknown code is an error
    assert set(AR.RECOMMENDATIONS) == {"APPROVE_RECOMMENDED", "CONDITIONAL_APPROVAL_RECOMMENDED", "AMBIGUOUS", "INSUFFICIENT_EVIDENCE"}


def _staging():
    return U.locate_staging(ROOT / "docs/capstone/p10/p10c_f2a/acquisition_manifest.json")


@pytest.mark.skipif(_staging() is None, reason="staged BLS files not present in this environment")
def test_real_alias_reviews_are_recommendations_only_and_never_invent_a_mapping():
    st = _staging()
    structure = U.parse_soc_structure(st / "raw/soc_structure_2018.xlsx")
    defs = U.parse_soc_definitions(st / "raw/soc_2018_definitions.xlsx")
    rv = AR.build_alias_reviews(structure, defs)
    assert [a["recommendation"] for a in rv["aliases"]] == ["APPROVE_RECOMMENDED", "APPROVE_RECOMMENDED", "APPROVE_RECOMMENDED", "CONDITIONAL_APPROVAL_RECOMMENDED", "CONDITIONAL_APPROVAL_RECOMMENDED"]
    assert all("no human decision exists" in a["status"] for a in rv["aliases"] + rv["unresolved_titles"])
    assert {u["title"] for u in rv["unresolved_titles"]} == {"Data Analyst", "Product Manager"} and all("target" not in u for u in rv["unresolved_titles"])      # no mapping for either
    assert all(a["target_detail"]["definition_excerpt"] and a["competing_detail"] for a in rv["aliases"])
    assert rv["counts"] == {"APPROVE_RECOMMENDED": 3, "CONDITIONAL_APPROVAL_RECOMMENDED": 2, "AMBIGUOUS": 1, "INSUFFICIENT_EVIDENCE": 1}


# ------------------------------------------------------------------------------------------------------------------------------------- packet logic
def test_packet_script_partitions_the_records_without_loss(checked, svc, tmp_path):
    spec = importlib.util.spec_from_file_location("p10c_f2ar_packet", ROOT / "scripts/p10c_f2ar_packet.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    b = mod.batches(svc, checked.sf, tmp_path)
    assert b["records_in_groups"] == len(checked.recs) and b["groups_needing_individual_assessment"] == 0 and b["groups_batch_eligible"] == len(b["groups"])
    mean = next(g for g in b["groups"] if g["group"] == "detailed/annual/mean")
    med = next(g for g in b["groups"] if g["group"] == "detailed/annual/median")
    assert "mean wage RSE published" in mean["published_rse"] and "no RSE" in med["published_rse"] and med["samples"][0]["source_field"]
    tsv = (tmp_path / "measurement_review_per_record.tsv").read_text().splitlines()
    assert len(tsv) == len(checked.recs) + 1 and tsv[0].split("\t")[-4:] == ["reviewer_decision", "reviewer_user_id", "review_timestamp", "audit_ref"]
    assert all(line.split("\t")[-4:] == ["", "", "", ""] for line in tsv[1:])                    # no decision is pre-filled
