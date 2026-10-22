"""Plan administration read models and bulk assignment (03B, REQ-OWN-02). Counts, plan codes, version numbers, subject ids
and entitlement KEY names only: no candidate content, no email, no commercial terms (those live on the Billing page).

Four layers stay separate and are labelled as such in every explanation: authorization (who may act), capability (what the
deployment supports), entitlement (what a plan grants, the only layer this module reads) and billing state (never an
access source). Every mutation here goes through ``PlanRepository`` so there is still ONE assignment code path.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src import plan_revision as R
from src.admin_repository import AdminNotFound
from src.application.errors import ConflictError
from src.entitlements import (
    REGISTRY,
    EntitlementError,
    EntitlementService,
    bounds_of,
    seed_default_plans,
)
from src.persistence import (
    PLAN_STATUS_ACTIVE,
    SUBSCRIPTION_STATUS_ACTIVE,
    PlanEntitlement,
    PlanVersion,
    Subscription,
    User,
    Workspace,
)
from src.plans_repository import PlanRepository

MAX_BULK = 100
SUBJECT_KINDS = ("user", "workspace")

LAYERS = (
    {"layer": "authorization", "evaluated_here": False,
     "note": "Who may perform an operation is decided per request by ownership and Admin permissions. A plan never grants permission."},
    {"layer": "capability", "evaluated_here": False,
     "note": "What the deployment technically supports (flags, providers) is decided separately. An entitlement never overrides it."},
    {"layer": "entitlement", "evaluated_here": True,
     "note": "What the subject's plan version grants. This is the only layer explained here."},
    {"layer": "billing_state", "evaluated_here": False,
     "note": "Billing is mock and never an access source. A payment or commercial-terms change never changes entitlements."},
)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _h(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


class PlanAdminService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory
        self._ent = EntitlementService(session_factory)

    # -- matrix and comparison -------------------------------------------------------------------------------

    @staticmethod
    def _values(s: Session, version_id: int) -> dict[str, dict]:
        rows = {e.entitlement_key: e for e in s.scalars(
            select(PlanEntitlement).where(PlanEntitlement.plan_version_id == version_id)).all()}
        return {k: {"enabled": bool(rows[k].enabled) if k in rows else False,
                    "limit": rows[k].limit_value if k in rows else None} for k in REGISTRY}

    def matrix(self) -> dict:
        """Entitlement matrix: every key against every version of every real plan."""
        with self._sf() as s:
            seed_default_plans(s)
            s.commit()
            versions = s.scalars(select(PlanVersion).order_by(PlanVersion.plan_code, PlanVersion.version.desc())).all()
            return {
                "entitlements": [{"code": k, "label": d.label, "description": d.description, "type": d.type.value,
                                  "bounds": bounds_of(d)} for k, d in REGISTRY.items()],
                "versions": [{"id": v.id, "plan_code": v.plan_code, "version": v.version, "display_name": v.display_name,
                              "status": v.status, "revision": R.version_revision(s, v),
                              "values": self._values(s, v.id)} for v in versions]}

    def compare(self, left_id: int, right_id: int) -> dict:
        with self._sf() as s:
            lv, rv = s.get(PlanVersion, left_id), s.get(PlanVersion, right_id)
            if lv is None or rv is None:
                raise AdminNotFound("Plan version not found.")
            lvals, rvals = self._values(s, lv.id), self._values(s, rv.id)

            def head(v: PlanVersion) -> dict:
                return {"id": v.id, "plan_code": v.plan_code, "version": v.version, "display_name": v.display_name,
                        "status": v.status, "subscribers": PlanRepository._subscriber_counts(s, v.id)}
            rows = [{"code": k, "label": d.label, "left": lvals[k], "right": rvals[k], "differs": lvals[k] != rvals[k]}
                    for k, d in REGISTRY.items()]
            return {"left": head(lv), "right": head(rv), "rows": rows, "changed": sum(1 for r in rows if r["differs"]),
                    "note": "Subscribers stay pinned to their version; comparing or activating a version never moves anyone."}

    # -- subjects, history -----------------------------------------------------------------------------------

    @staticmethod
    def _subject_cond(kind: str, subject_id: int):
        return Subscription.workspace_id == subject_id if kind == "workspace" else Subscription.user_id == subject_id

    @staticmethod
    def _require_subject(s: Session, kind: str, subject_id: int) -> None:
        if kind not in SUBJECT_KINDS:
            raise EntitlementError("Unknown subject type.")
        model, label = (Workspace, "Workspace") if kind == "workspace" else (User, "Account")
        if s.get(model, subject_id) is None:
            raise AdminNotFound(f"{label} not found.")

    def subject_state(self, kind: str, subject_id: int) -> dict:
        """Current plan, assignment history (newest first, bounded) and the revision a change must quote."""
        with self._sf() as s:
            self._require_subject(s, kind, subject_id)
            rows = s.execute(select(Subscription, PlanVersion).join(PlanVersion, PlanVersion.id == Subscription.plan_version_id)
                             .where(self._subject_cond(kind, subject_id)).order_by(Subscription.id.desc()).limit(50)).all()
            hist = [{"plan_code": v.plan_code, "version": v.version, "display_name": v.display_name, "status": sub.status,
                     "source": sub.source, "started_at": _iso(sub.started_at), "ended_at": _iso(sub.ended_at)}
                    for sub, v in rows]
            kw = {"workspace_id": subject_id} if kind == "workspace" else {"user_id": subject_id}
            return {"subject_type": kind, "subject_id": subject_id,
                    "current": next((h for h in hist if h["status"] == SUBSCRIPTION_STATUS_ACTIVE), None),
                    "history": hist, "revision": R.subject_revision(s, **kw)}

    def version_assignments(self, version_id: int, *, page: int = 1, page_size: int = 25) -> dict:
        page, page_size = max(1, int(page)), max(1, min(int(page_size), 100))
        with self._sf() as s:
            v = s.get(PlanVersion, version_id)
            if v is None:
                raise AdminNotFound("Plan version not found.")
            total = int(s.scalar(select(func.count()).select_from(Subscription).where(Subscription.plan_version_id == v.id)) or 0)
            rows = s.scalars(select(Subscription).where(Subscription.plan_version_id == v.id)
                             .order_by(Subscription.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
            items = [{"subject_type": "workspace" if r.workspace_id is not None else "user",
                      "subject_id": r.workspace_id if r.workspace_id is not None else r.user_id,
                      "status": r.status, "source": r.source, "started_at": _iso(r.started_at), "ended_at": _iso(r.ended_at)}
                     for r in rows]
            return {"plan_code": v.plan_code, "version": v.version, "total": total, "page": page, "page_size": page_size,
                    "items": items}

    # -- effective-entitlement explanation -------------------------------------------------------------------

    def explain(self, *, user_id: int | None = None, workspace_id: int | None = None) -> dict:
        if (user_id is None) == (workspace_id is None):
            raise EntitlementError("Exactly one subject (user or workspace) is required.")
        kind, sid = ("workspace", workspace_id) if workspace_id is not None else ("user", user_id)
        with self._sf() as s:
            self._require_subject(s, kind, sid)
        # The resolver is the single authority; the explanation only labels ITS answer.
        res = self._ent.resolve_all(user_id or 0, workspace_id=workspace_id)
        first = next(iter(res.values()))
        rows: dict[str, PlanEntitlement] = {}
        status = None
        if first.plan_version is not None:
            with self._sf() as s:
                pv = s.scalar(select(PlanVersion).where(PlanVersion.plan_code == first.plan_code,
                                                        PlanVersion.version == first.plan_version))
                if pv is not None:
                    status = pv.status
                    rows = {e.entitlement_key: e for e in s.scalars(
                        select(PlanEntitlement).where(PlanEntitlement.plan_version_id == pv.id)).all()}
        items = []
        for key, d in REGISTRY.items():
            r = res[key]
            if first.source == "subscription":
                reason = ("granted_by_plan_version" if r.enabled else
                          "disabled_by_plan_version" if key in rows else "not_listed_in_plan_version_denied_by_default")
            elif first.plan_version is None:
                reason = "code_default_basic_grants" if r.enabled else "code_default_basic_denies"
            else:
                reason = ("no_active_subscription_basic_fallback_grants" if r.enabled
                          else "no_active_subscription_basic_fallback_denies")
            items.append({"code": key, "label": d.label, "allowed": r.enabled, "limit": r.limit,
                          "unlimited": r.enabled and r.limit is None, "reason": reason})
        return {"subject_type": kind, "subject_id": sid, "plan_code": first.plan_code, "plan_version": first.plan_version,
                "plan_version_status": status, "source": first.source, "items": items, "layers": list(LAYERS),
                "note": "Explains access from plan data only. It never reads or shows candidate content."}

    # -- assignment preview and bulk assignment --------------------------------------------------------------

    @staticmethod
    def _clean_ids(kind: str, ids: list[int]) -> list[int]:
        if kind not in SUBJECT_KINDS:
            raise EntitlementError("Unknown subject type.")
        out = sorted({int(i) for i in ids})
        if not out:
            raise EntitlementError("Choose at least one subject.")
        if len(out) > MAX_BULK or any(i < 1 for i in out):
            raise EntitlementError(f"Choose between 1 and {MAX_BULK} valid subjects.")
        return out

    def _analyse(self, s: Session, plan_code: str, kind: str, ids: list[int]) -> tuple[dict, str]:
        target = s.scalar(select(PlanVersion).where(PlanVersion.plan_code == plan_code, PlanVersion.status == PLAN_STATUS_ACTIVE))
        if target is None:
            raise ConflictError("That plan has no active version to assign.")
        model = Workspace if kind == "workspace" else User
        found = sorted(i for i in ids if s.get(model, i) is not None)
        tvals = self._values(s, target.id)
        by_current = {"basic": 0, "premium": 0, "none": 0}
        effect = {k: {"gain": 0, "lose": 0, "limit_changed": 0} for k in REGISTRY}
        unchanged = 0
        revs = []
        for i in found:
            kw = {"workspace_id": i} if kind == "workspace" else {"user_id": i}
            sub = s.execute(select(Subscription.plan_version_id, PlanVersion.plan_code)
                            .join(PlanVersion, PlanVersion.id == Subscription.plan_version_id)
                            .where(self._subject_cond(kind, i), Subscription.status == SUBSCRIPTION_STATUS_ACTIVE)).first()
            revs.append(f"{i}:{R.subject_revision(s, **kw)}")
            by_current[sub[1] if sub and sub[1] in by_current else "none"] += 1
            if sub and sub[0] == target.id:
                unchanged += 1
                continue
            cur = self._ent.resolve_all(0 if kind == "workspace" else i, workspace_id=i if kind == "workspace" else None)
            for k in REGISTRY:
                c, t = cur[k], tvals[k]
                if not c.enabled and t["enabled"]:
                    effect[k]["gain"] += 1
                elif c.enabled and not t["enabled"]:
                    effect[k]["lose"] += 1
                elif c.enabled and t["enabled"] and c.limit != t["limit"]:
                    effect[k]["limit_changed"] += 1
        data = {"plan_code": target.plan_code, "target_version": target.version, "subject_type": kind,
                "requested": len(ids), "found": len(found), "missing": len(ids) - len(found), "unchanged": unchanged,
                "would_change": len(found) - unchanged, "by_current_plan": by_current,
                "entitlement_effect": [{"code": k, "label": REGISTRY[k].label, **v} for k, v in effect.items()]}
        token = _h("assign", target.id, R.version_revision(s, target), kind, ",".join(revs), data["missing"])
        return data, token

    def assignment_effect(self, plan_code: str, kind: str, ids: list[int]) -> dict:
        """The effect of an assignment as COUNTS ONLY (never which accounts). The returned ``preview_revision`` is what a
        bulk assignment must quote; any change to the target version or a subject's subscription invalidates it."""
        clean = self._clean_ids(kind, ids)
        with self._sf() as s:
            seed_default_plans(s)
            data, token = self._analyse(s, plan_code, kind, clean)
        return {**data, "preview_revision": token}

    def bulk_assign(self, plan_code: str, kind: str, ids: list[int], *, preview_revision: str,
                    audit_for: Callable[[str, int, int], dict | None], source: str = "admin") -> dict:
        """All-or-nothing: every subject (and its audit row) commits in ONE transaction, or none does."""
        clean = self._clean_ids(kind, ids)
        with self._sf() as s:
            seed_default_plans(s)
            data, token = self._analyse(s, plan_code, kind, clean)
            R.require(preview_revision, token, required=True)
            if data["missing"]:
                raise EntitlementError("Some of the chosen subjects do not exist. Review the preview and try again.")
            changed = 0
            for i in clean:
                kw = {"workspace_id": i} if kind == "workspace" else {"user_id": i}
                out = PlanRepository.assign_in_session(s, plan_code, source=source, audit=audit_for(kind, i, len(clean)), **kw)
                changed += 1 if out["changed"] else 0
            s.commit()
            return {"plan_code": data["plan_code"], "version": data["target_version"], "subject_type": kind,
                    "requested": len(clean), "changed": changed, "unchanged": len(clean) - changed}
