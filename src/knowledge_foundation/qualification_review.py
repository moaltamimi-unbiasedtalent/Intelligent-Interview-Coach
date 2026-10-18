"""P10C-F2A-R: the human review and approval workflow for measurement and alias qualification. It reuses the existing authority model and adds nothing parallel:

* **Authority** is the code-defined platform role preset: a reviewer is an ACTIVE ``User`` whose CURRENT role holds ``platform.knowledge.approve`` (the ``knowledge_admin`` and
  ``platform_admin`` presets). The check re-reads the database on every call (as the two-person role-change service does); nothing is read from a client. A release approver must also hold
  ``platform.releases.read`` (today only the ``platform_admin`` preset), and may not be the batch's measurement reviewer. Reviewer APPOINTMENT is the existing two-person role change
  (``RoleChangeService``): this module neither creates users nor assigns roles.
* **Authentication** happens at the API layer (``require_permission``); this service never authenticates and must only be called with the verified principal's ``user_id``. No route is
  exposed by this module (a privileged route is a separate, owner-authorised step).
* **Batch qualification** is never automatic. A batch is a defined scope; its validation results are recomputed from the stored records and summarised in a digest; the reviewer must
  submit that exact digest, so an approval is bound to reproducible results. Only ENGINEERING_CHECKED records of the scope are affected; exceptions are listed and left unchanged.
  The decision, the reviewer and the counts are audited IN THE SAME TRANSACTION as the state change; every affected record's history carries the reviewer, the timestamp and the audit
  reference, so the batch can be traced per record, revoked or corrected.
* A reviewer decision is never fabricated here: every public method needs a verified reviewer id."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from sqlalchemy import select

from src.application import admin_audit as A
from src.application.admin_permissions import KNOWLEDGE_APPROVE, permissions_for_role
from src.knowledge_foundation import enums as E
from src.knowledge_foundation import us_qualification as Q
from src.knowledge_foundation.compensation.record import from_row
from src.persistence import ACCOUNT_STATUS_ACTIVE, AuditEvent, GlobalSource, GraphOccupationAlias, User
from src.persistence import CompensationRecordV2Row as R

__all__ = ["appointment_readiness", "reviewer_check_for", "REVIEWER_ROLES", "ReviewAuthorityError", "ReviewValidationError", "BatchScope", "QualificationReviewService", "reviewer_authority", "assert_separation_of_duties"]

REVIEWER_ROLES = {
    "measurement_reviewer": frozenset({KNOWLEDGE_APPROVE}),
    "alias_reviewer": frozenset({KNOWLEDGE_APPROVE}),
    "release_approver": frozenset({KNOWLEDGE_APPROVE, "platform.releases.read"}),
}


class ReviewAuthorityError(PermissionError):
    """The actor is not an active human account whose current role holds the permissions the review role needs. Carries no identity detail."""


class ReviewValidationError(ValueError):
    """The review request is not acceptable (stale digest, empty scope, unapproved source, bad decision). Carries no record content."""


def reviewer_authority(session, user_id: int | None, role: str) -> User:
    """Re-read the CURRENT database authority. Raises ``ReviewAuthorityError`` for: no id, unknown user, inactive account, or a role preset lacking the needed permissions."""
    if role not in REVIEWER_ROLES:
        raise ReviewAuthorityError("unknown review role")
    user = session.get(User, int(user_id)) if user_id is not None else None
    if user is None or user.status != ACCOUNT_STATUS_ACTIVE:
        raise ReviewAuthorityError("a named, active reviewer account is required")
    if not REVIEWER_ROLES[role] <= permissions_for_role(user.platform_role):
        raise ReviewAuthorityError("the reviewer's current role does not hold the permissions this review needs")
    return user


def assert_separation_of_duties(measurement_reviewer_id: int, release_approver_id: int) -> None:
    """A runtime/release approval must come from a different person than the batch's measurement reviewer."""
    if measurement_reviewer_id == release_approver_id:
        raise ReviewAuthorityError("the release approver must differ from the measurement reviewer")


@dataclass(frozen=True)
class BatchScope:
    source_ref: str
    source_edition: str
    occupation_level: str | None = None        # detailed | broad
    pay_period: str | None = None              # annual | hourly
    measure: str | None = None                 # mean | median | percentile

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


def _digest(items: Iterable[tuple]) -> str:
    h = hashlib.sha256()
    for it in sorted(items):
        h.update(("\x1f".join(map(str, it)) + "\x1e").encode())
    return h.hexdigest()


class QualificationReviewService:
    def __init__(self, session_factory, registry, soc_levels: Callable[[], dict[str, str]], files_ok: Callable[[], bool], now: Callable[[], datetime] | None = None) -> None:
        self._sf, self._reg, self._levels, self._files_ok = session_factory, registry, soc_levels, files_ok
        self._now = now or (lambda: datetime.now(timezone.utc))

    # ----------------------------------------------------------------------------------------------------------------------------- validation
    def _rows(self, s, scope: BatchScope):
        stmt = select(R).where(R.source_ref == scope.source_ref, R.source_edition == scope.source_edition)
        for col, val in ((R.occupation_level, scope.occupation_level), (R.pay_period, scope.pay_period), (R.measure, scope.measure)):
            if val is not None:
                stmt = stmt.where(col == val)
        return list(s.scalars(stmt.order_by(R.id)))

    def validate_batch(self, scope: BatchScope) -> dict[str, Any]:
        """Reproducible validation of one batch (read-only): per-record outcome, exception inventory and a digest binding a later decision to exactly these results."""
        src = self._reg.get(scope.source_ref)
        if src is None:
            raise ReviewValidationError("unknown source")
        levels, ok = self._levels(), self._files_ok()
        with self._sf() as s:
            rows = self._rows(s, scope)
            keys: dict[str, int] = {}
            for r in rows:
                keys[r.record_key] = keys.get(r.record_key, 0) + 1
            outcomes: dict[str, int] = {}
            exceptions: list[dict[str, Any]] = []
            eligible: list[str] = []
            digest_items = []
            for r in rows:
                rec = {**from_row(r), "provenance": r.provenance, "batch_id": r.batch_id}
                outcome, why = Q.review_record(rec, source=src, file_integrity_ok=ok, soc_level=levels.get(r.native_code), key_count=keys[r.record_key])
                outcomes[outcome] = outcomes.get(outcome, 0) + 1
                digest_items.append((r.record_key, outcome, "|".join(why), r.qualification_status))
                if outcome == "ENGINEERING_CHECKED" and r.qualification_status == "engineering_checked":
                    eligible.append(r.record_key)
                else:
                    exceptions.append({"record_key": r.record_key, "native_code": r.native_code, "outcome": outcome, "state": r.qualification_status, "reasons": why})
        return {"scope": scope.as_dict(), "records": len(rows), "outcomes": outcomes, "eligible_records": len(eligible), "exceptions": exceptions, "digest": _digest(digest_items), "eligible_keys": eligible,
                "source": {"approval_status": src["approval_status"], "licence_status": src["licence_status"]}}

    # -------------------------------------------------------------------------------------------------------------------------------- decide
    def decide_batch(self, *, reviewer_user_id: int, scope: BatchScope, validation_digest: str, decision: str, reason: str, acknowledged_exceptions: int,
                     request_id: str | None = None) -> dict[str, Any]:
        """One explicit human decision on one batch. ``approve`` moves the eligible records to ``qualified``; ``reject`` records the refusal and changes no state."""
        if decision not in ("approve", "reject"):
            raise ReviewValidationError("decision must be approve or reject")
        if not (reason or "").strip():
            raise ReviewValidationError("a reviewer reason is required")
        v = self.validate_batch(scope)
        if v["records"] == 0:
            raise ReviewValidationError("the batch scope selects no records")
        if validation_digest != v["digest"]:
            raise ReviewValidationError("the validation results changed since they were reviewed: re-validate before deciding")
        if acknowledged_exceptions != len(v["exceptions"]):
            raise ReviewValidationError("the reviewer must acknowledge the exact number of exceptions in the inventory")
        with self._sf() as s:
            reviewer_authority(s, reviewer_user_id, "measurement_reviewer")
            src = self._reg.get(scope.source_ref)
            if decision == "approve":
                if src["approval_status"] not in ("approved_for_ingestion", "approved_for_runtime_use") or src["licence_status"] != "verified" or src["origin"] not in E.EVIDENCE_ORIGINS:
                    raise ReviewValidationError("the source is not approved for ingestion with a verified licence and a genuine origin")
                if v["eligible_records"] == 0:
                    raise ReviewValidationError("no record in the scope is eligible")
            spec = A.build_audit(event_type=A.ADMIN_FOUNDATION_QUALIFICATION_DECIDED, actor_user_id=int(reviewer_user_id), request_id=request_id, target_type="compensation_batch",
                                 target_id=scope.source_ref, result="success", reason=reason, decision=decision, source_id=scope.source_ref, source_edition=scope.source_edition,
                                 scope=scope.as_dict(), records=v["records"], eligible=v["eligible_records"], exceptions=len(v["exceptions"]), validation_digest=v["digest"])
            ev = AuditEvent(actor_user_id=spec["actor_user_id"], event_type=spec["event_type"], target_type=spec["target_type"], target_id=spec["target_id"], result="success",
                            request_id=request_id, context=spec["context"])
            s.add(ev)
            s.flush()
            moved = 0
            if decision == "approve":
                at = self._now().isoformat()
                wanted = set(v["eligible_keys"])
                for r in self._rows(s, scope):
                    if r.record_key in wanted and r.qualification_status == "engineering_checked":
                        hist = list((r.provenance or {}).get("qualification_history", []))
                        hist.append({"from": r.qualification_status, "to": "qualified", "actor_user_id": int(reviewer_user_id), "at": at, "audit_ref": ev.id, "batch_digest": v["digest"]})
                        r.provenance = {**(r.provenance or {}), "qualification_history": hist}
                        r.qualification_status = "qualified"
                        moved += 1
            s.commit()
            return {"audit_ref": ev.id, "decision": decision, "records_in_scope": v["records"], "qualified": moved, "exceptions_left_unchanged": len(v["exceptions"]), "digest": v["digest"]}

    def revoke_batch(self, *, reviewer_user_id: int, audit_ref: int, reason: str, request_id: str | None = None) -> dict[str, Any]:
        """Correction capability: every record qualified under ``audit_ref`` and still qualified returns to ``engineering_checked``; history and audit keep both decisions."""
        if not (reason or "").strip():
            raise ReviewValidationError("a reviewer reason is required")
        with self._sf() as s:
            reviewer_authority(s, reviewer_user_id, "measurement_reviewer")
            prior = s.get(AuditEvent, int(audit_ref))
            if prior is None or prior.event_type != A.ADMIN_FOUNDATION_QUALIFICATION_DECIDED or (prior.context or {}).get("decision") != "approve":
                raise ReviewValidationError("not an approval decision")
            spec = A.build_audit(event_type=A.ADMIN_FOUNDATION_QUALIFICATION_REVOKED, actor_user_id=int(reviewer_user_id), request_id=request_id, target_type="compensation_batch",
                                 target_id=prior.target_id, reason=reason, revoked_ref=int(audit_ref))
            ev = AuditEvent(actor_user_id=spec["actor_user_id"], event_type=spec["event_type"], target_type=spec["target_type"], target_id=spec["target_id"], result="success",
                            request_id=request_id, context=spec["context"])
            s.add(ev)
            s.flush()
            at, n = self._now().isoformat(), 0
            for r in s.scalars(select(R).where(R.source_ref == prior.target_id, R.qualification_status == "qualified")):
                hist = list((r.provenance or {}).get("qualification_history", []))
                if any(h.get("audit_ref") == int(audit_ref) and h.get("to") == "qualified" for h in hist):
                    hist.append({"from": "qualified", "to": "engineering_checked", "actor_user_id": int(reviewer_user_id), "at": at, "audit_ref": ev.id, "revokes": int(audit_ref)})
                    r.provenance = {**(r.provenance or {}), "qualification_history": hist}
                    r.qualification_status = "engineering_checked"
                    n += 1
            s.commit()
            return {"audit_ref": ev.id, "revoked_records": n}

    # ------------------------------------------------------------------------------------------------------------------------------- aliases
    def decide_alias(self, *, reviewer_user_id: int, alias_id: int, decision: str, reason: str, evidence_reviewed: bool, request_id: str | None = None) -> dict[str, Any]:
        """One alias at a time (never batched): the reviewer attests that the official definition, scope and competing occupations were reviewed."""
        if decision not in ("approve", "reject"):
            raise ReviewValidationError("decision must be approve or reject")
        if not (reason or "").strip() or evidence_reviewed is not True:
            raise ReviewValidationError("a reason and an explicit evidence-reviewed attestation are required")
        with self._sf() as s:
            reviewer_authority(s, reviewer_user_id, "alias_reviewer")
            a = s.get(GraphOccupationAlias, int(alias_id))
            if a is None or a.status != "current":
                raise ReviewValidationError("unknown or inactive alias")
            if a.qualification_status != "engineering_checked":
                raise ReviewValidationError("only an engineering-checked alias can be decided")
            origin = s.scalar(select(GlobalSource.origin).where(GlobalSource.source_id == a.source_ref))
            if decision == "approve" and origin not in E.EVIDENCE_ORIGINS:
                raise ReviewValidationError("the alias source has no genuine origin")
            spec = A.build_audit(event_type=A.ADMIN_FOUNDATION_ALIAS_DECIDED, actor_user_id=int(reviewer_user_id), request_id=request_id, target_type="occupation_alias", target_id=int(alias_id),
                                 reason=reason, decision=decision, alias_id=int(alias_id))
            ev = AuditEvent(actor_user_id=spec["actor_user_id"], event_type=spec["event_type"], target_type=spec["target_type"], target_id=spec["target_id"], result="success",
                            request_id=request_id, context=spec["context"])
            s.add(ev)
            s.flush()
            at = self._now().isoformat()
            hist = list((a.provenance or {}).get("qualification_history", []))
            if decision == "approve":
                hist.append({"from": a.qualification_status, "to": "qualified", "actor_user_id": int(reviewer_user_id), "at": at, "audit_ref": ev.id})
                a.qualification_status = "qualified"
            else:
                hist.append({"from": a.qualification_status, "to": a.qualification_status, "rejected_by": int(reviewer_user_id), "at": at, "audit_ref": ev.id})
                a.status = "deprecated"                                   # a rejected alias stops resolving; nothing is deleted
            a.provenance = {**(a.provenance or {}), "qualification_history": hist}
            s.commit()
            return {"audit_ref": ev.id, "decision": decision, "alias_id": int(alias_id), "qualification_status": a.qualification_status, "status": a.status}

    def revoke_alias(self, *, reviewer_user_id: int, alias_id: int, reason: str, request_id: str | None = None) -> dict[str, Any]:
        if not (reason or "").strip():
            raise ReviewValidationError("a reviewer reason is required")
        with self._sf() as s:
            reviewer_authority(s, reviewer_user_id, "alias_reviewer")
            a = s.get(GraphOccupationAlias, int(alias_id))
            if a is None:
                raise ReviewValidationError("unknown alias")
            spec = A.build_audit(event_type=A.ADMIN_FOUNDATION_ALIAS_REVOKED, actor_user_id=int(reviewer_user_id), request_id=request_id, target_type="occupation_alias", target_id=int(alias_id),
                                 reason=reason, alias_id=int(alias_id))
            ev = AuditEvent(actor_user_id=spec["actor_user_id"], event_type=spec["event_type"], target_type=spec["target_type"], target_id=spec["target_id"], result="success",
                            request_id=request_id, context=spec["context"])
            s.add(ev)
            s.flush()
            hist = list((a.provenance or {}).get("qualification_history", []))
            hist.append({"from": a.qualification_status, "to": "engineering_checked" if a.qualification_status == "qualified" else a.qualification_status, "actor_user_id": int(reviewer_user_id),
                         "at": self._now().isoformat(), "audit_ref": ev.id, "revoked": True})
            a.provenance = {**(a.provenance or {}), "qualification_history": hist}
            a.status = "deprecated"
            if a.qualification_status == "qualified":
                a.qualification_status = "engineering_checked"
            s.commit()
            return {"audit_ref": ev.id, "alias_id": int(alias_id), "status": a.status, "qualification_status": a.qualification_status}


def appointment_readiness(session) -> dict[str, Any]:
    """Counts only (never identities): how many ACTIVE accounts could serve each review role under their CURRENT role preset."""
    users = list(session.scalars(select(User).where(User.status == ACCOUNT_STATUS_ACTIVE)))
    out = {role: sum(1 for u in users if need <= permissions_for_role(u.platform_role)) for role, need in REVIEWER_ROLES.items()}
    return {"active_accounts": len(users), "eligible_by_role": out, "any_eligible_for_measurement_review": out["measurement_reviewer"] > 0}


def reviewer_check_for(session_factory, role: str) -> Callable[[int | None], bool]:
    """A hook for ``CompensationStoreV2``/``AliasStore`` so their low-level ``qualified`` transition also demands a verified, active reviewer account (production wiring)."""
    def check(user_id: int | None) -> bool:
        with session_factory() as s:
            try:
                reviewer_authority(s, user_id, role)
                return True
            except ReviewAuthorityError:
                return False
    return check
