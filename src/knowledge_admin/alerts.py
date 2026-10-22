"""In-app Admin alerts for knowledge health (package 02A part 2, REQ-OWN-05 K8). No external paging, no new alert mechanism.

The alert store is the EXISTING one (``src.admin_security.alerts``: code-defined categories, one row per logical condition keyed by a stable dedupe key, a
recurrence of a resolved condition reopens the same row). This module only DERIVES conditions from facts the environment guard and the job table already
hold and maps them to four new categories (added by migration 0040, the only schema change of package 02A):

* ``knowledge_collection_lost``       governed collection empty/missing/short or unreadable while the registry records built indexes
* ``knowledge_source_files_missing``  private source files recorded in the registry are missing from the private file store
* ``knowledge_identity_mismatch``     the API and a live worker disagree about the data root, database or embedding settings
* ``knowledge_embedding_mismatch``    the live embedder is incompatible with the index manifest (the producer of this signal is 02B; the mechanism is here)

Failed knowledge jobs reuse the existing ``job_failed`` category with its existing per-job-type dedupe key, so there is exactly one alert per failing job type
whichever path observed it. Emission never raises and never changes the outcome of the request that observed the condition. Alert rows hold only the
code-defined title, the category and a short source id; never a path, a URL, a credential or a message.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from src.admin_security.alerts import record_condition
from src.knowledge_admin import policy as P
from src.persistence import AdminNotification, Job, utcnow

log = logging.getLogger("ask4mo.knowledge.alerts")

COLLECTION_LOST = "knowledge_collection_lost"
FILES_MISSING = "knowledge_source_files_missing"
IDENTITY_MISMATCH = "knowledge_identity_mismatch"
EMBEDDING_MISMATCH = "knowledge_embedding_mismatch"
CATEGORIES = (COLLECTION_LOST, FILES_MISSING, IDENTITY_MISMATCH, EMBEDDING_MISMATCH)
# guard finding code -> alert category
FINDING_CATEGORY = {
    "governed_collection_empty": COLLECTION_LOST, "governed_collection_short": COLLECTION_LOST, "store_unreadable": COLLECTION_LOST,
    "private_files_missing": FILES_MISSING, "private_files_all_missing": FILES_MISSING,
    "identity_mismatch": IDENTITY_MISMATCH,
}
REFRESH_SECONDS = 300            # an already-active alert is refreshed at most this often (the guard runs every few seconds)
KNOWLEDGE_JOB_TYPES = (P.JOB_PARSE, P.JOB_INDEX, P.JOB_REINDEX, P.JOB_REMOVE)


def dedupe_key(category: str) -> str:
    return category                  # one alert per logical condition (category), so a flapping condition reopens the same row


def _aware(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=utcnow().tzinfo)


def _raise(session_factory: Any, category: str, source_id: str | None = None, key: str | None = None) -> None:
    """Create or refresh the alert, but not on every evaluation: an active/acknowledged alert seen in the last REFRESH_SECONDS is left alone."""
    key = key or dedupe_key(category)
    with session_factory() as s:
        row = s.scalar(select(AdminNotification).where(AdminNotification.dedupe_key == key))
        if row is not None and row.state in ("active", "acknowledged") and _aware(row.last_seen_at) > utcnow() - timedelta(seconds=REFRESH_SECONDS):
            return
    record_condition(session_factory, category=category, dedupe_key=key, source_id=source_id)


def _clear(session_factory: Any, category: str) -> None:
    """The condition no longer holds: mark the alert resolved (system resolution, no actor). It reopens if the condition recurs."""
    try:
        with session_factory() as s:
            row = s.scalar(select(AdminNotification).where(AdminNotification.dedupe_key == dedupe_key(category)))
            if row is not None and row.state in ("active", "acknowledged"):
                now = utcnow()
                row.state, row.resolved_at, row.resolved_by_user_id, row.updated_at = "resolved", now, None, now
                row.revision += 1
                s.commit()
    except Exception:  # noqa: BLE001 - alerting must never break the observed operation
        log.warning("knowledge alert could not be cleared")


def observe_guard_report(session_factory: Any, report: Any, *, embedding_mismatch: list[str] | None = None) -> list[str]:
    """Derive alerts from a guard report (and, when 02B supplies it, the embedding mismatch fields). Returns the categories raised (for tests)."""
    raised: list[str] = []
    try:
        present = {FINDING_CATEGORY[f.code] for f in report.findings if f.code in FINDING_CATEGORY}
        if embedding_mismatch:
            present.add(EMBEDDING_MISMATCH)
        for category in CATEGORIES:
            if category in present:
                _raise(session_factory, category, source_id=report.environment[:16])
                raised.append(category)
            elif category != EMBEDDING_MISMATCH or embedding_mismatch is not None:
                _clear(session_factory, category)
        observe_failed_jobs(session_factory)
    except Exception:  # noqa: BLE001
        log.warning("knowledge alert observation failed")
    return raised


def observe_embedding_incompatibility(session_factory: Any, mismatched_fields: list[str]) -> None:
    """For 02B: call with the fields of an ``EmbedderMatch`` (``mismatched_fields`` + ``unknown_fields``); an empty list clears the alert."""
    if mismatched_fields:
        _raise(session_factory, EMBEDDING_MISMATCH, source_id="embedder")
    else:
        _clear(session_factory, EMBEDDING_MISMATCH)


def observe_failed_jobs(session_factory: Any) -> list[str]:
    """One existing ``job_failed`` alert per knowledge job TYPE with a terminally failed job (same key the job service uses, so no duplicates)."""
    seen: list[str] = []
    try:
        with session_factory() as s:
            rows = s.execute(select(Job.job_type, Job.public_id).where(Job.job_type.in_(KNOWLEDGE_JOB_TYPES), Job.state == "failed")
                             .order_by(Job.finished_at.desc())).all()
        latest: dict[str, str] = {}
        for jt, pid in rows:
            latest.setdefault(jt, pid)
        for jt, pid in latest.items():
            _raise(session_factory, "job_failed", source_id=pid, key=f"job_failed:{jt}"[:80])      # the key observe_job_failed uses
            seen.append(jt)
    except Exception:  # noqa: BLE001
        log.warning("failed-job alert observation failed")
    return seen


# ------------------------------------------------------------------ scanner outage (02C)
SCANNER_ALERT_KEY = "scanner_unavailable"      # one alert row for the malware scanner condition (reuses the existing ``job_failed`` category)


SIGNATURE_ALERT_KEY = "scanner_signatures_stale"


def observe_scanner(session_factory: Any, *, available: bool, signatures_stale: bool | None = None) -> None:
    """The malware scanner could not scan (``available=False``: raise the in-app alert) or just completed a scan (``True``: resolve it). Reuses the
    existing ``job_failed`` category with its own dedupe key, so no category and no migration is added. Never raises; the row holds only the
    code-defined title, the category and the short source id ``malware_scanner``."""
    try:
        _set(session_factory, SCANNER_ALERT_KEY, active=not available)
        if signatures_stale is not None:
            _set(session_factory, SIGNATURE_ALERT_KEY, active=bool(signatures_stale))
    except Exception:  # noqa: BLE001 - alerting must never break the observed operation
        log.warning("scanner alert could not be recorded")


def _set(session_factory: Any, key: str, *, active: bool) -> None:
    if active:
        _raise(session_factory, "job_failed", "malware_scanner", key=key)
        return
    with session_factory() as s:
        row = s.scalar(select(AdminNotification).where(AdminNotification.dedupe_key == key))
        if row is None or row.state not in ("active", "acknowledged"):
            return
        now = utcnow()
        row.state, row.resolved_at, row.resolved_by_user_id, row.updated_at = "resolved", now, None, now
        row.revision += 1
        s.commit()
