"""Durable privacy-request workflow (SEC-W10-04, P10B-W10.10).

A privacy request is the durable record of something that needs human follow-up (correction, a governed access or deletion request, a
consent/preference question). It is NOT a replacement for the immediate self-service export and deletion in Data & Privacy. It stores
no exported data, no IP/device, and no candidate dataset: only the request type, a bounded note the candidate wrote, state,
assignment and a result category. Statuses are operational and carry no legal conclusion.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Callable

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import sessionmaker

from src.admin_repository import _page, _stage
from src.application import admin_permissions as perm
from src.persistence import ACCOUNT_STATUS_ACTIVE, PrivacyRequest as R, User, utcnow
from src.privacy import policy as P

MAX_OPEN_PER_USER = 5


class PrivacyNotFound(Exception):
    pass


class PrivacyValidationError(Exception):
    pass


class PrivacyConflict(Exception):
    pass


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


class PrivacyRequestService:
    def __init__(self, session_factory: sessionmaker, clock: Callable[[], datetime] = utcnow) -> None:
        self._sf = session_factory
        self._clock = clock

    # ---------------------------------------------------------------- creation
    @staticmethod
    def _validate(request_type: str, note: str | None) -> str | None:
        if request_type not in P.REQUEST_TYPES:
            raise PrivacyValidationError("Choose a request type.")
        note = (note or "").strip() or None
        if note is not None and (len(note) > P.MAX_NOTE or "\x00" in note):
            raise PrivacyValidationError("The note is too long.")
        return note

    def create(self, user_id: int, request_type: str, note: str | None, *, source: str = "candidate_portal",
               created_by_user_id: int | None = None, audit: dict | None = None) -> dict:
        note = self._validate(request_type, note)
        if source not in P.SOURCES:
            raise PrivacyValidationError("Unknown source.")
        now = self._clock()
        with self._sf() as s:
            user = s.get(User, user_id)
            if user is None:
                raise PrivacyNotFound("account")
            open_count = s.scalar(select(func.count()).select_from(R).where(R.user_id == user_id, R.status.in_(P.OPEN_STATUSES))) or 0
            if open_count >= MAX_OPEN_PER_USER:
                raise PrivacyConflict("There are already several open privacy requests for this account.")
            r = R(public_id=uuid.uuid4().hex, user_id=user_id, subject_user_id=user_id, request_type=request_type, status="submitted",
                  source=source, request_note=note, created_by_user_id=created_by_user_id, created_at=now, updated_at=now)
            s.add(r)
            s.flush()
            _stage(s, {**audit, "target_id": r.public_id} if audit else None, request_public_id=r.public_id, request_type=request_type,
                   subject_user_id=user_id, new_state="submitted")
            s.commit()
            return self._owner_view(r)

    # ---------------------------------------------------------------- candidate views (no operator identity, no internals)
    @staticmethod
    def _owner_view(r: R) -> dict:
        return {"public_id": r.public_id, "request_type": r.request_type, "type_label": P.REQUEST_TYPE_LABEL[r.request_type],
                "status": r.status, "result_category": r.result_category, "created_at": _iso(r.created_at), "updated_at": _iso(r.updated_at)}

    def list_for_owner(self, user_id: int, *, page: int = 1, page_size: int = 20) -> dict:
        page, page_size = _page(page, page_size)
        with self._sf() as s:
            total = s.scalar(select(func.count()).select_from(R).where(R.user_id == user_id)) or 0
            rows = s.scalars(select(R).where(R.user_id == user_id).order_by(R.created_at.desc(), R.id.desc())
                             .limit(page_size).offset((page - 1) * page_size)).all()
            return {"items": [self._owner_view(r) for r in rows], "total": total, "page": page, "page_size": page_size}

    def export_for_owner(self, user_id: int) -> list[dict]:
        with self._sf() as s:
            return [self._owner_view(r) for r in s.scalars(select(R).where(R.user_id == user_id).order_by(R.id)).all()]

    # ---------------------------------------------------------------- admin views
    @staticmethod
    def _admin_row(r: R, email: str | None, assignee_email: str | None) -> dict:
        return {**PrivacyRequestService._owner_view(r), "source": r.source, "user_id": r.user_id, "candidate_email": email,
                "assigned_user_id": r.assigned_user_id, "assignee_email": assignee_email, "acknowledged_at": _iso(r.acknowledged_at),
                "completed_at": _iso(r.completed_at), "closed_at": _iso(r.closed_at), "related_job_id": r.related_job_public_id}

    def list(self, *, status: str | None = None, request_type: str | None = None, assignee: str | None = None, q: str | None = None,
             page: int = 1, page_size: int = 25, actor_user_id: int | None = None) -> dict:
        page, page_size = _page(page, page_size)
        conds = []
        if status:
            if status == "open":
                conds.append(R.status.in_(P.OPEN_STATUSES))
            elif status in P.STATUSES:
                conds.append(R.status == status)
            else:
                raise PrivacyValidationError("Unknown status.")
        if request_type:
            if request_type not in P.REQUEST_TYPES:
                raise PrivacyValidationError("Unknown request type.")
            conds.append(R.request_type == request_type)
        if assignee == "unassigned":
            conds.append(R.assigned_user_id.is_(None))
        elif assignee == "me" and actor_user_id is not None:
            conds.append(R.assigned_user_id == actor_user_id)
        elif assignee and assignee.isdigit():
            conds.append(R.assigned_user_id == int(assignee))
        if q:
            term = q.strip()
            like = f"%{term.lower()}%"
            sub = [R.public_id == term.lower(), R.user_id.in_(select(User.id).where(func.lower(User.email).like(like)))]
            if term.isdigit():
                sub.append(R.user_id == int(term))
            conds.append(or_(*sub))                  # request id, account id or email only: never request text
        with self._sf() as s:
            total = s.scalar(select(func.count()).select_from(R).where(*conds)) or 0
            rows = s.scalars(select(R).where(*conds).order_by(R.created_at.desc(), R.id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
            return {"items": [self._admin_row(r, *self._emails(s, r)) for r in rows], "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def _emails(s, r: R) -> tuple[str | None, str | None]:
        cand = s.get(User, r.user_id).email if r.user_id and s.get(User, r.user_id) else None
        asg = s.get(User, r.assigned_user_id).email if r.assigned_user_id and s.get(User, r.assigned_user_id) else None
        return cand, asg

    def _find(self, s, public_id: str) -> R:
        r = s.scalar(select(R).where(R.public_id == public_id))
        if r is None:
            raise PrivacyNotFound(public_id)
        return r

    def detail(self, public_id: str) -> dict:
        with self._sf() as s:
            r = self._find(s, public_id)
            email, asg = self._emails(s, r)
            cand = s.get(User, r.user_id) if r.user_id else None
            allowed = sorted(P.TRANSITIONS[r.status])
            return {**self._admin_row(r, email, asg), "request_note": r.request_note,
                    "candidate": ({"user_id": cand.id, "email": cand.email, "status": cand.status, "platform_role": cand.platform_role,
                                   "created_at": _iso(cand.created_at)} if cand else None),
                    "allowed_statuses": allowed, "result_categories": list(P.RESULT_CATEGORIES),
                    "can_execute_deletion": bool(r.request_type == "deletion" and r.status in ("acknowledged", "in_progress") and cand is not None
                                                 and cand.platform_role == "user" and not r.related_job_public_id)}

    # ---------------------------------------------------------------- admin mutations
    def assign(self, public_id: str, assignee_user_id: int | None, *, audit: dict | None = None) -> dict:
        with self._sf() as s:
            r = self._find(s, public_id)
            if r.status == "closed":
                raise PrivacyConflict("A closed request cannot be changed.")
            if assignee_user_id is not None:
                u = s.get(User, assignee_user_id)
                if u is None or u.status != ACCOUNT_STATUS_ACTIVE or perm.permissions_for_role(u.platform_role).isdisjoint({"platform.privacy.execute"}):
                    raise PrivacyConflict("That account cannot be assigned privacy requests.")
            before = r.assigned_user_id
            r.assigned_user_id, r.updated_at = assignee_user_id, self._clock()
            _stage(s, {**audit, "target_id": public_id} if audit else None, request_public_id=public_id,
                   before_assignee=before, after_assignee=assignee_user_id)
            s.commit()
        return self.detail(public_id)

    def set_status(self, public_id: str, status: str, *, result_category: str | None = None, audit: dict | None = None) -> dict:
        if status not in P.STATUSES:
            raise PrivacyValidationError("Unknown status.")
        if result_category is not None and result_category not in P.RESULT_CATEGORIES:
            raise PrivacyValidationError("Unknown result category.")
        now = self._clock()
        with self._sf() as s:
            r = self._find(s, public_id)
            if status not in P.TRANSITIONS[r.status]:
                raise PrivacyConflict(f"A {r.status.replace('_', ' ')} request cannot move to {status.replace('_', ' ')}.")
            if status == "completed" and result_category is None:
                raise PrivacyValidationError("Choose a result category to complete a request.")
            values: dict = {"status": status, "updated_at": now}
            if status == "acknowledged":
                values["acknowledged_at"] = now
            if status == "completed":
                values.update(completed_at=now, result_category=result_category)
            if status in ("closed",):
                values["closed_at"] = now
            old = r.status
            res = s.execute(update(R).where(R.id == r.id, R.status == old).values(**values))
            if res.rowcount != 1:
                s.rollback()
                raise PrivacyConflict("The request changed while this action ran; reload and retry.")
            _stage(s, {**audit, "target_id": public_id} if audit else None, request_public_id=public_id, old_state=old, new_state=status,
                   result_category=result_category)
            s.commit()
        return self.detail(public_id)

    def link_job(self, public_id: str, job_public_id: str) -> None:
        with self._sf() as s:
            s.execute(update(R).where(R.public_id == public_id).values(related_job_public_id=job_public_id, updated_at=self._clock()))
            s.commit()

    def complete_system(self, public_id: str, result_category: str, *, clear_subject: bool = True, audit: dict | None = None) -> bool:
        """Finalise from a job. Idempotent (already completed => False). Clears the subject id and the free-text note."""
        now = self._clock()
        with self._sf() as s:
            r = self._find(s, public_id)
            if r.status == "completed" or r.status == "closed":
                return False
            res = s.execute(update(R).where(R.id == r.id, R.status == r.status).values(
                status="completed", completed_at=now, result_category=result_category, updated_at=now,
                **({"subject_user_id": None, "request_note": None, "user_id": None} if clear_subject else {})))
            _stage(s, {**audit, "target_id": public_id} if audit else None, request_public_id=public_id, old_state=r.status,
                   new_state="completed", result_category=result_category)
            s.commit()
            return bool(res.rowcount)

    def stats(self) -> dict:
        with self._sf() as s:
            counts = dict(s.execute(select(R.status, func.count()).group_by(R.status)).all())
            unassigned = s.scalar(select(func.count()).select_from(R).where(R.status.in_(P.OPEN_STATUSES), R.assigned_user_id.is_(None))) or 0
            oldest = s.scalar(select(func.min(R.created_at)).where(R.status.in_(P.OPEN_STATUSES)))
        return {"open": sum(counts.get(k, 0) for k in P.OPEN_STATUSES), "submitted": counts.get("submitted", 0),
                "in_progress": counts.get("in_progress", 0), "waiting_for_user": counts.get("waiting_for_user", 0),
                "unassigned_open": unassigned, "completed": counts.get("completed", 0), "total": sum(counts.values()),
                "oldest_open_at": _iso(oldest)}
