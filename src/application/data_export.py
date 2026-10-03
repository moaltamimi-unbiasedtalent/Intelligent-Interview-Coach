"""Candidate data export (P10B-W9.8): one owner-scoped, bounded JSON document.

Everything here is read with the caller's authenticated ``user_id`` (never a browser-supplied id) and
projected through an explicit column policy: private-file storage keys, token hashes, provider secrets,
prompts and internal telemetry are never included. The result is plain JSON-serialisable data.

Scope is truthful and stated IN the document (``scope.included`` / ``scope.not_included``) so the
candidate can see what a download does and does not contain. Nothing is persisted or cached: the file is
built on demand, so there is no export artefact to expire or leak. W10 (admin GDPR operations) can reuse
:func:`build_candidate_export` as the single export seam.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select

from src import persistence as P

EXPORT_FORMAT = "ask4mo.candidate-export.v1"

INCLUDED = (
    "account", "preferences", "opportunities", "documents (metadata, extracted claims; not the files)",
    "stories", "memories", "interviews (questions, your answers, evaluations, reports)",
    "feedback you submitted", "workspace memberships", "items you share",
    "support tickets you opened and the messages in them that you can see",
    "your plan and its assignment history (access assignments only; Ask4Mo has no payment records)",
    "your recorded acceptances of the Terms, Privacy notice and AI transparency versions",
    "the privacy requests you submitted (type, status and result category; not internal handling records)",
    "an index of your preparation-chat runs (identifiers and status only)",
)
NOT_INCLUDED = (
    "the original uploaded files (download them from Documents)",
    "security and audit records kept by the platform",
    "legal-acceptance history (Ask4Mo does not record it yet)",
    "other people's data, including content shared with you",
    "internal prompts, model reasoning and provider secrets",
    "internal notes written by support staff (they are operational records, not part of your visible conversation)",
    "the content of your preparation-chat runs (only identifiers and status are listed; extracting chat content is not yet supported)",
    "acceptances from before acceptance recording existed (none were recorded)",
)

# Columns that must never leave the server even though they sit on a user-owned row.
_EXCLUDE = {"storage_key", "content_hash", "token_hash", "password_hash", "checksum"}


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _row(obj: Any, exclude: tuple[str, ...] = ()) -> dict[str, Any]:
    skip = _EXCLUDE | set(exclude)
    return {c.name: _jsonable(getattr(obj, c.name)) for c in obj.__table__.columns if c.name not in skip}


def build_candidate_export(*, user_id: int, session_factory, repo, account: Any) -> dict[str, Any]:
    """Assemble the caller's export. ``repo`` is the InterviewRepository (completed history)."""
    with session_factory() as s:
        def mine(model, order=None, col="user_id"):
            stmt = select(model).where(getattr(model, col) == user_id)
            if order is not None:
                stmt = stmt.order_by(order)
            return s.scalars(stmt).all()

        prefs = s.scalar(select(P.UserPreference).where(P.UserPreference.user_id == user_id))
        docs = mine(P.CandidateDocument, P.CandidateDocument.id)
        doc_ids = [d.id for d in docs]
        versions = (s.scalars(select(P.DocumentVersion).where(P.DocumentVersion.document_id.in_(doc_ids))
                              .order_by(P.DocumentVersion.id)).all() if doc_ids else [])
        claims = (s.scalars(select(P.DocumentClaim).where(P.DocumentClaim.document_id.in_(doc_ids))
                            .order_by(P.DocumentClaim.id)).all() if doc_ids else [])
        stories = mine(P.CandidateStory, P.CandidateStory.id)
        memberships = s.execute(
            select(P.WorkspaceMembership, P.Workspace.name)
            .join(P.Workspace, P.Workspace.id == P.WorkspaceMembership.workspace_id)
            .where(P.WorkspaceMembership.user_id == user_id)
        ).all()
        shares = mine(P.ShareGrant, P.ShareGrant.id, col="owner_user_id")
        data = {
            "preferences": _row(prefs, ("id", "user_id")) if prefs else None,
            "opportunities": [_row(o, ("user_id",)) for o in mine(P.Opportunity, P.Opportunity.id)],
            "documents": [
                {**_row(d, ("user_id",)),
                 "versions": [_row(v) for v in versions if v.document_id == d.id],
                 "claims": [_row(c) for c in claims if c.document_id == d.id]}
                for d in docs
            ],
            "stories": [_row(st, ("user_id",)) for st in stories],
            "memories": [_row(m, ("user_id",)) for m in mine(P.PreparationMemory, P.PreparationMemory.id)],
            "feedback": [_row(f, ("user_id",)) for f in mine(P.UserFeedback, P.UserFeedback.id)],
            "workspace_memberships": [
                {"workspace": name, "role": m.role, "status": m.status,
                 "joined": _jsonable(m.created_at)} for m, name in memberships
            ],
            "shares": [_row(g, ("owner_user_id",)) for g in shares],
        }
    # W10.4: the candidate's own plan and subscription history (access assignments only: no payment data exists).
    from src.plans_repository import PlanRepository

    data["plan"] = PlanRepository(session_factory).subject_plan(user_id=user_id)
    # W10.3: the candidate-visible support conversation. Admin-only internal notes are NEVER exported here.
    from src.support_repository import SupportRepository

    data["support_tickets"] = SupportRepository(session_factory).export_for_owner(user_id)
    # W10.10: recorded legal acceptances, the candidate-visible privacy requests and the preparation-run index (ids/status only).
    from src.privacy.legal import LegalService
    from src.privacy.requests import PrivacyRequestService

    data["legal_acceptances"] = LegalService(session_factory).export_for_user(user_id)
    data["privacy_requests"] = PrivacyRequestService(session_factory).export_for_owner(user_id)
    with session_factory() as s2:
        data["preparation_runs"] = [{"run_id": r.run_id, "state": r.state, "source": r.source, "created_at": _jsonable(r.created_at)}
                                    for r in s2.scalars(select(P.PreparationRun).where(P.PreparationRun.owner_user_id == user_id)
                                                        .order_by(P.PreparationRun.id)).all()]
    history = repo.export_user_data(user_id)
    return {
        "format": EXPORT_FORMAT,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {"included": list(INCLUDED), "not_included": list(NOT_INCLUDED)},
        "account": {
            "user_id": user_id,
            "email": getattr(account, "email", None),
            "tier": getattr(account, "tier", None),
            "status": getattr(account, "status", None),
            "email_verified": bool(getattr(account, "email_verified", False)),
        },
        "legal_acceptance": {"recorded": False},
        **data,
        "interviews": history.get("interviews", []),
        # Back-compat with the pre-W9.8 shape consumers may have saved.
        "data": history,
    }
