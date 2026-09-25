#!/usr/bin/env python
"""Deterministic workspace/sharing security evaluation (Capstone P6.5, §32).

Offline, no provider call, no cost — runs against a temporary SQLite DB with seeded users
and fake owner verifiers. Gates every sharing/membership security invariant:
membership_scope, cross_workspace_isolation, private_by_default, explicit_share_required,
share_owner_validation, share_workspace_validation, share_revocation,
deleted_resource_invalidation, invite_single_use, invite_expiry,
role_escalation_prevention, admin_not_data_superuser. Exits non-zero on any failure.
"""

from __future__ import annotations

import sys
import tempfile
import types
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.application.sharing_service import (  # noqa: E402
    SharingNotFoundError, SharingPermissionError, SharingService,
)
from src.application.workspace_service import (  # noqa: E402
    WorkspacePermissionError, WorkspaceService,
)
from src.persistence import (  # noqa: E402
    User, init_db, make_engine, make_session_factory, utcnow,
)
from src.workspace_repository import WorkspaceRepository  # noqa: E402


class _Accounts:
    def __init__(self, sf):
        self._sf = sf

    def get_account(self, uid):
        with self._sf() as s:
            u = s.get(User, uid)
            return types.SimpleNamespace(email=u.email) if u else None


class _Mail:
    def __init__(self):
        self.sent = []

    def send(self, m):
        self.sent.append(m)
        return True


class _ReportOwner:
    """alice(1) owns 'r1'; bob(2) owns 'r2'."""
    OWN = {("r1", 1), ("r2", 2)}

    def verify(self, rid, uid):
        return (rid, uid) in self.OWN

    def load(self, rid, uid):
        return {"report_id": rid} if (rid, uid) in self.OWN else None


def _harness():
    db = tempfile.mktemp(suffix=".db")
    eng = make_engine(f"sqlite:///{db}")
    init_db(eng)
    sf = make_session_factory(eng)
    with sf() as s:
        for i, email in enumerate(["alice@x.com", "bob@x.com", "mallory@x.com", "carol@x.com"], 1):
            s.add(User(subject=f"u{i}", provider="local", email=email, display_name=email))
        s.commit()
    repo = WorkspaceRepository(sf)
    mail = _Mail()
    ws = WorkspaceService(workspaces=repo, accounts=_Accounts(sf), audit=None, email=mail)
    ro = _ReportOwner()
    share = SharingService(workspaces=repo, audit=None,
                          owner_verifiers={"interview_report": ro.verify},
                          owner_loaders={"interview_report": ro.load})
    return repo, ws, share, mail


def _accept(ws, mail, uid):
    raw = mail.sent[-1].body.split("token=")[1].split()[0]
    return raw, ws.accept_invitation(user_id=uid, token=raw)


def evaluate() -> dict:
    m: dict = {}
    repo, ws, share, mail = _harness()

    # alice creates WS-A, invites+adds bob.
    a = ws.create_workspace(user_id=1, name="A")["id"]
    ws.invite(user_id=1, workspace_id=a, email="bob@x.com")
    raw_bob, _ = _accept(ws, mail, 2)

    # membership_scope — bob is a member, mallory is not.
    m["membership_scope"] = 1 if (repo.member_role(a, 2) and repo.member_role(a, 3) is None) else 0

    # role_escalation_prevention — bob (member) cannot invite/remove/transfer.
    esc = 0
    for call in (lambda: ws.invite(user_id=2, workspace_id=a, email="carol@x.com"),
                 lambda: ws.remove_member(user_id=2, workspace_id=a, target_user_id=1),
                 lambda: ws.transfer_ownership(user_id=2, workspace_id=a, new_owner_user_id=2)):
        try:
            call()
        except WorkspacePermissionError:
            esc += 1
        except Exception:  # noqa: BLE001
            pass
    m["role_escalation_prevention"] = 1 if esc == 3 else 0

    # invite_single_use — replay of bob's token fails.
    try:
        ws.accept_invitation(user_id=2, token=raw_bob)
        m["invite_single_use"] = 0
    except Exception:  # noqa: BLE001
        m["invite_single_use"] = 1

    # foreign invite acceptance — mallory cannot accept an invite issued to carol.
    ws.invite(user_id=1, workspace_id=a, email="carol@x.com")
    raw_carol = mail.sent[-1].body.split("token=")[1].split()[0]
    try:
        ws.accept_invitation(user_id=3, token=raw_carol)
        m["foreign_invite_rejected"] = 0
    except WorkspacePermissionError:
        m["foreign_invite_rejected"] = 1

    # invite_expiry — an expired token cannot be accepted.
    expired_id = repo.create_invitation(
        workspace_id=a, inviter_user_id=1, email="carol@x.com",
        token_hash=__import__("hashlib").sha256(b"expiredraw").hexdigest(),
        role="workspace_member", expires_at=utcnow() - timedelta(hours=1))
    try:
        ws.accept_invitation(user_id=4, token="expiredraw")
        m["invite_expiry"] = 0
    except Exception:  # noqa: BLE001
        m["invite_expiry"] = 1
    _ = expired_id

    # --- sharing ---
    # explicit_share_required + private_by_default — with no share, bob cannot view r1.
    m["private_by_default"] = 1 if share.can_view(user_id=2, resource_type="interview_report", resource_id="r1") is None else 0
    m["explicit_share_required"] = m["private_by_default"]

    # share_owner_validation — alice cannot share bob's r2.
    try:
        share.share(user_id=1, workspace_id=a, resource_type="interview_report", resource_id="r2")
        m["share_owner_validation"] = 0
    except SharingPermissionError:
        m["share_owner_validation"] = 1

    # share_workspace_validation — alice cannot share into a workspace she's not in.
    other = ws.create_workspace(user_id=4, name="Carol WS")["id"]  # carol's workspace
    try:
        share.share(user_id=1, workspace_id=other, resource_type="interview_report", resource_id="r1")
        m["share_workspace_validation"] = 0
    except SharingPermissionError:
        m["share_workspace_validation"] = 1

    # valid share → bob can view; mallory (non-member) cannot.
    grant = share.share(user_id=1, workspace_id=a, resource_type="interview_report", resource_id="r1")
    can_bob = share.can_view(user_id=2, resource_type="interview_report", resource_id="r1") == 1
    can_mallory = share.can_view(user_id=3, resource_type="interview_report", resource_id="r1")
    m["cross_workspace_isolation"] = 1 if (can_bob and can_mallory is None) else 0

    # share_revocation — after revoke, bob loses access immediately.
    share.revoke(user_id=1, share_id=grant["share_id"])
    try:
        share.resolve_shared_resource(user_id=2, resource_type="interview_report", resource_id="r1")
        m["share_revocation"] = 0
    except SharingNotFoundError:
        m["share_revocation"] = 1

    # deleted_resource_invalidation — re-share, then delete source → grants invalidated.
    share.share(user_id=1, workspace_id=a, resource_type="interview_report", resource_id="r1")
    share.invalidate_on_delete(owner_user_id=1, resource_type="interview_report", resource_id="r1")
    m["deleted_resource_invalidation"] = 1 if share.can_view(
        user_id=2, resource_type="interview_report", resource_id="r1") is None else 0

    # admin_not_data_superuser — the admin account-metadata projection contains NO
    # candidate-private content keys.
    from src.auth_repository import AccountRepository
    accounts = AccountRepository(repo.session_factory)
    forbidden = {"comment", "answers", "documents", "memory", "cv", "report", "story", "password"}
    rows = accounts.list_accounts(limit=10)
    leaked = any(k in forbidden for row in rows for k in row)
    m["admin_not_data_superuser"] = 0 if leaked else 1

    return m


GATES = {
    "membership_scope": 1, "cross_workspace_isolation": 1, "private_by_default": 1,
    "explicit_share_required": 1, "share_owner_validation": 1, "share_workspace_validation": 1,
    "share_revocation": 1, "deleted_resource_invalidation": 1, "invite_single_use": 1,
    "invite_expiry": 1, "role_escalation_prevention": 1, "admin_not_data_superuser": 1,
    "foreign_invite_rejected": 1,
}


def gate_failures(m: dict) -> list[str]:
    return [f"{k} = {m.get(k)} (want {v})" for k, v in GATES.items() if m.get(k) != v]


def main() -> int:
    m = evaluate()
    print("WORKSPACE / SHARING SECURITY EVALUATION (Capstone P6.5, offline, no paid calls)")
    print("=" * 72)
    for k in GATES:
        print(f"  {k:<32} {m.get(k)}  (gate == {GATES[k]})")
    print("=" * 72)
    fails = gate_failures(m)
    if fails:
        print("\nGATE STATUS: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("\nGATE STATUS: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
