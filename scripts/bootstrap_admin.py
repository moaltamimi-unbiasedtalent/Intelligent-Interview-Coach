#!/usr/bin/env python
"""Promote an account to PLATFORM_ADMIN (Capstone P1/E1 — controlled bootstrap).

The platform-admin role is NEVER self-service (no API grants it). This script is the
deterministic, operator-run mechanism for a controlled deployment: it promotes an
existing account by email and records an audit event for the role change.

Safety:
* Operates only on an EXISTING account (never creates one, never sets a password).
* Requires an explicit ``--yes`` to make the change (dry-run by default).
* Records an ``account.platform_role_change`` audit event.
* Prints no secret; the target is identified by email only.

Usage:
    python scripts/bootstrap_admin.py --email owner@example.com            # dry-run
    python scripts/bootstrap_admin.py --email owner@example.com --yes      # apply
    DATABASE_URL=... python scripts/bootstrap_admin.py --email ... --yes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import constants  # noqa: E402
from src.persistence import PLATFORM_ROLE_ADMIN  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote an account to platform_admin.")
    parser.add_argument("--email", required=True, help="Email of the existing account to promote.")
    parser.add_argument("--yes", action="store_true", help="Apply the change (otherwise dry-run).")
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL.")
    args = parser.parse_args(argv)

    import os

    from src.auth_repository import AccountRepository, AuditRepository
    from src.persistence import make_engine, make_session_factory

    db_url = args.database_url or os.environ.get("DATABASE_URL") or constants.DEFAULT_DATABASE_URL
    sf = make_session_factory(make_engine(db_url))
    accounts = AccountRepository(sf)

    account = accounts.find_by_email(args.email)
    if account is None:
        print(f"No account found for {args.email}. Create/verify the account first.")
        return 1

    if account.platform_role == PLATFORM_ROLE_ADMIN:
        print(f"{args.email} (user_id={account.user_id}) is already platform_admin.")
        return 0

    if not args.yes:
        print(
            f"DRY-RUN: would promote {args.email} (user_id={account.user_id}) "
            f"from '{account.platform_role}' to '{PLATFORM_ROLE_ADMIN}'.\n"
            "Re-run with --yes to apply."
        )
        return 0

    accounts.set_platform_role(account.user_id, PLATFORM_ROLE_ADMIN)
    AuditRepository(sf).record(
        event_type="account.platform_role_change",
        result="success",
        actor_user_id=account.user_id,
        target_type="user",
        target_id=str(account.user_id),
        context={"from": account.platform_role, "to": PLATFORM_ROLE_ADMIN, "via": "bootstrap_admin"},
    )
    print(f"Promoted {args.email} (user_id={account.user_id}) to {PLATFORM_ROLE_ADMIN}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
