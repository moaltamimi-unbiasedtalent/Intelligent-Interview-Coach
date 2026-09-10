#!/usr/bin/env python
"""Ask4Mo demo identity + persistence readiness (DEV / DEMO ONLY).

Ensures the local demo database is schema-current and a persisted demo user exists, then
smoke-tests user-scoped persistence (preparation memory + interview history) — the exact
paths that failed in the first golden-demo rehearsal because a stale local SQLite file was
never migrated (missing the `pinned` / `source_session_id` columns).

This is a dev/demo helper. It does NOT weaken production auth: production stays fail-closed
and its schema is owned by Alembic (`alembic upgrade head`). Identity is resolved exactly
as the API does (`InterviewRepository.get_or_create_user`) — no ownership checks are
bypassed and no anonymous sharing is introduced.

Usage:
    python scripts/ensure_demo_user.py
    DEMO_USER_SUBJECT=demo-reviewer python scripts/ensure_demo_user.py

Exit code 0 when the demo identity + persistence are READY; non-zero otherwise (with the
exact remediation — safe to use as a pre-demo gate alongside check_demo_knowledge.py).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import constants  # noqa: E402

DB_URL = os.environ.get("DATABASE_URL") or constants.DEFAULT_DATABASE_URL
SUBJECT = os.environ.get("DEMO_USER_SUBJECT") or "demo-reviewer"
_PROBE = "__demo_readiness_probe__"


def _db_file(url: str) -> str:
    return url.split("sqlite:///", 1)[1] if url.startswith("sqlite:///") else "<your database>"


def main() -> int:
    from src.application.memory_service import MemoryApplicationService
    from src.persistence import make_engine, make_session_factory
    from src.repository import InterviewRepository, MemoryRepository

    print("ASK4MO DEMO USER\n")
    print(f"subject:\n{SUBJECT}\n")

    sf = make_session_factory(make_engine(DB_URL))
    repo = InterviewRepository(sf)
    problems: list[str] = []

    # 1) Identity resolves to a persisted user (auto-provisioned, idempotent).
    try:
        uid = repo.get_or_create_user(
            subject=SUBJECT, provider="dev", display_name="Demo reviewer", email=None)
        print(f"database user:\nREADY (id={uid})\n")
    except Exception as exc:  # noqa: BLE001 - readiness must report, not crash
        print(f"database user:\nFAILED — {type(exc).__name__}: {str(exc)[:160]}\n")
        _print_not_ready()
        return 1

    # 2) Memory persistence (this is the path that 500s on a stale schema).
    mem = MemoryApplicationService(MemoryRepository(sf))
    try:
        item = mem.create(uid, category="recurring_gap", summary=_PROBE)
        mem.delete(uid, item.id)  # clean up the probe
        print("memory persistence:\nREADY\n")
    except Exception as exc:  # noqa: BLE001
        print(f"memory persistence:\nFAILED — {type(exc).__name__}\n")
        problems.append(f"memory: {str(exc)[:140]}")

    # 3) Interview-history read (user-scoped).
    try:
        repo.list_interviews(uid)
        print("history persistence:\nREADY\n")
    except Exception as exc:  # noqa: BLE001
        print(f"history persistence:\nFAILED — {type(exc).__name__}\n")
        problems.append(f"history: {str(exc)[:140]}")

    if problems:
        print("DEMO IDENTITY:\nNOT READY")
        for p in problems:
            print(f"  - {p}")
        _print_not_ready()
        return 1

    print("DEMO IDENTITY:\nREADY")
    print(f"\nFrontend: set NEXT_PUBLIC_DEV_USER_SUBJECT={SUBJECT} to send this identity, "
          "or leave it unset to use the anonymous dev user (both work once the schema is "
          "current).")
    return 0


def _print_not_ready() -> None:
    dbf = _db_file(DB_URL)
    print(
        "\nThe local demo database schema looks stale or behind head (a common cause is a "
        "leftover SQLite file created before a migration). Rebuild it from migrations "
        "(dev/demo data is disposable — this backs it up first):\n"
        f"  mv {dbf} {dbf}.bak 2>/dev/null || true\n"
        f"  DATABASE_URL={DB_URL} alembic upgrade head\n"
        "Then re-run this check. Production databases are migrated with `alembic upgrade "
        "head`, never recreated."
    )


if __name__ == "__main__":
    raise SystemExit(main())
