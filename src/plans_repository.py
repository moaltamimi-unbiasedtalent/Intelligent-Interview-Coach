"""Plan versions, subscriptions and their Admin operations (P10B-W10.4). No billing.

Every mutation stages its canonical audit row in the SAME transaction (SEC-W10-02 semantics); the audit holds
plan code, version numbers, subject type/id and entitlement KEY names only, never payment data (none exists).
Active and retired versions are immutable; a draft is the only editable state; subscriptions keep history
(the old row is ended, a new active row is added) and stay pinned to their plan version.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.admin_repository import AdminNotFound, _stage
from src.application.errors import ConflictError
from src.entitlements import (
    DEFAULT_PLAN_CODE,
    PLAN_CODES,
    REGISTRY,
    EntitlementError,
    ensure_default_subscription,  # noqa: F401  (re-exported)
    seed_default_plans,
    validate_value,
)
from src.persistence import (
    PLAN_STATUS_ACTIVE,
    PLAN_STATUS_DRAFT,
    PLAN_STATUS_RETIRED,
    PRODUCT_TIERS,
    SUBSCRIPTION_STATUS_ACTIVE,
    SUBSCRIPTION_STATUS_ENDED,
    PlanEntitlement,
    PlanVersion,
    ProductEntitlement,
    Subscription,
    User,
    Workspace,
    utcnow,
)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


class PlanRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    # -- reads ---------------------------------------------------------------------------------------

    @staticmethod
    def _subscriber_counts(s: Session, version_id: int) -> dict[str, int]:
        def n(col):
            return int(s.scalar(select(func.count()).select_from(Subscription).where(
                Subscription.plan_version_id == version_id, Subscription.status == SUBSCRIPTION_STATUS_ACTIVE,
                col.is_not(None))) or 0)
        return {"users": n(Subscription.user_id), "workspaces": n(Subscription.workspace_id)}

    def list_versions(self) -> list[dict]:
        with self._sf() as s:
            seed_default_plans(s)
            s.commit()
            rows = s.scalars(select(PlanVersion).order_by(PlanVersion.plan_code, PlanVersion.version.desc())).all()
            out = []
            for v in rows:
                enabled = int(s.scalar(select(func.count()).select_from(PlanEntitlement).where(
                    PlanEntitlement.plan_version_id == v.id, PlanEntitlement.enabled.is_(True))) or 0)
                out.append({"id": v.id, "plan_code": v.plan_code, "version": v.version, "display_name": v.display_name,
                            "status": v.status, "enabled_entitlements": enabled, "total_entitlements": len(REGISTRY),
                            "subscribers": self._subscriber_counts(s, v.id),
                            "created_at": _iso(v.created_at), "activated_at": _iso(v.activated_at),
                            "retired_at": _iso(v.retired_at)})
            return out

    def get_version(self, version_id: int) -> dict | None:
        with self._sf() as s:
            v = s.get(PlanVersion, version_id)
            if v is None:
                return None
            rows = {e.entitlement_key: e for e in s.scalars(
                select(PlanEntitlement).where(PlanEntitlement.plan_version_id == v.id)).all()}
            ents = []
            for key, d in REGISTRY.items():
                e = rows.get(key)
                ents.append({"code": key, "label": d.label, "description": d.description, "type": d.type.value,
                             "enabled": bool(e.enabled) if e else False, "limit": e.limit_value if e else None})
            return {"id": v.id, "plan_code": v.plan_code, "version": v.version, "display_name": v.display_name,
                    "status": v.status, "editable": v.status == PLAN_STATUS_DRAFT, "entitlements": ents,
                    "subscribers": self._subscriber_counts(s, v.id), "created_at": _iso(v.created_at),
                    "activated_at": _iso(v.activated_at), "retired_at": _iso(v.retired_at)}

    def assignable_plans(self) -> list[dict]:
        with self._sf() as s:
            seed_default_plans(s)
            s.commit()
            rows = s.scalars(select(PlanVersion).where(PlanVersion.status == PLAN_STATUS_ACTIVE)
                             .order_by(PlanVersion.plan_code)).all()
            return [{"plan_code": v.plan_code, "version": v.version, "display_name": v.display_name} for v in rows]

    def subject_plan(self, *, user_id: int | None = None, workspace_id: int | None = None) -> dict:
        """Current subscription plus history for a user or workspace (metadata only)."""
        cond = Subscription.workspace_id == workspace_id if workspace_id is not None else Subscription.user_id == user_id
        with self._sf() as s:
            rows = s.execute(select(Subscription, PlanVersion).join(PlanVersion, PlanVersion.id == Subscription.plan_version_id)
                             .where(cond).order_by(Subscription.id.desc())).all()
            hist = [{"plan_code": v.plan_code, "version": v.version, "display_name": v.display_name,
                     "status": sub.status, "source": sub.source, "started_at": _iso(sub.started_at),
                     "ended_at": _iso(sub.ended_at)} for sub, v in rows]
            current = next((h for h in hist if h["status"] == SUBSCRIPTION_STATUS_ACTIVE), None)
            return {"current": current, "history": hist[:20]}

    def stats(self) -> dict:
        """Counts only (Command Center). No revenue, price or payment figures exist."""
        with self._sf() as s:
            rows = s.execute(select(PlanVersion.plan_code, func.count(Subscription.user_id), func.count(Subscription.workspace_id))
                             .join(Subscription, Subscription.plan_version_id == PlanVersion.id)
                             .where(Subscription.status == SUBSCRIPTION_STATUS_ACTIVE)
                             .group_by(PlanVersion.plan_code)).all()
            no_sub = int(s.scalar(select(func.count()).select_from(User).where(
                ~select(Subscription.id).where(Subscription.user_id == User.id,
                                               Subscription.status == SUBSCRIPTION_STATUS_ACTIVE).exists())) or 0)
            return {"by_plan": {code: {"users": int(u), "workspaces": int(w)} for code, u, w in rows},
                    "accounts_without_subscription": no_sub}

    # -- plan version lifecycle (draft -> active -> retired) -----------------------------------------

    @staticmethod
    def _version(s: Session, version_id: int) -> PlanVersion:
        v = s.get(PlanVersion, version_id, with_for_update=True)
        if v is None:
            raise AdminNotFound("Plan version not found.")
        return v

    def create_draft(self, plan_code: str, *, audit: dict | None = None) -> dict:
        if plan_code not in PLAN_CODES:
            raise EntitlementError("Only the existing plan families can have new versions.")
        with self._sf() as s:
            seed_default_plans(s)
            if s.scalar(select(PlanVersion.id).where(PlanVersion.plan_code == plan_code,
                                                     PlanVersion.status == PLAN_STATUS_DRAFT)) is not None:
                raise ConflictError("A draft version of this plan already exists.")
            latest = s.scalar(select(PlanVersion).where(PlanVersion.plan_code == plan_code)
                              .order_by(PlanVersion.version.desc()).limit(1))
            if latest is None:
                raise AdminNotFound("Plan not found.")
            nv = PlanVersion(plan_code=plan_code, version=latest.version + 1, display_name=latest.display_name,
                             status=PLAN_STATUS_DRAFT)
            s.add(nv)
            s.flush()
            for e in s.scalars(select(PlanEntitlement).where(PlanEntitlement.plan_version_id == latest.id)).all():
                s.add(PlanEntitlement(plan_version_id=nv.id, entitlement_key=e.entitlement_key, enabled=e.enabled,
                                      limit_value=e.limit_value))
            _stage(s, audit, plan_code=plan_code, version=nv.version, copied_from=latest.version, version_id=nv.id)
            s.commit()
            return {"id": nv.id, "plan_code": plan_code, "version": nv.version}

    def update_draft(self, version_id: int, values: dict[str, dict], *, audit: dict | None = None,
                     registry=None) -> dict:
        if not values:
            raise EntitlementError("No entitlement values supplied.")
        with self._sf() as s:
            v = self._version(s, version_id)
            if v.status != PLAN_STATUS_DRAFT:
                raise ConflictError("Only a draft plan version can be edited; active and retired versions are immutable.")
            clean = {}
            for key, val in values.items():
                if not isinstance(val, dict):
                    raise EntitlementError(f"{key}: expected an object with 'enabled' and optional 'limit'.")
                clean[key] = validate_value(key, val.get("enabled"), val.get("limit"), registry)
            existing = {e.entitlement_key: e for e in s.scalars(
                select(PlanEntitlement).where(PlanEntitlement.plan_version_id == v.id)).all()}
            for key, (enabled, limit) in clean.items():
                row = existing.get(key)
                if row is None:
                    s.add(PlanEntitlement(plan_version_id=v.id, entitlement_key=key, enabled=enabled, limit_value=limit))
                else:
                    row.enabled, row.limit_value = enabled, limit
            _stage(s, audit, plan_code=v.plan_code, version=v.version, changed_keys=",".join(sorted(clean)))
            s.commit()
            return {"id": v.id, "changed": sorted(clean)}

    def activate(self, version_id: int, *, audit: dict | None = None) -> dict:
        with self._sf() as s:
            v = self._version(s, version_id)
            if v.status != PLAN_STATUS_DRAFT:
                raise ConflictError("Only a draft version can be activated.")
            now = utcnow()
            prev = s.scalar(select(PlanVersion).where(PlanVersion.plan_code == v.plan_code,
                                                      PlanVersion.status == PLAN_STATUS_ACTIVE).with_for_update())
            prev_version = None
            if prev is not None:   # the previous version stops being assignable; its subscribers stay pinned to it
                prev.status, prev.retired_at = PLAN_STATUS_RETIRED, now
                prev_version = prev.version
                s.flush()
            v.status, v.activated_at = PLAN_STATUS_ACTIVE, now
            _stage(s, audit, plan_code=v.plan_code, version=v.version, retired_version=prev_version)
            s.commit()
            return {"id": v.id, "plan_code": v.plan_code, "version": v.version, "retired_version": prev_version}

    def retire(self, version_id: int, *, audit: dict | None = None) -> dict:
        with self._sf() as s:
            v = self._version(s, version_id)
            if v.status != PLAN_STATUS_ACTIVE:
                raise ConflictError("Only an active version can be retired.")
            if v.plan_code == DEFAULT_PLAN_CODE:
                raise ConflictError("The default plan cannot be retired: new accounts need an active default version.")
            v.status, v.retired_at = PLAN_STATUS_RETIRED, utcnow()
            _stage(s, audit, plan_code=v.plan_code, version=v.version)
            s.commit()
            return {"id": v.id, "plan_code": v.plan_code, "version": v.version}

    # -- subscriptions ----------------------------------------------------------------------------------

    def assign(self, plan_code: str, *, user_id: int | None = None, workspace_id: int | None = None,
               source: str = "admin", audit: dict | None = None) -> dict:
        """Move ONE subject to the ACTIVE version of ``plan_code``: end the old subscription, add the new one,
        keep the legacy tier column in step (user subjects), and write the audit row, all in one transaction."""
        if (user_id is None) == (workspace_id is None):
            raise EntitlementError("Exactly one subject (user or workspace) is required.")
        with self._sf() as s:
            seed_default_plans(s)
            target = s.scalar(select(PlanVersion).where(PlanVersion.plan_code == plan_code,
                                                        PlanVersion.status == PLAN_STATUS_ACTIVE))
            if target is None:
                raise ConflictError("That plan has no active version to assign.")
            if user_id is not None:
                if s.get(User, user_id) is None:
                    raise AdminNotFound("Account not found.")
                cond, subject = Subscription.user_id == user_id, ("user", user_id)
            else:
                if s.get(Workspace, workspace_id) is None:
                    raise AdminNotFound("Workspace not found.")
                cond, subject = Subscription.workspace_id == workspace_id, ("workspace", workspace_id)
            current = s.execute(select(Subscription, PlanVersion).join(PlanVersion, PlanVersion.id == Subscription.plan_version_id)
                                .where(cond, Subscription.status == SUBSCRIPTION_STATUS_ACTIVE)).first()
            before = (current[1].plan_code, current[1].version) if current else (None, None)
            changed = not (current and current[0].plan_version_id == target.id)
            if changed:
                now = utcnow()
                if current:
                    current[0].status, current[0].ended_at = SUBSCRIPTION_STATUS_ENDED, now
                    s.flush()
                s.add(Subscription(user_id=user_id, workspace_id=workspace_id, plan_version_id=target.id,
                                   status=SUBSCRIPTION_STATUS_ACTIVE, source=source, started_at=now))
                if user_id is not None and plan_code in PRODUCT_TIERS:
                    ent = s.scalar(select(ProductEntitlement).where(ProductEntitlement.user_id == user_id))
                    if ent is None:
                        s.add(ProductEntitlement(user_id=user_id, tier=plan_code, source=source))
                    else:
                        ent.tier, ent.source = plan_code, source   # compatibility tier follows the subscription
            _stage(s, audit, subject_type=subject[0], before_plan=before[0], before_version=before[1],
                   after_plan=target.plan_code, after_version=target.version, assignment_source=source)
            s.commit()
            return {"subject_type": subject[0], "subject_id": subject[1], "plan_code": target.plan_code,
                    "version": target.version, "changed": changed}
