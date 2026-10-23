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

from src.constants import DEFAULT_DATABASE_URL as _DEFAULT_SQLITE

__all__ = ["EnvReport", "validate_runtime_config", "enforce_runtime_config", "runtime_env"]

_DEV_ENVS = {"development", "dev", "local"}
_TEST_ENVS = {"test", "testing"}


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
    base = (os.environ.get("APP_BASE_URL", "") or "").strip()
    if base and not base.lower().startswith("https://") and is_prod:
        # Verification and recovery links are built from this origin: a hosted production link must not downgrade to plain HTTP.
        report.critical.append("APP_BASE_URL must be an https:// origin in production (verification and recovery links use it).")
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

    # --- Secure credential store (W12.4B): selecting it without a valid master key must not boot "healthy" ---
    backend = (os.environ.get("SECRET_STORE_BACKEND", "environment") or "environment").strip().lower()
    if backend not in ("environment", "encrypted_database"):
        report.critical.append("SECRET_STORE_BACKEND must be 'environment' or 'encrypted_database'.")
    elif backend == "encrypted_database":
        from src.secret_store import master_key_state

        if master_key_state() is not None:
            report.critical.append(
                "SECRET_STORE_BACKEND=encrypted_database requires SECRET_STORE_MASTER_KEY: standard base64 of exactly 32 random bytes.")

    # --- Shared rate-limit store (05D): hosted operation either has it or states the single-process limitation ---
    backend_req = (os.environ.get("RATE_LIMIT_BACKEND", "") or "").strip().lower()
    try:
        from src.core import secrets as _secrets

        redis_url_set = bool((_secrets.read_setting("REDIS_URL") or "").strip())    # the SAME resolution the limiter uses (managed credential, then environment)
    except Exception:  # noqa: BLE001
        redis_url_set = _has("REDIS_URL")
    if backend_req not in ("", "in_memory", "redis", "shared"):
        report.critical.append("RATE_LIMIT_BACKEND must be 'in_memory', 'redis' or 'shared'.")
    elif backend_req in ("redis", "shared"):
        # Requested but unusable would silently fall back to a per-process limiter: refuse to boot instead of pretending to be distributed.
        import importlib.util

        if not redis_url_set:
            report.critical.append("RATE_LIMIT_BACKEND requests a shared store but REDIS_URL is not set (limits would silently stay per process).")
        elif importlib.util.find_spec("redis") is None:
            report.critical.append("RATE_LIMIT_BACKEND requests a shared store but the 'redis' package is not installed (limits would silently stay per process).")
    elif not redis_url_set and (os.environ.get("RATE_LIMIT_SINGLE_PROCESS_ACKNOWLEDGED", "") or "").strip().lower() not in ("1", "true", "yes", "on"):
        report.warnings.append(
            "Rate limits are per process (no shared store). That is correct for ONE replica only; set RATE_LIMIT_BACKEND=redis and REDIS_URL for several "
            "replicas, or set RATE_LIMIT_SINGLE_PROCESS_ACKNOWLEDGED=true to record that this deployment is single-process.")

    # --- Optional providers: warnings only (they disable themselves safely) ---
    if _has("FEATURE_GOOGLE_LOGIN") and not (_has("GOOGLE_CLIENT_ID") and _has("GOOGLE_CLIENT_SECRET")):
        report.warnings.append(
            "FEATURE_GOOGLE_LOGIN is on but GOOGLE_CLIENT_ID/SECRET are missing — Google "
            "sign-in will stay disabled.")
    # --- Billing provider (W12.4D-B): live billing is disabled by a code constant; configuration may only select the sandbox foundation ---
    if _has("BILLING_PROVIDER"):
        provider = os.environ.get("BILLING_PROVIDER", "").strip().lower()
        if provider not in ("disabled", "none", "mock", "stripe_managed_payments"):
            report.critical.append("BILLING_PROVIDER must be 'disabled', 'mock' or 'stripe_managed_payments'.")
        if provider == "stripe_managed_payments":
            stripe_env = (os.environ.get("STRIPE_ENVIRONMENT", "sandbox") or "sandbox").strip().lower()
            if stripe_env not in ("sandbox", "live"):
                report.critical.append("STRIPE_ENVIRONMENT must be 'sandbox' or 'live'.")
            elif stripe_env == "live":
                report.warnings.append("STRIPE_ENVIRONMENT=live is selected, but live billing is disabled in this release: no payment can be processed.")
            elif prod_like:
                report.warnings.append("The Stripe sandbox foundation is selected in a hosted environment: no payment can be processed (no checkout exists).")
    if _has("FEATURE_GOOGLE_LOGIN"):
        redirect = (os.environ.get("OIDC_REDIRECT_URI", "") or "").strip()
        valid = redirect.startswith("https://") and redirect.split("?")[0].split("#")[0].endswith("/api/v1/auth/oidc/google/callback")
        if not valid:
            (report.critical if is_prod else report.warnings).append(
                "FEATURE_GOOGLE_LOGIN is on but OIDC_REDIRECT_URI is not a trusted https URL ending in /api/v1/auth/oidc/google/callback — "
                "the request Host is never trusted for the Google callback in a hosted environment.")
    if _has("REALTIME_VOICE_ENABLED") and not _has("REALTIME_VOICE_API_KEY"):
        report.warnings.append(
            "REALTIME_VOICE_ENABLED is on but REALTIME_VOICE_API_KEY is missing — realtime "
            "voice will fall back to turn-based.")
    # --- Malware scanner (05A): the in-memory fake scanner approves everything and must never run in a hosted environment ---
    scan_provider = (os.environ.get("FILE_SCAN_PROVIDER", "") or "").strip().lower()
    if scan_provider == "fake":
        report.critical.append(
            "FILE_SCAN_PROVIDER=fake is a test double and is refused in hosted environments (use clamav).")
    elif prod_like and scan_provider != "clamav":
        report.warnings.append(
            "FILE_SCAN_PROVIDER is not 'clamav' — uploads are not malware-scanned (set FILE_SCAN_PROVIDER=clamav and MALWARE_SCAN_REQUIRED=true).")
    if prod_like and not _has("COPILOT_DATA_DIR"):
        report.warnings.append(
            "COPILOT_DATA_DIR is not set — the API and worker must share ONE explicit knowledge/index data root on a persistent volume.")
    if prod_like and not _has("DOCUMENT_STORAGE_DIR"):
        report.warnings.append(
            "DOCUMENT_STORAGE_DIR is not set — private uploads will use a temp directory "
            "(configure durable private storage for hosted operation).")

    return report


def enforce_runtime_config() -> EnvReport:
    """Validate and, in hosted environments, raise on any CRITICAL problem so the app fails
    fast rather than booting with missing/insecure config.

    Both PRODUCTION and STAGING fail closed (P10B-W9.1): a missing required CORS allow-list
    (``FRONTEND_ORIGINS``) — or any other critical — stops startup instead of silently opening
    access or serving header-less error responses. Dev/test remain permissive.
    """
    report = validate_runtime_config()
    if report.env in ("production", "staging") and report.critical:
        raise RuntimeError(
            f"Hosted configuration is incomplete (env={report.env}):\n  - "
            + "\n  - ".join(report.critical))
    return report
