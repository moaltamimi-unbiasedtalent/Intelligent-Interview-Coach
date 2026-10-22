#!/usr/bin/env python
"""Issue a private-beta registration invitation from the command line (package 04E, operator bootstrap).

Why this exists: in staging and production registration needs an invitation, and the Admin console needs an administrator, who needs an account. This is the
deterministic, operator-run way to mint the FIRST invitation (for the owner), after which ``scripts/bootstrap_admin.py`` promotes that account. Day to day, use the
Admin invitations API/page instead.

Safety:
* Dry-run by default; ``--yes`` is required to write anything.
* The plaintext code and link are printed to stdout ONCE and never stored, logged or audited (the database keeps only the SHA-256 hash).
* No email is sent and no provider is called; hand the link to the invitee yourself.
* Records an ``admin.invitation_issued`` audit event with no actor (an operator action) and metadata only.

Usage:
    python scripts/issue_invitation.py                                   # dry-run
    python scripts/issue_invitation.py --email owner@example.com --yes   # issue, bound to that address
    DATABASE_URL=... APP_BASE_URL=https://staging.example.com python scripts/issue_invitation.py --yes
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Issue a single-use private-beta registration invitation.")
    parser.add_argument("--email", default=None, help="Optional: bind the invitation to this address (only it can redeem).")
    parser.add_argument("--expires-days", type=int, default=None, help="Lifetime in days (default 14, maximum 30).")
    parser.add_argument("--yes", action="store_true", help="Issue it (otherwise dry-run).")
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL.")
    args = parser.parse_args(argv)

    from src import constants
    from src.application import admin_audit as A
    from src.application.auth_service import AuthConfig, _valid_email
    from src.application.errors import ValidationError
    from src.invitations import policy
    from src.invitations import repository as R
    from src.persistence import make_engine, make_session_factory

    days = args.expires_days if args.expires_days is not None else policy.DEFAULT_TTL_DAYS
    if not 1 <= days <= policy.MAX_TTL_DAYS:
        print(f"--expires-days must be between 1 and {policy.MAX_TTL_DAYS}.")
        return 2
    email = None
    if args.email:
        try:
            email = _valid_email(args.email)
        except ValidationError:
            print("--email is not a valid address.")
            return 2

    if not args.yes:
        print(f"DRY-RUN: would issue one invitation valid for {days} day(s){' bound to ' + R.mask_email(email) if email else ''}. Re-run with --yes to issue it.")
        return 0

    db_url = args.database_url or os.environ.get("DATABASE_URL") or constants.DEFAULT_DATABASE_URL
    sf = make_session_factory(make_engine(db_url))
    code = R.new_code()
    audit = A.build_audit(event_type=A.ADMIN_INVITATION_ISSUED, actor_user_id=None, request_id=None, target_type="invitation", origin="cli")
    try:
        view = R.InvitationRepository(sf).issue(code_hash=R.hash_code(code), ttl_days=days, email=email, issued_by_user_id=None, audit=audit)
    except R.InvitationLimit as exc:
        print(str(exc))
        return 1
    base = AuthConfig.from_env().app_base_url
    print(f"Invitation {view.id} issued (expires {view.expires_at.isoformat()}). The code is shown ONCE and cannot be recovered:")
    print(f"  code: {code}")
    print(f"  link: {base}/register#invitation={code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
