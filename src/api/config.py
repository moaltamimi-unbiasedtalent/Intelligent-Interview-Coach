"""API-specific configuration for the FastAPI backend.

Reuses the existing environment-reading approach (no second config system) and
holds only settings the HTTP layer needs: the environment label, the version
string, and the CORS allow-list for the future Next.js frontend. No secrets are
stored or exposed here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

API_PREFIX = "/api/v1"
DEFAULT_DEV_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def _project_version() -> str:
    try:
        from importlib.metadata import version

        return version("interview-os-coach")
    except Exception:  # noqa: BLE001 - packaging metadata may be absent in dev
        return "0.1.0"


@dataclass(frozen=True)
class ApiSettings:
    """Resolved API settings (safe to surface in non-secret metadata)."""

    env: str = "development"
    version: str = field(default_factory=_project_version)
    frontend_origins: tuple[str, ...] = DEFAULT_DEV_ORIGINS

    @classmethod
    def from_env(cls) -> "ApiSettings":
        env = (os.environ.get("API_ENV") or "development").strip().lower()
        raw = os.environ.get("FRONTEND_ORIGINS", "").strip()
        if raw:
            origins = tuple(o.strip() for o in raw.split(",") if o.strip())
        elif env == "development":
            # Safe local defaults only; production MUST set FRONTEND_ORIGINS.
            origins = DEFAULT_DEV_ORIGINS
        else:
            origins = ()
        return cls(env=env, version=_project_version(), frontend_origins=origins)
