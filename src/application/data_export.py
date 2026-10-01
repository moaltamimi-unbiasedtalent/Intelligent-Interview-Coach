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
)
NOT_INCLUDED = (
    "the original uploaded files (download them from Documents)",
    "security and audit records kept by the platform",
    "legal-acceptance history (Ask4Mo does not record it yet)",
    "other people's data, including content shared with you",
    "internal prompts, model reasoning and provider secrets",
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
