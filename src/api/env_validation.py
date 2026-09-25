"""Runtime environment validation for hosted operation (Capstone P8, §31).

Differentiates DEVELOPMENT / TEST / STAGING / PRODUCTION and, in production, FAILS FAST when a
mandatory dependency is missing instead of booting "healthy" (§31). Optional providers disable
themselves safely and are reported as warnings, never hard failures.

Called from ``create_app``; in production a CRITICAL problem raises ``RuntimeError`` so the app
does not start. Also exposed as a pure ``validate_runtime_config`` for the hosting-readiness
evaluator (no side effects, no provider calls).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

__all__ = ["EnvReport", "validate_runtime_config", "enforce_runtime_config", "runtime_env"]

_DEV_ENVS = {"development", "dev", "local"}
_TEST_ENVS = {"test", "testing"}
_DEFAULT_SQLITE = "sqlite:///data/interview_studio.db"


def runtime_env() -> str:
    return (os.environ.get("API_ENV", "development") or "development").strip().lower()


@dataclass
class EnvReport:
    env: str
    critical: list[str] = field(default_factory=list)   # must-fix in production
    warnings: list[str] = field(default_factory=list)   # optional/degraded features

    @property
    def ok(self) -> bool:
        return not self.critical

    def to_dict(self) -> dict:
        return {"env": self.env, "ok": self.ok, "critical": list(self.critical),
                "warnings": list(self.warnings)}


def _has(name: str) -> bool:
    return bool((os.environ.get(name, "") or "").strip())


def validate_runtime_config(env: str | None = None) -> EnvReport:
    """Classify configuration for the current (or given) environment. No side effects."""
    env = (env or runtime_env()).strip().lower()
    report = EnvReport(env=env)
    is_dev = env in _DEV_ENVS or env in _TEST_ENVS
    is_prod = env == "production"
    # Staging is treated like production for MOST checks but downgrades email to a warning
    # (private staging may use console email until public launch).
    prod_like = is_prod or env == "staging"

    if is_dev:
        return report  # dev/test are permissive by design

    # --- Critical in production (and staging) ---
    if not _has("FRONTEND_ORIGINS"):
        report.critical.append("FRONTEND_ORIGINS must be set (no wildcard CORS in hosted envs).")
    db = (os.environ.get("DATABASE_URL", "") or "").strip()
    if not db:
        report.critical.append("DATABASE_URL must be set in hosted environments.")
    elif db == _DEFAULT_SQLITE or db.startswith("sqlite"):
        (report.critical if is_prod else report.warnings).append(
            "DATABASE_URL should be PostgreSQL in hosted operation (SQLite is dev-only).")
    if not _has("APP_BASE_URL"):
        report.critical.append("APP_BASE_URL must be set (used for links, cookies, OIDC redirect).")
    if not _has("SESSION_SECRET") and is_prod:
        # Sessions are opaque server-side tokens, but a deployment secret is expected for prod.
        report.warnings.append("SESSION_SECRET is not set (recommended for production).")
    if not _has("OPENROUTER_API_KEY"):
        report.warnings.append(
            "OPENROUTER_API_KEY is not set — Mo/LLM features will be unavailable.")

    # --- Open verified-email registration requires a real email provider (§22) ---
    registration_paused = "public_registration" in (
        os.environ.get("PAUSED_CAPABILITIES", "") or "")
    email_provider = (os.environ.get("EMAIL_PROVIDER", "console") or "console").strip().lower()
    email_ready = email_provider == "brevo" and _has("BREVO_API_KEY") and _has("EMAIL_SENDER")
    if not registration_paused and not email_ready:
        msg = ("Open verified-email registration requires a configured email provider "
               "(EMAIL_PROVIDER=brevo + BREVO_API_KEY + EMAIL_SENDER), or pause "
               "public_registration.")
        (report.critical if is_prod else report.warnings).append(msg)

    # --- Optional providers: warnings only (they disable themselves safely) ---
    if _has("FEATURE_GOOGLE_LOGIN") and not (_has("GOOGLE_CLIENT_ID") and _has("GOOGLE_CLIENT_SECRET")):
        report.warnings.append(
            "FEATURE_GOOGLE_LOGIN is on but GOOGLE_CLIENT_ID/SECRET are missing — Google "
            "sign-in will stay disabled.")
    if _has("REALTIME_VOICE_ENABLED") and not _has("REALTIME_VOICE_API_KEY"):
        report.warnings.append(
            "REALTIME_VOICE_ENABLED is on but REALTIME_VOICE_API_KEY is missing — realtime "
            "voice will fall back to turn-based.")
    if prod_like and not _has("DOCUMENT_STORAGE_DIR"):
        report.warnings.append(
            "DOCUMENT_STORAGE_DIR is not set — private uploads will use a temp directory "
            "(configure durable private storage for hosted operation).")

    return report


def enforce_runtime_config() -> EnvReport:
    """Validate and, in production, raise on any CRITICAL problem so the app fails fast."""
    report = validate_runtime_config()
    if report.env == "production" and report.critical:
        raise RuntimeError(
            "Production configuration is incomplete:\n  - " + "\n  - ".join(report.critical))
    return report
