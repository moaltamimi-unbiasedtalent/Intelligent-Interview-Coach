"""Generic world builder for the 05E erasure tests.

Builds, for any set of user-referencing columns, one row for a VICTIM and one for a BYSTANDER, using only the schema (column types, defaults, unique and CHECK
constraints) so a table added later is exercised without writing a fixture by hand. SQLite does not enforce foreign keys, so parent ids may dangle; what is
asserted is what the deletion does with rows that carry the victim's user id.
"""

from __future__ import annotations

import itertools
import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, JSON, LargeBinary, Numeric, String, Text, insert

from src.persistence import Base

_COUNTER = itertools.count(1000)
_IN = re.compile(r"(\w+)\s+IN\s*\(([^)]*)\)", re.IGNORECASE)


def _allowed_values(table) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for c in table.constraints:
        text = getattr(c, "sqltext", None)
        if text is None:
            continue
        for col, body in _IN.findall(str(text)):
            vals = [v.strip().strip("'") for v in body.split(",") if v.strip()]
            if vals:
                out.setdefault(col, vals)
    return out


_CYCLE: dict[tuple[str, str], int] = {}


def _value_for(col, allowed: dict[str, list[str]]):
    n = next(_COUNTER)
    if col.name in allowed:
        key = (col.table.name, col.name)                                   # cycle through the allowed values so a UNIQUE categorical column still gets distinct rows
        i = _CYCLE.get(key, 0)
        _CYCLE[key] = i + 1
        return allowed[col.name][i % len(allowed[col.name])]
    if any(w in col.name for w in ("hash", "checksum", "sha")) and isinstance(col.type, String) and (getattr(col.type, "length", None) or 0) >= 64:
        return f"{n:064x}"
    t = col.type
    if isinstance(t, Boolean):
        return False
    if isinstance(t, Integer):
        return n
    if isinstance(t, (Float, Numeric)):
        return 1.0
    if isinstance(t, DateTime):
        return datetime.now(timezone.utc) + timedelta(days=1, seconds=n % 1000)
    if isinstance(t, Date):
        return date.today()
    if isinstance(t, JSON):
        return {}
    if isinstance(t, LargeBinary):
        return b"x"
    if isinstance(t, (String, Text)):
        length = getattr(t, "length", None) or 64
        return f"v{n}"[:length]
    return n


def make_row(connection, table, **overrides) -> int | None:
    """Insert one row of ``table`` with every required column filled from the schema; ``overrides`` win. Returns the primary key when it is an integer."""
    allowed = _allowed_values(table)
    values = dict(overrides)
    for col in table.columns:
        if col.name in values:
            continue
        if col.primary_key and isinstance(col.type, Integer):
            continue                                                       # autoincrement
        if col.nullable or col.default is not None or col.server_default is not None:
            continue
        values[col.name] = _value_for(col, allowed)
    res = connection.execute(insert(table).values(**values))
    pk = res.inserted_primary_key
    return pk[0] if pk and isinstance(pk[0], int) else None


# Per-table state overrides so the world is a valid "settled" account (terminal billing states: an unresolved provider subscription would, by design, refuse the closure).
STATE_OVERRIDES = {
    "billing_provider_links": {"provider_state": "canceled"},
    "billing_checkout_sessions": {"status": "expired"},
}


def build_world(connection, victim_id: int, bystander_id: int, references) -> dict[str, dict[str, int]]:
    """For each reference column insert a victim row and a bystander row. Returns {"table.column": {"victim": n, "bystander": n}} counts afterwards."""
    for ref in references:
        table = Base.metadata.tables[ref.table]
        extra = STATE_OVERRIDES.get(ref.table, {})
        for owner in (victim_id, bystander_id):
            make_row(connection, table, **{ref.column: owner}, **extra)
    return {}
