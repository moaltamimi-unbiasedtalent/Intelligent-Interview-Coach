"""Derived expected-revision tokens for plan administration (03B). No schema: each token is a short hash of state that is
already stored, so two administrators cannot silently overwrite each other and nothing needs a new column.

* version revision: the version's own content (status, name, every entitlement value) plus its family's lifecycle state
  (the status of every version of the plan code), so an activation or retirement elsewhere in the family invalidates it;
* family revision: only the family's lifecycle state (used to create or restore a draft);
* subject revision: the id of the subject's ACTIVE subscription (or none), so any assignment change invalidates it.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.application.errors import ConflictError
from src.persistence import SUBSCRIPTION_STATUS_ACTIVE, PlanEntitlement, PlanVersion, Subscription

STALE = "The plan changed since it was loaded. Reload and review the current state before trying again."


def _h(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def family_revision(s: Session, plan_code: str) -> str:
    rows = s.execute(select(PlanVersion.id, PlanVersion.version, PlanVersion.status)
                     .where(PlanVersion.plan_code == plan_code).order_by(PlanVersion.version)).all()
    return _h("family", plan_code, ";".join(f"{i}:{v}:{st}" for i, v, st in rows))


def version_revision(s: Session, v: PlanVersion) -> str:
    ents = s.scalars(select(PlanEntitlement).where(PlanEntitlement.plan_version_id == v.id)
                     .order_by(PlanEntitlement.entitlement_key)).all()
    content = ";".join(f"{e.entitlement_key}={int(bool(e.enabled))}/{e.limit_value}" for e in ents)
    return _h("version", v.id, v.status, v.display_name, content, family_revision(s, v.plan_code))


def subject_revision(s: Session, *, user_id: int | None = None, workspace_id: int | None = None) -> str:
    cond = Subscription.workspace_id == workspace_id if workspace_id is not None else Subscription.user_id == user_id
    sid = s.scalar(select(Subscription.id).where(cond, Subscription.status == SUBSCRIPTION_STATUS_ACTIVE))
    return _h("subject", "none" if sid is None else sid)


def require(expected: str | None, actual: str, *, required: bool = False) -> None:
    """Raise 409 when a supplied token no longer matches; ``required`` also refuses a missing token."""
    if expected is None:
        if required:
            raise ConflictError(STALE)
        return
    if expected != actual:
        raise ConflictError(STALE)
