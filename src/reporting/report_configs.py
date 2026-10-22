"""Saved Admin report configurations (package 03E1): durable, owner-scoped, revision-protected, bounded.

* A configuration is a report DEFINITION only (``BuilderDefinition`` as JSON). It never holds a result, a figure or candidate data; viewing or exporting one always
  recomputes through the suppression pipeline and re-validates the stored definition against the CURRENT registry and the viewer's CURRENT permissions.
* Owner = the Admin who created it. It is private to the owner unless ``shared`` is true; sharing only lets other Admins who ALREADY hold the report's existing read
  permission VIEW and run it (no new permission, no edit, no delete). A configuration that is not visible to the caller is indistinguishable from a missing one.
* Bounds: ``MAX_CONFIGS_PER_OWNER`` per owner, the definition size cap of the builder, validated names, unique name per owner.
* Concurrency: ``expected_revision`` compare-and-swap on update and delete (stale -> ``ConfigConflict``). An update that repeats exactly the current content is an
  idempotent no-op (no revision bump, no audit); creating an identical configuration again returns the existing one.
* Every create, update and delete is audited IN THE SAME TRANSACTION (an audit failure rolls the change back). Audit payloads carry ids, the report type, the revision
  and the NAMES of changed fields; never a definition body, a name or any figure.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Final

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from src.persistence import ReportConfiguration as RC
from src.persistence import utcnow
from src.reporting.report_builder import BuilderDefinition, parse_definition

MAX_CONFIGS_PER_OWNER: Final = 25


class ConfigError(Exception):
    pass


class ConfigNotFound(ConfigError):
    pass


class ConfigForbidden(ConfigError):
    """Visible to the caller but owned by another Admin (HTTP 403): only the owner changes a configuration."""


class ConfigConflict(ConfigError):
    """Stale revision, duplicate name or the per-owner limit (HTTP 409)."""


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    from datetime import timezone

    return (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)).isoformat()


class ReportConfigService:
    def __init__(self, session_factory, *, clock: Callable[[], datetime] = utcnow) -> None:
        self._sf = session_factory
        self._clock = clock

    @staticmethod
    def _view(row: RC, caller_id: int) -> dict:
        return {"id": row.id, "name": row.name, "report_id": row.report_id, "definition": row.definition_json, "shared": bool(row.shared), "revision": row.revision,
                "editable": row.owner_user_id == caller_id, "created_at": _iso(row.created_at), "updated_at": _iso(row.updated_at)}

    def definition_of(self, row_view: dict) -> BuilderDefinition:
        return parse_definition(row_view["definition"])

    # ------------------------------------------------------------------ reads
    def list_visible(self, caller_id: int, readable_report_ids: frozenset[str]) -> list[dict]:
        """The caller's own configurations plus others' SHARED ones whose report type the caller may read (``readable_report_ids``)."""
        with self._sf() as s:
            rows = s.scalars(select(RC).where((RC.owner_user_id == caller_id) | (RC.shared.is_(True))).order_by(RC.name, RC.id)).all()
            return [self._view(r, caller_id) for r in rows if r.report_id in readable_report_ids]

    def get_visible(self, caller_id: int, config_id: int, readable_report_ids: frozenset[str]) -> dict:
        with self._sf() as s:
            row = s.get(RC, config_id)
            if row is None or row.report_id not in readable_report_ids or not (row.owner_user_id == caller_id or row.shared):
                raise ConfigNotFound("Saved report not found.")
            return self._view(row, caller_id)

    def count_owned(self, owner_id: int) -> int:
        with self._sf() as s:
            return int(s.scalar(select(func.count()).select_from(RC).where(RC.owner_user_id == owner_id)) or 0)

    # ------------------------------------------------------------------ mutations
    def create(self, owner_id: int, name: str, definition: BuilderDefinition, shared: bool, *, audit: dict | None = None) -> tuple[dict, bool]:
        """Returns ``(view, created)``. The same name with the identical definition and sharing is an idempotent replay (``created`` False)."""
        from src.admin_repository import _stage

        digest, now = definition.digest(), self._clock()
        with self._sf() as s:
            existing = s.scalar(select(RC).where(RC.owner_user_id == owner_id, RC.name == name))
            if existing is not None:
                if existing.definition_hash == digest and bool(existing.shared) == shared:
                    return self._view(existing, owner_id), False
                raise ConfigConflict("You already have a saved report with this name.")
            if int(s.scalar(select(func.count()).select_from(RC).where(RC.owner_user_id == owner_id)) or 0) >= MAX_CONFIGS_PER_OWNER:
                raise ConfigConflict(f"You can keep at most {MAX_CONFIGS_PER_OWNER} saved reports. Delete one first.")
            row = RC(owner_user_id=owner_id, name=name, report_id=definition.report_id, definition_json=definition.model_dump(mode="json"), definition_hash=digest,
                     shared=shared, revision=1, created_at=now, updated_at=now)
            s.add(row)
            try:
                s.flush()
            except IntegrityError:
                s.rollback()
                raise ConfigConflict("You already have a saved report with this name.")
            _stage(s, {**audit, "target_id": row.id} if audit else None, config_id=row.id, report_id=row.report_id, revision=1, shared=shared)
            s.commit()
            s.refresh(row)
            return self._view(row, owner_id), True

    def update(self, owner_id: int, config_id: int, *, expected_revision: int, name: str, definition: BuilderDefinition, shared: bool,
               readable_report_ids: frozenset[str], audit: dict | None = None) -> tuple[dict, bool]:
        """Full replace guarded by ``expected_revision``. Returns ``(view, changed)``."""
        from src.admin_repository import _stage

        digest, now = definition.digest(), self._clock()
        with self._sf() as s:
            row = s.get(RC, config_id)
            if row is None or row.report_id not in readable_report_ids or not (row.owner_user_id == owner_id or row.shared):
                raise ConfigNotFound("Saved report not found.")
            if row.owner_user_id != owner_id:
                raise ConfigForbidden("Only the owner can change a saved report.")
            same = row.name == name and row.definition_hash == digest and bool(row.shared) == shared
            if same:                                                       # idempotent replay (also covers a retried request after the revision moved)
                return self._view(row, owner_id), False
            if row.revision != expected_revision:
                raise ConfigConflict("This saved report changed since you loaded it. Reload and review it before changing it.")
            changed = [f for f, differs in (("name", row.name != name), ("definition", row.definition_hash != digest), ("shared", bool(row.shared) != shared)) if differs]
            res = s.execute(update(RC).where(RC.id == config_id, RC.revision == expected_revision).values(
                name=name, report_id=definition.report_id, definition_json=definition.model_dump(mode="json"), definition_hash=digest, shared=shared,
                revision=expected_revision + 1, updated_at=now))
            if res.rowcount != 1:
                raise ConfigConflict("This saved report changed since you loaded it. Reload and review it before changing it.")
            try:
                s.flush()
            except IntegrityError:
                s.rollback()
                raise ConfigConflict("You already have a saved report with this name.")
            _stage(s, {**audit, "target_id": config_id} if audit else None, config_id=config_id, report_id=definition.report_id, revision=expected_revision + 1,
                   changed_fields=changed)
            s.commit()
            s.expire_all()
            return self._view(s.get(RC, config_id), owner_id), True

    def delete(self, owner_id: int, config_id: int, *, expected_revision: int, readable_report_ids: frozenset[str], audit: dict | None = None) -> None:
        from src.admin_repository import _stage

        with self._sf() as s:
            row = s.get(RC, config_id)
            if row is None or row.report_id not in readable_report_ids or not (row.owner_user_id == owner_id or row.shared):
                raise ConfigNotFound("Saved report not found.")
            if row.owner_user_id != owner_id:
                raise ConfigForbidden("Only the owner can delete a saved report.")
            if row.revision != expected_revision:
                raise ConfigConflict("This saved report changed since you loaded it. Reload and review it before deleting it.")
            report_id, revision = row.report_id, row.revision
            res = s.execute(delete(RC).where(RC.id == config_id, RC.revision == expected_revision))
            if res.rowcount != 1:
                raise ConfigConflict("This saved report changed since you loaded it. Reload and review it before deleting it.")
            _stage(s, {**audit, "target_id": config_id} if audit else None, config_id=config_id, report_id=report_id, revision=revision)
            s.commit()
