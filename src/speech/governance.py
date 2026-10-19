"""Admin governance of the server-side speech providers (W12.4E): validated, durable, audited, revision-protected configuration.

THE INVARIANTS:
* Configuration holds SELECTION and POLICY only: a provider id from a code-defined list, enabled flags, the eligible languages (a subset of the seven-language product boundary; Russian and any other
  language is refused), browser-fallback permissions and timeouts inside fixed bounds. No secret, path, command, endpoint or environment value can be stored or read through it.
* Configuration is NEVER authorization: enabling a provider here does not make it operational. Execution needs the code constants in ``src.speech.policy`` (all False) and the dependency and model.
* No row means the code defaults: providers selected, EVERYTHING DISABLED, all seven languages eligible (narrowed by provider capability), browser fallback allowed (the existing behaviour).
* An unreadable store FAILS CLOSED: server providers are disabled and the browser fallback is reported not allowed (control-plane state that cannot be read is unknown).
* Changes need the expected revision, a reason, and are audited in the same transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from src.persistence import SpeechGovernance as SG, utcnow
from src.speech import policy

__all__ = ["SpeechConfig", "SpeechGovernanceService", "SpeechGovernanceUnavailable", "SpeechGovernanceConflict", "SpeechGovernanceValidationError", "SpeechGovernanceUnsupportedEnvironment",
           "STT_TIMEOUT_BOUNDS", "TTS_TIMEOUT_BOUNDS", "default_config", "MAX_REASON"]

MAX_REASON = 200
STT_TIMEOUT_BOUNDS = (5, 120)
TTS_TIMEOUT_BOUNDS = (5, 60)
_PATCHABLE = {"stt_provider", "tts_provider", "stt_enabled", "tts_enabled", "languages", "browser_stt_allowed", "browser_tts_allowed", "stt_timeout_seconds", "tts_timeout_seconds"}


class SpeechGovernanceUnavailable(Exception):
    pass


class SpeechGovernanceConflict(Exception):
    pass


class SpeechGovernanceValidationError(Exception):
    pass


class SpeechGovernanceUnsupportedEnvironment(Exception):
    pass


@dataclass(frozen=True)
class SpeechConfig:
    stt_provider: str = policy.SELECTED_STT_PROVIDER
    tts_provider: str = policy.SELECTED_TTS_PROVIDER
    stt_enabled: bool = False
    tts_enabled: bool = False
    languages: tuple[str, ...] = policy.PRODUCT_SPEECH_LANGUAGES
    browser_stt_allowed: bool = True
    browser_tts_allowed: bool = True
    stt_timeout_seconds: int = 30
    tts_timeout_seconds: int = 30
    revision: int = 0
    persisted: bool = False
    updated_at: str | None = None
    updated_by_user_id: int | None = None
    reason: str = ""

    def public(self) -> dict:
        return {"stt_provider": self.stt_provider, "tts_provider": self.tts_provider, "stt_enabled": self.stt_enabled, "tts_enabled": self.tts_enabled, "languages": list(self.languages),
                "browser_stt_allowed": self.browser_stt_allowed, "browser_tts_allowed": self.browser_tts_allowed, "stt_timeout_seconds": self.stt_timeout_seconds,
                "tts_timeout_seconds": self.tts_timeout_seconds, "revision": self.revision, "persisted": self.persisted, "updated_at": self.updated_at,
                "updated_by_user_id": self.updated_by_user_id, "reason": self.reason}


def default_config() -> SpeechConfig:
    return SpeechConfig()


def _fail_closed() -> SpeechConfig:
    return SpeechConfig(stt_enabled=False, tts_enabled=False, languages=(), browser_stt_allowed=False, browser_tts_allowed=False)


def _validate_patch(patch: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(patch, dict) or not patch:
        raise SpeechGovernanceValidationError("A change is required.")
    unknown = set(patch) - _PATCHABLE
    if unknown:
        raise SpeechGovernanceValidationError("Only the documented speech settings can be changed.")
    out: dict[str, Any] = {}
    for key, value in patch.items():
        if key == "stt_provider":
            if value not in policy.STT_PROVIDER_IDS:
                raise SpeechGovernanceValidationError("Unknown speech-to-text provider.")
        elif key == "tts_provider":
            if value not in policy.TTS_PROVIDER_IDS:
                raise SpeechGovernanceValidationError("Unknown text-to-speech provider.")
        elif key in ("stt_enabled", "tts_enabled", "browser_stt_allowed", "browser_tts_allowed"):
            if not isinstance(value, bool):
                raise SpeechGovernanceValidationError(f"{key} must be true or false.")
        elif key == "languages":
            if not isinstance(value, (list, tuple)) or not all(isinstance(v, str) for v in value):
                raise SpeechGovernanceValidationError("Languages must be a list of language codes.")
            codes = [v.strip().lower() for v in value]
            if len(set(codes)) != len(codes):
                raise SpeechGovernanceValidationError("Languages must not repeat.")
            bad = [c for c in codes if c not in policy.PRODUCT_SPEECH_LANGUAGES]
            if bad:
                raise SpeechGovernanceValidationError("Speech is offered only in English, German, French, Spanish, Italian, Portuguese and Dutch. Russian is not a speech language.")
            value = [c for c in policy.PRODUCT_SPEECH_LANGUAGES if c in codes]
        elif key in ("stt_timeout_seconds", "tts_timeout_seconds"):
            lo, hi = STT_TIMEOUT_BOUNDS if key == "stt_timeout_seconds" else TTS_TIMEOUT_BOUNDS
            if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
                raise SpeechGovernanceValidationError(f"{key} must be a whole number of seconds between {lo} and {hi}.")
        out[key] = value
    return out


class SpeechGovernanceService:
    def __init__(self, session_factory, *, environment: str | None = "from_process", clock: Callable[[], datetime] = utcnow) -> None:
        if environment == "from_process":
            from src.ai_admin.resolver import environment_name
            environment = environment_name()
        self.environment = environment
        self._sf = session_factory
        self._clock = clock

    def _to_config(self, row: SG | None) -> SpeechConfig:
        if row is None:
            return default_config()
        return SpeechConfig(stt_provider=row.stt_provider, tts_provider=row.tts_provider, stt_enabled=bool(row.stt_enabled), tts_enabled=bool(row.tts_enabled),
                            languages=tuple(c for c in policy.PRODUCT_SPEECH_LANGUAGES if c in (row.languages or [])), browser_stt_allowed=bool(row.browser_stt_allowed),
                            browser_tts_allowed=bool(row.browser_tts_allowed), stt_timeout_seconds=row.stt_timeout_seconds, tts_timeout_seconds=row.tts_timeout_seconds,
                            revision=row.revision, persisted=True, updated_at=row.updated_at.isoformat() if row.updated_at else None, updated_by_user_id=row.updated_by_user_id, reason=row.reason or "")

    def get(self) -> SpeechConfig:
        """The stored configuration (or the defaults). Raises ``SpeechGovernanceUnavailable`` when the store cannot be read."""
        try:
            with self._sf() as s:
                row = s.scalar(select(SG).where(SG.environment == (self.environment or "unsupported")))
                return self._to_config(row)
        except Exception as exc:  # noqa: BLE001 - fixed category only
            raise SpeechGovernanceUnavailable("speech governance state unavailable") from exc

    def get_or_fail_closed(self) -> SpeechConfig:
        try:
            return self.get()
        except SpeechGovernanceUnavailable:
            return _fail_closed()

    def update(self, patch: dict[str, Any], *, expected_revision: int, reason: Any, actor_user_id: int, audit_for: Callable[[dict], dict] | None = None) -> SpeechConfig:
        from src.admin_repository import _stage

        if self.environment is None:
            raise SpeechGovernanceUnsupportedEnvironment("This deployment's environment is not recognised, so speech settings cannot be changed here.")
        text = reason.strip() if isinstance(reason, str) else ""
        if not text or len(text) > MAX_REASON or "\x00" in text:
            raise SpeechGovernanceValidationError(f"A reason is required (up to {MAX_REASON} characters).")
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise SpeechGovernanceValidationError("A valid expected revision is required.")
        changes = _validate_patch(patch)
        now = self._clock()
        with self._sf() as s:
            row = s.scalar(select(SG).where(SG.environment == self.environment))
            current = row.revision if row else 0
            if expected_revision != current:
                raise SpeechGovernanceConflict("The speech settings changed since you loaded them. Reload and review the current state before changing them.")
            before = self._to_config(row)
            if row is None:
                base = default_config().public()
                base.update(changes)
                s.add(SG(environment=self.environment, stt_provider=base["stt_provider"], tts_provider=base["tts_provider"], stt_enabled=base["stt_enabled"], tts_enabled=base["tts_enabled"],
                         languages=list(base["languages"]), browser_stt_allowed=base["browser_stt_allowed"], browser_tts_allowed=base["browser_tts_allowed"],
                         stt_timeout_seconds=base["stt_timeout_seconds"], tts_timeout_seconds=base["tts_timeout_seconds"], revision=1, updated_by_user_id=actor_user_id, updated_at=now, reason=text))
                new_revision = 1
            else:
                res = s.execute(update(SG).where(SG.id == row.id, SG.revision == current).values(**changes, revision=current + 1, updated_by_user_id=actor_user_id, updated_at=now, reason=text))
                if res.rowcount != 1:
                    raise SpeechGovernanceConflict("The speech settings changed since you loaded them. Reload and review the current state before changing them.")
                new_revision = current + 1
            try:
                s.flush()
            except IntegrityError:
                s.rollback()
                raise SpeechGovernanceConflict("The speech settings changed since you loaded them. Reload and review the current state before changing them.")
            spec = audit_for({"changed": sorted(changes), "revision": new_revision}) if audit_for else None
            _stage(s, {**spec, "target_id": self.environment} if spec else None, environment=self.environment, changed=sorted(changes), revision=new_revision,
                   old={k: _plain(getattr(before, k)) for k in changes}, new={k: _plain(v) for k, v in changes.items()})
            s.commit()
        return self.get()


def _plain(v):
    return list(v) if isinstance(v, (tuple, list)) else v
