"""Erasure inventory and residual verification (05E, W9.8-D10).

Account deletion (``AccountDeletionService``) removes every candidate-owned row with explicit, owner-scoped deletes. This module is the SAFETY NET
around that code and is derived from the schema itself, so it cannot be forgotten when a table is added:

* ``user_references`` enumerates EVERY column that points at a user (each foreign key to ``users.id`` plus the few reference columns that carry a user id
  without a foreign key). The deletion service finishes with a sweep over exactly this list: a ``CASCADE`` reference is deleted and a ``SET NULL`` reference is
  cleared. That is what PostgreSQL does for the real foreign keys; SQLite (tests, development) does not enforce foreign keys, so the sweep makes both behave
  the same and means a new table with a user foreign key is erased or anonymised without a code change here.
* ``residual_references`` counts, per reference column, the rows that STILL point at a user. After a complete deletion the result is empty (except the
  documented, deliberately retained rows when a billing reference or a privacy-request row must stay); it is the evidence an erasure is complete and it is
  what the privacy-request deletion job checks before it records the request as completed.
* ``NOT_USER_REFERENCES`` documents the columns whose name suggests a user but which are not a user reference (so a new reference-like column fails a test
  until somebody classifies it).

Nothing here reads or returns candidate content: only table and column names and counts. Backups, the checkpoint store and the private file store are
handled by their own interfaces (see ``docs/production/execution/evidence/05E_EVIDENCE.md``); hosted backups are outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import delete, func, select, update

from src.persistence import Base

# Reference columns that carry a user id WITHOUT a foreign key (kept as plain integers by design: an index or an operator log must outlive the account row
# long enough to be purged). Each is classified here; a new one must be added to this tuple or to NOT_USER_REFERENCES (enforced by a test).
NON_FK_USER_REFERENCES: Final[tuple[tuple[str, str, str], ...]] = (
    ("preparation_runs", "owner_user_id", "erase"),            # the ownership index row is removed after the checkpoint purge succeeded
    ("privacy_requests", "subject_user_id", "clear"),          # cleared (NULL) with the account link
    ("compensation_import_batches", "actor_user_id", "clear"), # an operator's id on a knowledge import batch (no candidate content)
)

# Columns that look like a user reference by name but are not one, with the reason.
NOT_USER_REFERENCES: Final[dict[tuple[str, str], str]] = {
    ("auth_sessions", "user_agent"): "browser identification string of a session row; the whole row is deleted with the account",
    ("jobs", "lease_owner"): "a worker process identifier, not a user",
    ("admin_incidents", "affected_user_estimate"): "a number entered by an operator; not an identifier",
}

# Tables whose user-referencing rows are DELIBERATELY not touched by the sweep in the named retained mode.
RETAINED_FOR_BILLING: Final[frozenset[str]] = frozenset({"billing_provider_links", "billing_checkout_sessions", "billing_account_closures"})
RETAINED_FOR_PRIVACY_REQUEST: Final[frozenset[str]] = frozenset({"privacy_requests"})


@dataclass(frozen=True)
class UserReference:
    table: str
    column: str
    action: str       # "erase" (CASCADE or index row), "clear" (SET NULL or plain clear)
    has_fk: bool


def user_references(metadata=None) -> list[UserReference]:
    """Every column that references a user, derived from the schema. Deterministic order."""
    md = metadata or Base.metadata
    out: list[UserReference] = []
    for table in md.sorted_tables:
        if table.name == "users":
            continue
        for col in table.columns:
            fks = [fk for fk in col.foreign_keys if fk.column.table.name == "users"]
            if not fks:
                continue
            ondelete = (fks[0].ondelete or "").upper()
            out.append(UserReference(table.name, col.name, "erase" if ondelete == "CASCADE" else "clear", True))
    for table_name, col_name, action in NON_FK_USER_REFERENCES:
        if table_name in md.tables and col_name in md.tables[table_name].c:     # (a test may pass a smaller schema)
            out.append(UserReference(table_name, col_name, action, False))
    return sorted(out, key=lambda r: (r.table, r.column))


def unclassified_user_like_columns(metadata=None) -> list[tuple[str, str]]:
    """Columns that look like a user reference (name contains user/owner/actor) but are neither a foreign key to users, nor a listed non-FK reference, nor documented in
    ``NOT_USER_REFERENCES``. Must be empty: a new reference column has to be classified deliberately."""
    md = metadata or Base.metadata
    known = {(r.table, r.column) for r in user_references(md)}
    out = []
    for table in md.sorted_tables:
        for col in table.columns:
            low = col.name.lower()
            if (any(w in low for w in ("user", "owner", "actor")) and (table.name, col.name) not in known
                    and (table.name, col.name) not in NOT_USER_REFERENCES and not col.foreign_keys):
                out.append((table.name, col.name))
    return out


def _skip(retain_billing: bool, retain_requests: bool) -> set[str]:
    return (set(RETAINED_FOR_BILLING) if retain_billing else set()) | (set(RETAINED_FOR_PRIVACY_REQUEST) if retain_requests else set())


def sweep(session, user_id: int, *, retain_billing: bool = False, retain_requests: bool = False, metadata=None) -> dict[str, int]:
    """Apply the database's own foreign-key actions to every remaining reference to ``user_id`` (idempotent). Returns {"table.column": rows_changed} for changes only.
    ``preparation_runs`` is NOT swept here: its rows are removed only after the checkpoint purge succeeded (the index is what finds the data)."""
    md = metadata or Base.metadata
    skip = _skip(retain_billing, retain_requests)
    changed: dict[str, int] = {}
    for ref in user_references(md):
        if ref.table in skip or ref.table == "preparation_runs":
            continue
        table = md.tables[ref.table]
        col = table.c[ref.column]
        if ref.action == "erase":
            n = session.execute(delete(table).where(col == user_id)).rowcount or 0
        else:
            n = session.execute(update(table).where(col == user_id).values({ref.column: None})).rowcount or 0
        if n:
            changed[f"{ref.table}.{ref.column}"] = int(n)
    return changed


def residual_references(session, user_id: int, *, retain_billing: bool = False, retain_requests: bool = False, metadata=None) -> dict[str, int]:
    """Rows that still point at ``user_id`` after a deletion, per ``table.column`` (empty = complete). Counts only; never content."""
    md = metadata or Base.metadata
    skip = _skip(retain_billing, retain_requests)
    left: dict[str, int] = {}
    for ref in user_references(md):
        if ref.table in skip:
            continue
        table = md.tables[ref.table]
        n = session.scalar(select(func.count()).select_from(table).where(table.c[ref.column] == user_id)) or 0
        if n:
            left[f"{ref.table}.{ref.column}"] = int(n)
    return left


def residual_for_user(session_factory: Any, user_id: int, **kw) -> dict[str, int]:
    with session_factory() as s:
        return residual_references(s, user_id, **kw)
