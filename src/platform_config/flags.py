"""Code-defined feature flags with DURABLE overrides (P10B-W10.11).

THE INVARIANTS:
* A flag may only RESTRICT availability. ``available = existing_authorized_capability AND flag``. A flag never grants authorization, an entitlement,
  Premium, a billing change or an AI/model change, and enabling one only removes the flag's own restriction.
* The flag keys are defined here, in code. Admin cannot create a key; an unknown key is rejected.
* Precedence (healthy store): a durable override for THIS environment > the existing environment/code baseline. No override means INHERIT: behaviour is
  exactly what it was before W10.11 (including the environment variable and its default).
* FAILURE (unreadable authoritative store, durable service installed): FAIL CLOSED. The effective value is False and Admin reads report unavailable.
* State is tri-valued: inherit (no row), enabled override (row enabled=true), disabled override (row enabled=false).
* Overrides are optimistic-concurrency protected (``revision``) and audited in the same transaction as the change.
* Only flags with a real, safe, backend-enforced consumer qualify. Deployment capabilities that need credentials, security settings, integrations,
  billing, AI, entitlements and legal/privacy policy are NOT flags (see ``NOT_MUTABLE``).
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from src.persistence import FeatureFlagOverride as FFO, utcnow

__all__ = ["FlagDef", "FLAGS", "NOT_MUTABLE", "FeatureFlagService", "FeatureFlagStateUnavailable", "FlagConflict", "FlagValidationError", "FlagUnsupportedEnvironment",
           "install", "uninstall", "effective", "MAX_REASON"]

MAX_REASON = 200


@dataclass(frozen=True)
class FlagDef:
    key: str
    display_name: str
    description: str
    env_var: str                 # the existing deployment variable that is the baseline
    env_default: bool            # its default when unset
    category: str
    candidate_visible: bool
    consumers: tuple[str, ...]   # the real backend call sites that enforce it
    notes: str = ""

    def baseline(self) -> bool:
        raw = os.environ.get(self.env_var)
        if raw is None or not raw.strip():
            return self.env_default
        return raw.strip().lower() in ("1", "true", "yes", "on")


# The ONLY mutable flags. Both are RESTRICTION switches over the existing external-research feature (default ON): disabling one removes the
# capability for candidates; enabling one cannot create a capability (research still needs its own auth, entitlement and cost gates).
FLAGS: dict[str, FlagDef] = {f.key: f for f in (
    FlagDef("external_research", "External market research", "Allows the external labour-market and company research providers to run at all.",
            "EXTERNAL_RESEARCH_ENABLED", True, "research", True,
            ("src/copilot/research/service.py:default_research_service", "src/api/routes/health.py:_company_research_available"),
            "Disabling it turns external research off for candidates. Enabling it cannot bypass authentication, the plan entitlement, rate limits or the operator pause."),
    FlagDef("company_web_research", "Company website research", "Allows researching a company's own public website (inside the existing SSRF, robots and size guards).",
            "COMPANY_WEB_RESEARCH_ENABLED", True, "research", True, ("src/copilot/research/service.py:default_research_service",),
            "A sub-feature of external research: it is effective only while external research is effective."),
)}

# Classification of every other existing runtime flag found in the audit. They are NOT mutable here.
NOT_MUTABLE: dict[str, str] = {
    "AGENT_COACH_ENABLED": "read-only environment capability: a UI cutover for a surface whose API is not flag-gated; an Admin toggle would be frontend-only",
    "INTERVIEW_LIVE_ENABLED": "read-only environment capability: experimental Live mode that needs provider credentials",
    "REALTIME_VOICE_ENABLED": "integration/credential configuration (W10.6); runtime availability is controlled by the durable pause",
    "FEATURE_GOOGLE_LOGIN": "security configuration (authentication provider)",
    "AGENT_EXTERNAL_OBSERVABILITY_ENABLED": "integration configuration (W10.6)",
    "BILLING_PROVIDER": "billing configuration (W10.5)",
    "OPENROUTER_MODEL_*": "AI configuration (W10.7)",
    "AUTH_REQUIRED": "security configuration",
    "TRUST_PROXY": "security configuration",
}


class FeatureFlagStateUnavailable(Exception):
    """The authoritative feature-flag store could not be read. A restriction flag must then be treated as OFF: the durable override that may exist
    (for example an explicit disable) is unknown, so the environment baseline is NOT a safe guess."""


class FlagConflict(Exception):
    pass


class FlagValidationError(Exception):
    pass


class FlagUnsupportedEnvironment(Exception):
    pass


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


class FeatureFlagService:
    def __init__(self, session_factory, *, environment: str | None = "from_process", clock: Callable[[], datetime] = utcnow) -> None:
        if environment == "from_process":
            from src.ai_admin.resolver import environment_name
            environment = environment_name()
        self.environment = environment
        self._sf = session_factory
        self._clock = clock

    @staticmethod
    def definition(key: str) -> FlagDef:
        if key not in FLAGS:
            raise FlagValidationError("Unknown feature flag.")
        return FLAGS[key]

    def _row(self, s, key: str) -> FFO | None:
        return s.scalar(select(FFO).where(FFO.environment == (self.environment or "unsupported"), FFO.flag_key == key))

    def _state(self, d: FlagDef, row: FFO | None) -> dict:
        base = d.baseline()
        override = None if row is None or row.enabled is None else bool(row.enabled)
        eff = base if override is None else override
        # A restriction flag never enables a sub-feature whose parent is off.
        return {"flag_id": d.key, "display_name": d.display_name, "description": d.description, "category": d.category, "candidate_visible": d.candidate_visible,
                "baseline": base, "baseline_source": f"environment variable {d.env_var} (default {'on' if d.env_default else 'off'})",
                "override": override, "state": "inherited" if override is None else ("enabled_override" if override else "disabled_override"),
                "effective": eff, "revision": row.revision if row else 0, "updated_at": _iso(row.updated_at) if row else None,
                "updated_by_user_id": row.updated_by_user_id if row else None, "reason": row.reason if row else "", "notes": d.notes,
                "consumers": list(d.consumers)}

    def states(self) -> list[dict]:
        try:
            with self._sf() as s:
                rows = {r.flag_key: r for r in s.scalars(select(FFO).where(FFO.environment == (self.environment or "unsupported"))).all()}
        except Exception as exc:  # noqa: BLE001 - fixed category only; never surface the cause
            raise FeatureFlagStateUnavailable("feature flag state unavailable") from exc
        return [self._state(d, rows.get(d.key)) for d in FLAGS.values()]

    def effective(self, key: str) -> bool:
        d = self.definition(key)
        try:
            with self._sf() as s:
                row = self._row(s, key)
        except Exception as exc:  # noqa: BLE001
            raise FeatureFlagStateUnavailable("feature flag state unavailable") from exc
        return bool(row.enabled) if row is not None and row.enabled is not None else d.baseline()

    def stats(self) -> dict:
        st = self.states()
        return {"environment": self.environment or "unsupported", "flags": len(st), "overrides": sum(1 for x in st if x["override"] is not None),
                "disabled_overrides": sum(1 for x in st if x["override"] is False)}

    def set_override(self, key: str, enabled: bool | None, *, expected_revision: int, reason: Any, actor_user_id: int, audit_for: Callable[[str], dict] | None = None) -> dict:
        """enabled True/False = explicit override; None = reset to inherit (delete the row). ``audit_for(new_state)`` builds the audit spec."""
        from src.admin_repository import _stage

        d = self.definition(key)
        if self.environment is None:
            raise FlagUnsupportedEnvironment("This deployment's environment is not recognised, so flag overrides cannot be changed here.")
        text = reason.strip() if isinstance(reason, str) else ""
        if not text or len(text) > MAX_REASON or "\x00" in text:
            raise FlagValidationError(f"A reason is required (up to {MAX_REASON} characters).")
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise FlagValidationError("A valid expected revision is required.")
        if enabled is not None and not isinstance(enabled, bool):
            raise FlagValidationError("The override must be true, false or null.")
        now = self._clock()
        with self._sf() as s:
            row = self._row(s, key)
            current = row.revision if row else 0
            if expected_revision != current:
                raise FlagConflict("This flag changed since you loaded it. Reload and review the current state before changing it.")
            old_override = None if row is None or row.enabled is None else bool(row.enabled)
            old_effective = old_override if old_override is not None else d.baseline()
            if enabled is None and old_override is None:
                raise FlagConflict("This flag already inherits its baseline.")
            if row is None:
                s.add(FFO(environment=self.environment, flag_key=key, enabled=enabled, revision=1, updated_by_user_id=actor_user_id, updated_at=now, reason=text))
                new_revision = 1
            else:                                                          # also the reset: enabled=None keeps the row so the revision stays monotonic
                res = s.execute(update(FFO).where(FFO.id == row.id, FFO.revision == current).values(enabled=enabled, revision=current + 1, updated_by_user_id=actor_user_id,
                                                                                                 updated_at=now, reason=text))
                if res.rowcount != 1:
                    raise FlagConflict("This flag changed since you loaded it. Reload and review the current state before changing it.")
                new_revision = current + 1
            new_state = "inherited" if enabled is None else ("enabled_override" if enabled else "disabled_override")
            new_effective = d.baseline() if enabled is None else enabled
            try:
                s.flush()
            except IntegrityError:
                s.rollback()
                raise FlagConflict("This flag changed since you loaded it. Reload and review the current state before changing it.")
            spec = audit_for(new_state) if audit_for else None
            _stage(s, {**spec, "target_id": key} if spec else None, environment=self.environment, flag_key=key, old_override=_name(old_override), new_override=_name(enabled),
                   old_effective=old_effective, new_effective=new_effective, revision=new_revision)
            s.commit()
        return next(x for x in self.states() if x["flag_id"] == key)


def _name(v: bool | None) -> str:
    return "inherit" if v is None else ("enabled" if v else "disabled")


# -- process-wide accessor for non-DI consumers (the research service and /capabilities) -------------------------------------------------------
_lock = threading.Lock()
_installed: FeatureFlagService | None = None


def install(session_factory, *, environment: str | None = "from_process") -> FeatureFlagService:
    global _installed
    with _lock:
        _installed = FeatureFlagService(session_factory, environment=environment)
        return _installed


def uninstall() -> None:
    global _installed
    with _lock:
        _installed = None


def effective(key: str) -> bool:
    """The effective value of a code-defined flag. Healthy store: durable override > existing environment baseline. No installed service (bare/offline
    context only): the existing environment baseline. Installed service with an unreadable store: False (fail closed)."""
    d = FeatureFlagService.definition(key)
    svc = _installed
    # Two DISTINCT cases. (A) No durable service was ever installed: a bare/offline construction (a unit test with no database wiring). It keeps the
    # existing pre-W10.11 environment baseline for compatibility. (B) Every real application process installs the durable service
    # (``build_repository``); once installed, an unreadable authoritative store FAILS CLOSED: the effective value is False. We must not guess the
    # durable state, and a restriction (an explicit disable) must never be silently lifted by an outage.
    if svc is None:
        return d.baseline()
    try:
        return svc.effective(key)
    except FeatureFlagStateUnavailable:
        return False
