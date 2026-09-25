"""Retention inventory + safe temporary-artifact cleanup (Capstone P6/E7, §26/§27).

Two things:
1. A RETENTION INVENTORY that CLASSIFIES every relevant data store (application-required /
   user-controlled / temporary / operational / audit-security / external-provider-governed)
   with its deletion path. It invents NO legal retention periods — it records the technical
   default/configurable window where one is known.
2. A safe :class:`TemporaryArtifactCleaner` for app-OWNED temporary/generated artifacts.
   Dry-run is the default; it only ever touches files UNDER its configured root (a path
   outside the root, or a traversal, is refused — it can never delete another owner's or a
   private artifact); it preserves committed evidence (README/.gitkeep); and it is
   idempotent (a second run finds nothing new).

This module performs NO destructive action by default and makes no network/model call.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "RetentionClass", "RetentionEntry", "retention_inventory",
    "TemporaryArtifactCleaner", "CleanupManifest",
]


class RetentionClass(str):
    APPLICATION_REQUIRED = "application_required"
    USER_CONTROLLED = "user_controlled"
    TEMPORARY = "temporary"
    OPERATIONAL = "operational"
    AUDIT_SECURITY = "audit_security"
    EXTERNAL_PROVIDER = "external_provider_governed"


@dataclass(frozen=True)
class RetentionEntry:
    resource: str
    classification: str
    owner_controlled: bool
    default_retention: str          # technical default/configurable — never a legal claim
    deletion_path: str
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "resource": self.resource, "classification": self.classification,
            "owner_controlled": self.owner_controlled,
            "default_retention": self.default_retention,
            "deletion_path": self.deletion_path, "notes": self.notes,
        }


def retention_inventory() -> list[dict]:
    """The classified retention inventory (safe metadata; no legal periods invented)."""
    entries = [
        RetentionEntry("auth sessions (server-side cookie sessions)", RetentionClass.OPERATIONAL,
                       False, "expiry-based (session TTL); configurable",
                       "session store expiry + logout", "Expired sessions are cleanup-eligible."),
        RetentionEntry("email-verification / password-reset tokens", RetentionClass.OPERATIONAL,
                       False, "short expiry (token TTL)", "token expiry + single-use consumption",
                       "Expired/used tokens are cleanup-eligible."),
        RetentionEntry("audit events", RetentionClass.AUDIT_SECURITY, False,
                       "retained for security review; not user-deletable",
                       "not routinely deleted (security)", "Preserved; not cleaned by temp cleanup."),
        RetentionEntry("agent runs / LangGraph checkpoints", RetentionClass.USER_CONTROLLED,
                       True, "until the user deletes the run",
                       "DELETE /agent/runs/{id} (saver delete_thread)",
                       "Bulk age-based checkpoint cleanup remains a gap (no safe bulk list API)."),
        RetentionEntry("interview_sessions (in-progress)", RetentionClass.OPERATIONAL, True,
                       "stale window (INTERVIEW_SESSION_RETENTION_DAYS)",
                       "scripts/cleanup_runtime_data.py (dry-run default)",
                       "Never touches completed history/memory/checkpoints."),
        RetentionEntry("candidate feedback", RetentionClass.USER_CONTROLLED, True,
                       "until the user deletes it or account deletion",
                       "DELETE /feedback + account cascade", "Stores references + rating, minimal content."),
        RetentionEntry("Prompt Lab experiments", RetentionClass.OPERATIONAL, False,
                       "retained as engineering evidence; archivable",
                       "archive/delete via reviewer tooling (var/prompt_lab)",
                       "Synthetic/approved data only; no candidate content."),
        RetentionEntry("evaluation artifacts (generated runs)", RetentionClass.TEMPORARY, False,
                       "regenerable; stale runs cleanup-eligible",
                       "temp cleanup of generated run dirs",
                       "Committed baselines (11R, RAGAS deterministic) are PRESERVED."),
        RetentionEntry("temporary upload / OCR working files", RetentionClass.TEMPORARY, False,
                       "transient (per request)", "temp cleanup", "App-owned scratch only."),
        RetentionEntry("private documents / claims / stories", RetentionClass.USER_CONTROLLED,
                       True, "until user/account deletion",
                       "document delete + account cascade (private-file purge carried)",
                       "Never touched by temp cleanup."),
        RetentionEntry("report exports (downloaded)", RetentionClass.USER_CONTROLLED, True,
                       "leaves app control once downloaded", "n/a (client-held)",
                       "Not persisted server-side by default."),
        RetentionEntry("observability traces", RetentionClass.EXTERNAL_PROVIDER, False,
                       "provider-governed when enabled (OFF by default)",
                       "provider retention settings", "Sanitised projections only; no content."),
        RetentionEntry("generated knowledge indexes (Chroma / structured DBs)",
                       RetentionClass.TEMPORARY, False, "regenerable from sources",
                       "rebuild scripts; temp cleanup of stale builds", "Git-ignored generated artifacts."),
    ]
    return [e.to_dict() for e in entries]


@dataclass
class CleanupManifest:
    root: str
    dry_run: bool
    retention_days: int
    candidates: list[str]          # relative paths eligible for deletion
    deleted: list[str]
    skipped_preserved: list[str]
    bytes_reclaimable: int

    def to_dict(self) -> dict:
        return {
            "root": self.root, "dry_run": self.dry_run, "retention_days": self.retention_days,
            "candidates": self.candidates, "deleted": self.deleted,
            "skipped_preserved": self.skipped_preserved,
            "bytes_reclaimable": self.bytes_reclaimable,
        }


_PRESERVE_NAMES = {"README.md", ".gitkeep", ".gitignore"}


class TemporaryArtifactCleaner:
    """Safe cleanup of app-owned temporary/generated files under ONE configured root.

    Dry-run by default. Only files strictly under ``root`` are ever eligible; a path that
    escapes the root is refused (a foreign/private artifact can never be deleted). Files
    younger than the retention window, and preserved names, are always skipped. Idempotent.
    """

    def __init__(self, root: Path | str, *, retention_days: int = 7,
                 preserve_names: set[str] | None = None) -> None:
        self._root = Path(root).resolve()
        self._retention_days = max(0, int(retention_days))
        self._preserve = preserve_names or _PRESERVE_NAMES

    def _is_within_root(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self._root)
            return True
        except ValueError:
            return False

    def scan(self) -> list[Path]:
        """Stale files (older than the retention window) strictly under the root."""
        if not self._root.is_dir():
            return []
        cutoff = time.time() - self._retention_days * 86400
        stale: list[Path] = []
        for path in self._root.rglob("*"):
            if not path.is_file() or path.name in self._preserve:
                continue
            if not self._is_within_root(path):  # defence in depth against symlink escape
                continue
            try:
                if path.stat().st_mtime < cutoff:
                    stale.append(path)
            except OSError:
                continue
        return sorted(stale)

    def clean(self, *, dry_run: bool = True) -> CleanupManifest:
        """Report (dry-run) or delete stale files. Never deletes outside the root."""
        stale = self.scan()
        candidates, deleted = [], []
        reclaimable = 0
        for path in stale:
            rel = str(path.relative_to(self._root))
            try:
                reclaimable += path.stat().st_size
            except OSError:
                pass
            candidates.append(rel)
            if not dry_run:
                # Final guard: never delete outside the root, even if scan were wrong.
                if self._is_within_root(path):
                    try:
                        path.unlink()
                        deleted.append(rel)
                    except OSError:
                        pass
        return CleanupManifest(
            root=str(self._root), dry_run=dry_run, retention_days=self._retention_days,
            candidates=candidates, deleted=deleted, skipped_preserved=sorted(self._preserve),
            bytes_reclaimable=reclaimable,
        )
