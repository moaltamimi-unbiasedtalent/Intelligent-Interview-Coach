"""Runtime resolver for the governed AI configuration (P10B-W10.7).

Installed once per process (API and worker) through ``install_resolver``. It answers one question for the registry seam in
``src/llm/governed.py``: "is a configuration active for THIS environment, and what does it resolve to?"

* Fail closed to code-defined behaviour. A missing table, a database error, a hash mismatch, a non-approved version, an unknown catalogue id or
  a catalogue-version change all resolve to ``None`` (the code defaults), never to a partial or guessed configuration. A failure is logged as a
  category only.
* The loaded configuration is re-verified at load time (hash recomputed from the stored content, state approved, an approved distinct-approver
  record present, a passed evaluation bound to the hash), so a hand-edited database row cannot activate anything.
* Cache: one snapshot per process with a short TTL (default 5 s) so a hot path never queries per call, plus an explicit ``invalidate`` that the
  service calls on activate/rollback in the SAME process. Other processes (for example the worker) converge within the TTL; there is no
  broadcast and no external cache.
* The environment is derived from ``API_ENV`` (see ``environment_name``): development/dev/local/test/testing -> development, staging -> staging,
  production/prod -> production, anything else -> unsupported (code defaults, activation refused). Development is never staging.
"""

from __future__ import annotations

import logging
import os
import threading
import time

from sqlalchemy import select

from src.ai_admin import catalogue as C
from src.ai_admin import config as K
from src.ai_admin.evaluator import EVALUATOR_VERSION, snapshot_for
from src.llm import governed
from src.persistence import AIConfigActivation as ACT, AIConfigApproval as APR, AIConfigEvaluation as EV, AIConfigVersion as V

log = logging.getLogger(__name__)
DEFAULT_TTL_S = 5.0


# The deployment's own API_ENV decides which activation environment a process belongs to. Aliases follow the repository's existing vocabulary
# (billing MOCK_ALLOWED_ENVS: development, dev, test, testing, local). Development is NEVER staging evidence. An unrecognised value is
# UNSUPPORTED: the process resolves code defaults and refuses governed activation (it never becomes staging or production).
_ALIASES = {"development": "development", "dev": "development", "local": "development", "test": "development", "testing": "development",
            "staging": "staging", "stage": "staging", "production": "production", "prod": "production"}


def environment_name(api_env: str | None = None) -> str | None:
    """The activation environment of this process, or None when API_ENV is not a recognised name (fail closed)."""
    env = (api_env if api_env is not None else os.environ.get("API_ENV") or "development").strip().lower()
    return _ALIASES.get(env)


def resolve_profiles_for(config_json: dict | None) -> dict:
    """Profile -> {catalogue id, provider slug, source} for a configuration, or the code-defined baseline (including environment overrides)."""
    from src.llm.models import ModelProfile, code_model_id

    out = {}
    for p in ModelProfile:
        if config_json:
            entry = config_json["profiles"][p.value]
            out[p.value] = {"catalogue_id": entry, "provider_slug": C.slug_for(entry), "source": "governed_configuration"}
        else:
            slug = code_model_id(p)
            from src.llm.models import default_slug
            out[p.value] = {"catalogue_id": next((e.id for e in C.CATALOGUE.values() if e.slug == slug), None), "provider_slug": slug,
                            "source": "environment_override" if slug != default_slug(p) else "code_default"}
    return out


class GovernedResolver:
    def __init__(self, session_factory, *, environment: str | None = "from_process", ttl_s: float = DEFAULT_TTL_S) -> None:
        self._sf = session_factory
        self.environment = environment_name() if environment == "from_process" else environment   # None = unsupported: never loads a configuration
        self._ttl = ttl_s
        self._lock = threading.Lock()
        self._expires = 0.0
        self._snapshot: governed.GovernedSnapshot | None = None
        self.last_error: str | None = None
        self.loads = 0

    def invalidate(self) -> None:
        with self._lock:
            self._expires = 0.0

    def __call__(self) -> governed.GovernedSnapshot | None:
        now = time.monotonic()
        with self._lock:
            if now < self._expires:
                return self._snapshot
        snap, error = self._load()
        with self._lock:
            self._snapshot, self.last_error, self._expires = snap, error, time.monotonic() + self._ttl
            self.loads += 1
            return snap

    def _load(self) -> tuple[governed.GovernedSnapshot | None, str | None]:
        try:
            if self.environment is None:
                return None, "unsupported_environment"
            with self._sf() as s:
                act = s.scalar(select(ACT).where(ACT.environment == self.environment, ACT.deactivated_at.is_(None)))
                if act is None or act.config_version_id is None:
                    return None, None
                v = s.get(V, act.config_version_id)
                if v is None or v.state != "approved":
                    return None, "version_not_approved"
                canonical = K.normalise(v.config_json)
                if K.config_hash(canonical, v.catalogue_version) != v.config_hash or act.config_hash != v.config_hash:
                    return None, "hash_mismatch"
                if v.catalogue_version != C.CATALOGUE_VERSION:
                    return None, "catalogue_changed"
                ev = s.scalar(select(EV).where(EV.config_version_id == v.id).order_by(EV.id.desc()))
                if ev is None or ev.status != "passed" or ev.config_hash != v.config_hash or ev.evaluator_version != EVALUATOR_VERSION or ev.live_calls != 0:
                    return None, "no_passed_evaluation"
                ap = s.scalar(select(APR).where(APR.config_version_id == v.id, APR.status == "approved").order_by(APR.id.desc()))
                if (ap is None or ap.config_hash != v.config_hash or ap.decided_by_user_id is None
                        or ap.decided_by_user_id == ap.requested_by_user_id or ap.decided_by_user_id == v.created_by_user_id):
                    return None, "no_distinct_approval"
                return snapshot_for(canonical, version_public_id=v.public_id, version=v.version, cfg_hash=v.config_hash, environment=self.environment), None
        except Exception:  # noqa: BLE001 - fail closed to the code-defined registry
            log.warning("governed AI configuration could not be loaded; using code defaults")
            return None, "load_failed"


_installed: GovernedResolver | None = None


def install_resolver(session_factory, *, environment: str | None = "from_process", ttl_s: float = DEFAULT_TTL_S) -> GovernedResolver:
    """Idempotently install the resolver for this process (a second call replaces it)."""
    global _installed
    _installed = GovernedResolver(session_factory, environment=environment, ttl_s=ttl_s)
    governed.set_provider(_installed)
    return _installed


def installed() -> GovernedResolver | None:
    return _installed


def uninstall_resolver() -> None:
    global _installed
    _installed = None
    governed.clear()


def runtime_view(resolver: GovernedResolver | None = None) -> dict:
    """Safe, read-only diagnostic of what THIS process resolves right now (no secret, no prompt, no provider call)."""
    from src.llm.models import ModelProfile
    from src.llm.policy import ModelOperation, resolve_policy

    resolver = resolver or _installed
    snap = governed.current()
    profiles = {}
    for p in ModelProfile:
        from src.llm.models import code_model_id, default_slug, model_id

        slug = model_id(p)
        profiles[p.value] = {
            "catalogue_id": next((e.id for e in C.CATALOGUE.values() if e.slug == slug), None), "provider_slug": slug,
            "source": "governed_configuration" if snap else ("environment_override" if code_model_id(p) != default_slug(p) else "code_default")}
    ops = []
    for op in ModelOperation:
        r = resolve_policy(op, None)
        tuned = snap.operation_overrides.get(op.value, {}) if snap else {}
        # A numeric value is a governed override in force; None means INHERIT (the consumer keeps its own default). The code policy table is advisory.
        ops.append({"operation": op.value, "capability": r.capability.value, "uses_model": r.uses_model, "profile": r.profile.value if r.profile else None,
                    "provider_slug": r.model_id, "max_output_tokens": tuned.get("max_output_tokens"), "timeout_s": tuned.get("timeout_s"),
                    "max_retries": tuned.get("max_retries")})
    from src.voice.realtime import realtime_policy_summary

    rt = realtime_policy_summary()
    return {"environment": (resolver.environment if resolver else environment_name()) or "unsupported", "mode": "governed" if snap else "code_defaults",
            "active_version": snap.version if snap else None, "content_hash": snap.config_hash if snap else None,
            "fallback_reason": resolver.last_error if resolver else None, "profiles": profiles, "operations": ops,
            "realtime": {"capability": rt["capability"], "chat_slug": rt["model_id"], "governed": False},
            "note": "Realtime voice, deterministic operations, the three specialists and the Interview session profile are code-defined and unaffected."}
