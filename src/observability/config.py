"""Observability configuration — resolved ONCE, safely (Phase 7D, §3/§28/§29/§30/§36).

All telemetry knobs live here so business code never reads env vars or the SDK directly.
Nothing in this module performs network I/O or raises: a missing/invalid setting degrades to
"disabled", never a startup failure (§36). The release tag and environment are resolved once
(not per request, §30).
"""

from __future__ import annotations

import functools
import os
from dataclasses import dataclass

__all__ = ["ObservabilityConfig", "load_config", "resolve_release", "resolve_environment"]

# Enable flag — reuse the existing P5 env name so nothing regresses.
ENABLED_ENV = "AGENT_EXTERNAL_OBSERVABILITY_ENABLED"


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _clamp01(raw: str | None, default: float) -> float:
    if raw is None or not raw.strip():
        return default
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return default


@functools.lru_cache(maxsize=1)
def resolve_environment() -> str:
    """development | test | production — from env, resolved once. Never a hostname/path (§29)."""
    env = (os.environ.get("ASK4MO_ENV") or os.environ.get("APP_ENV")
           or os.environ.get("ENVIRONMENT") or "").strip().lower()
    if env in ("prod", "production"):
        return "production"
    if env in ("test", "testing", "ci"):
        return "test"
    if env in ("dev", "development", "local"):
        return "development"
    # Default: 'test' under pytest, else 'development'. Never 'production' by accident.
    return "test" if os.environ.get("PYTEST_CURRENT_TEST") else "development"


@functools.lru_cache(maxsize=1)
def resolve_release() -> str | None:
    """A safe version/release tag resolved ONCE (§30): explicit env → package version → short
    git SHA (a single subprocess call, cached). Never a per-request git call; never a path."""
    explicit = (os.environ.get("ASK4MO_RELEASE") or os.environ.get("GIT_SHA")
                or os.environ.get("SOURCE_VERSION") or "").strip()
    if explicit:
        return explicit[:64]
    try:
        from importlib.metadata import version
        v = version("interview-practice-studio")
        if v:
            return v
    except Exception:  # noqa: BLE001
        pass
    try:
        import subprocess
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S603,S607
            stderr=subprocess.DEVNULL, timeout=2).decode().strip()
        return sha or None
    except Exception:  # noqa: BLE001
        return None


@dataclass(frozen=True)
class ObservabilityConfig:
    """Resolved, immutable telemetry settings."""

    enabled: bool = False
    public_key_present: bool = False
    secret_key_present: bool = False
    host: str | None = None
    environment: str = "development"
    release: str | None = None
    sample_rate: float = 1.0
    capture_content: bool = False          # §10 — content capture is OFF in Phase 7D
    flush_timeout_seconds: float = 2.0     # bounded shutdown flush (§32)

    @property
    def credentials_present(self) -> bool:
        return self.public_key_present and self.secret_key_present

    @property
    def active(self) -> bool:
        """True only when enabled AND credentials are present (the sink can actually emit)."""
        return self.enabled and self.credentials_present

    def status(self) -> str:
        """DISABLED | NOT CONFIGURED | READY (for check/audit scripts, §44)."""
        if not self.enabled:
            return "DISABLED"
        if not self.credentials_present:
            return "NOT CONFIGURED"
        return "READY"


def load_config() -> ObservabilityConfig:
    """Read the environment and return a resolved config. Never raises."""
    return ObservabilityConfig(
        enabled=_flag(ENABLED_ENV),
        public_key_present=bool(os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()),
        secret_key_present=bool(os.environ.get("LANGFUSE_SECRET_KEY", "").strip()),
        host=(os.environ.get("LANGFUSE_HOST", "").strip() or None),
        environment=resolve_environment(),
        release=resolve_release(),
        sample_rate=_clamp01(os.environ.get("LANGFUSE_SAMPLE_RATE"), 1.0),
        capture_content=_flag("LANGFUSE_CAPTURE_CONTENT", default=False),
    )
