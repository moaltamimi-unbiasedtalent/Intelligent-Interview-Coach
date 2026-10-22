"""Hosted-topology readiness probes (05A): data-root writability, worker heartbeat staleness and scanner reachability.

Every probe is local (a file in the data root, one DB read, one TCP connect to the scanner) and returns a short status word: never a
path, host, exception text or secret. No provider is called. The worker container healthcheck reuses ``worker_heartbeat_fresh``.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from src.jobs.service import WORKER_STALE_SECONDS


def data_root_writable() -> bool:
    """True when the authoritative data root (COPILOT_DATA_DIR) exists and a file can be created and removed in it."""
    from src.copilot.constants import resolve_data_root

    probe: Path | None = None
    try:
        root = resolve_data_root()
        root.mkdir(parents=True, exist_ok=True)
        probe = root / f".ready-{uuid.uuid4().hex}"
        probe.write_bytes(b"ok")
        return True
    except Exception:  # noqa: BLE001 - the path and the error are never reported
        return False
    finally:
        try:
            if probe is not None:
                probe.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass


def worker_heartbeat_fresh(session_factory, *, max_age_seconds: int = WORKER_STALE_SECONDS, now: datetime | None = None) -> bool:
    """True when at least one worker in status ``running`` has been seen within ``max_age_seconds``."""
    from src.persistence import JobWorker

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=max_age_seconds)
    with session_factory() as s:
        rows = s.scalars(select(JobWorker).where(JobWorker.status == "running")).all()
    for w in rows:
        seen = w.last_seen_at
        if seen is not None and seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        if seen is not None and seen >= cutoff:
            return True
    return False


def worker_status(session_factory) -> str:
    """``ok`` | ``stale`` (no recent heartbeat) | ``unknown`` (the store could not be read)."""
    try:
        return "ok" if worker_heartbeat_fresh(session_factory) else "stale"
    except Exception:  # noqa: BLE001
        return "unknown"


def scanner_status() -> str:
    """``reachable`` | ``unreachable`` | ``not_configured`` (no ClamAV provider selected; ``fake``/unset are never reported as reachable)."""
    if (os.environ.get("FILE_SCAN_PROVIDER", "") or "").strip().lower() != "clamav":
        return "not_configured"
    try:
        from src.documents.file_security import build_file_scanner

        return "reachable" if build_file_scanner().available() else "unreachable"
    except Exception:  # noqa: BLE001
        return "unreachable"


def is_hosted(env: str | None = None) -> bool:
    from src.api.env_validation import runtime_env

    return (env or runtime_env()) in ("staging", "production")


def scanner_signature_status() -> str:
    """``fresh`` | ``stale`` | ``unknown`` (real scanner not reachable/not configured, or the signature date could not be read). Status word only."""
    if (os.environ.get("FILE_SCAN_PROVIDER", "") or "").strip().lower() != "clamav":
        return "unknown"
    from src.documents.file_security import scanner_health

    return scanner_health().get("signatures", "unknown")
