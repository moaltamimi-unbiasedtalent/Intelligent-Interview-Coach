"""Admin Command Center read model (P10B-W10.1). Truthful, cheap, no provider calls.

* Build metadata comes from deployment-injected env (``APP_GIT_SHA``, ``APP_BUILD_TIME``); anything
  absent is reported as ``unknown`` (never guessed, never ``git`` shelled out per request).
* Migration status compares the repository's Alembic head (read from the migration scripts) with the
  database revision (``alembic_version``). It never runs a migration.
* Rate-limit mode is reported as process-local unless a shared store is actually active.
* Pause state is process-local and non-durable (SEC-W10-05 is fixed in W10.11, not here).
* The privacy-request queue is deliberately withheld (SEC-W10-04 belongs to W10.10): no fake zero.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SAFE_TOKEN = re.compile(r"[^A-Za-z0-9._:+\-]")


def _env_token(name: str, fallback: str = "unknown", limit: int = 64) -> str:
    raw = (os.environ.get(name) or "").strip()
    return _SAFE_TOKEN.sub("", raw)[:limit] or fallback


def build_info(version: str) -> dict[str, Any]:
    env = (os.environ.get("API_ENV", "development") or "development").strip().lower()
    return {
        "version": version,
        "git_sha": _env_token("APP_GIT_SHA"),
        "build_time": _env_token("APP_BUILD_TIME", limit=40),
        "environment": env if env in {"development", "test", "staging", "production"} else "unknown",
        "source": "deployment environment (APP_GIT_SHA / APP_BUILD_TIME); 'unknown' when not injected",
    }


def repository_head() -> str | None:
    """Alembic head from the migration scripts on disk (no DB access). None if unreadable."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config(str(_REPO_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(_REPO_ROOT / "migrations"))
        heads = ScriptDirectory.from_config(cfg).get_heads()
        return heads[0] if len(heads) == 1 else ",".join(sorted(heads)) or None
    except Exception:  # noqa: BLE001 - alembic or scripts absent in this deployment
        return None


def database_revision(session_factory) -> str | None:
    """Revision recorded in the DB (``alembic_version``). None when absent/unreadable."""
    try:
        from sqlalchemy import text

        with session_factory() as s:
            row = s.execute(text("SELECT version_num FROM alembic_version")).first()
            return str(row[0]) if row else None
    except Exception:  # noqa: BLE001
        return None


def migration_status(session_factory) -> dict[str, Any]:
    head, db = repository_head(), database_revision(session_factory)
    if head is None or db is None:
        state, warning = "unknown", ("Migration state could not be determined "
                                     "(no Alembic scripts or no alembic_version table).")
    elif head == db:
        state, warning = "match", None
    else:
        state, warning = "mismatch", ("Database revision differs from the repository migration head. "
                                      "Ask4Mo never migrates automatically; run the migration deliberately.")
    return {"repository_head": head, "database_revision": db, "state": state, "warning": warning}


def health_summary(session_factory) -> dict[str, Any]:
    """Safe internal health: a cheap DB ping only. No provider call, no secret, no raw error text."""
    try:
        from sqlalchemy import text

        with session_factory() as s:
            s.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    return {"database": "reachable" if db_ok else "unreachable",
            "providers_probed": False,
            "note": "Internal checks only. Provider health is not tested here."}


def rate_limit_mode() -> dict[str, Any]:
    try:
        from src.api.rate_limit import shared_store_active, shared_store_requested

        active, requested = bool(shared_store_active()), bool(shared_store_requested())
    except Exception:  # noqa: BLE001
        active, requested = False, False
    return {
        "mode": "shared_store" if active else "in_memory_process_local",
        "distributed": active,
        "shared_store_requested": requested,
        "note": ("Limits are enforced per process; they are not shared across replicas."
                 if not active else "A shared store is active."),
    }


def pause_state() -> dict[str, Any]:
    from src.application.pause import get_pause_registry

    return {"paused": get_pause_registry().snapshot(), "durable": False,
            "note": "Process-local and non-durable: resets on restart and is not shared across replicas."}


def command_center(*, version: str, session_factory, accounts, workspaces, allowed: frozenset[str],
                   support=None, plans=None, integrations=None, jobs=None) -> dict[str, Any]:
    """Assemble the overview. Sections the caller lacks permission for are omitted, not blanked."""
    out: dict[str, Any] = {
        "build": build_info(version),
        "migrations": migration_status(session_factory),
        "health": health_summary(session_factory),
        "rate_limit": rate_limit_mode(),
        "pause": pause_state(),
        "privacy_requests": {"status": "not_operational",
                             "note": "Privacy-request administration is not available yet."},
        "accounts": accounts.account_stats(),
        "workspaces": workspaces.workspace_stats(),
        "diagnostics_links": [],
        "boundary": "Operational metadata only. No candidate-private content is accessible here.",
    }
    if support is not None and "platform.support.read" in allowed:
        # Counts only; no message text, and no SLA/breach figures (no SLA policy exists).
        out["support"] = {k: v for k, v in support.stats().items()}
    if plans is not None and ("platform.plans.read" in allowed or "platform.subscriptions.read" in allowed):
        # Counts only: no revenue, price or payment figure exists (billing is not implemented).
        out["plans"] = plans.stats()
    if integrations is not None and "platform.integrations.read" in allowed:
        # Counts only: nothing here is a secret, and "healthy" is never inferred (only a manual test sets it).
        out["integrations"] = integrations.stats()
    if jobs is not None and "platform.jobs.read" in allowed:
        # Counts only: no payload, no error body and no candidate data. Queue depth never implies a healthy worker.
        out["jobs"] = jobs.stats()
    links = []
    if "platform.knowledge.read" in allowed:
        links.append({"label": "Knowledge readiness", "path": "/review/rag"})
    if "platform.ai.read" in allowed:
        links.append({"label": "Evaluation & agent review", "path": "/review/evaluation"})
    out["diagnostics_links"] = links
    return out
