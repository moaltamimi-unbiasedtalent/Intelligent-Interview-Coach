#!/usr/bin/env python
"""Deterministic workspace/sharing security evaluation (Capstone P6.5, §32).

Offline, no provider call, no cost — runs against a temporary SQLite DB with seeded users
and fake owner verifiers. Gates every sharing/membership security invariant:
membership_scope, cross_workspace_isolation, private_by_default, explicit_share_required,
share_owner_validation, share_workspace_validation, share_revocation,
deleted_resource_invalidation, invite_single_use, invite_expiry,
role_escalation_prevention, admin_not_data_superuser.

04B extends (never weakens) the gate with: verified_email_required, atomic_accept_single_winner,
revoked_invitation_unusable, consent_required, archived_share_refused, archive_revokes_and_restore_does_not_revive,
admin_role_semantics, last_owner_protected, removal_revokes_member_shares, workspace_delete_revokes_all,
removed_member_loses_read, owner_departure_cuts_shares, admin_enrolment_guard, member_list_hides_addresses,
claim_is_conditional.

The 04B completion (two-step ownership transfer; OD-WS-TRANSFER is a provisional recommendation, not an approval) adds: transfer_two_step_no_early_move,
transfer_unverified_recipient_refused, transfer_replay_and_expiry_refused, transfer_atomic_single_winner, transfer_party_departure_cancels,
transfer_audit_metadata_only.
Exits non-zero on any failure.
"""

from __future__ import annotations

import sys
import tempfile
import threading
import types
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# TEST ISOLATION (W10.14): importing the pytest isolation module redirects DATABASE_URL/Chroma to a temp directory, disables .env and makes any non-temp engine FAIL FAST,
# so this evaluator can never write a developer store.
import tests.conftest  # noqa: E402,F401

from src.application.errors import ConflictError, ValidationError  # noqa: E402
from src.application.sharing_service import (  # noqa: E402
    SharingNotFoundError, SharingPermissionError, SharingService,
)
from src.application.workspace_service import (  # noqa: E402
    WorkspaceNotFoundError, WorkspacePermissionError, WorkspaceService,
)
from src.persistence import (  # noqa: E402
    User, init_db, make_engine, make_session_factory, utcnow,
)
from src.application.ownership_transfer_service import OwnershipTransferService  # noqa: E402
from src.ownership_transfer_repository import OwnershipTransferRepository, hash_token, transfer_email_hash  # noqa: E402
from src.workspace_repository import WorkspaceRepository  # noqa: E402


class _Accounts:
    def __init__(self, sf):
        self._sf = sf

    def get_account(self, uid):
        with self._sf() as s:
            u = s.get(User, uid)
            return types.SimpleNamespace(email=u.email, email_verified=bool(u.email_verified),
                                         interface_locale="en") if u else None

    def find_by_email(self, email):
        with self._sf() as s:
            from sqlalchemy import select
            u = s.scalar(select(User).where(User.email == email))
            return types.SimpleNamespace(interface_locale="en") if u else None


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
        # users 1-4 have PROVEN addresses; user 5 (eve) registered the address an invitation will be sent to but never verified it.
        for i, email in enumerate(["alice@x.com", "bob@x.com", "mallory@x.com", "carol@x.com", "eve@x.com", "dave@x.com"], 1):
            s.add(User(subject=f"u{i}", provider="local", email=email, display_name=email,
                       email_verified=(i != 5)))
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
    xf = OwnershipTransferService(workspaces=repo, transfers=OwnershipTransferRepository(repo.session_factory), accounts=ws._accounts, email=mail)  # noqa: SLF001

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
                 lambda: xf.propose(user_id=2, workspace_id=a, new_owner_user_id=2, confirm_name="A")):
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
        share.share(user_id=1, workspace_id=a, resource_type="interview_report", resource_id="r2", consent=True)
        m["share_owner_validation"] = 0
    except SharingPermissionError:
        m["share_owner_validation"] = 1

    # share_workspace_validation — alice cannot share into a workspace she's not in.
    other = ws.create_workspace(user_id=4, name="Carol WS")["id"]  # carol's workspace
    try:
        share.share(user_id=1, workspace_id=other, resource_type="interview_report", resource_id="r1", consent=True)
        m["share_workspace_validation"] = 0
    except SharingPermissionError:
        m["share_workspace_validation"] = 1

    # valid share → bob can view; mallory (non-member) cannot.
    grant = share.share(user_id=1, workspace_id=a, resource_type="interview_report", resource_id="r1", consent=True)
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
    share.share(user_id=1, workspace_id=a, resource_type="interview_report", resource_id="r1", consent=True)
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

    # operational_allowlist_truthful — the operational shareable set is exactly the wired,
    # durable, owner-scoped resource types (interview report + story). A type advertised but
    # not consumable (e.g. preparation_summary) must NOT be in the operational allowlist.
    from src.persistence import (
        SHARE_RESOURCE_PREP_SUMMARY, SHARE_RESOURCE_REPORT, SHARE_RESOURCE_STORY,
        SHAREABLE_RESOURCE_TYPES,
    )
    m["operational_allowlist_truthful"] = 1 if (
        set(SHAREABLE_RESOURCE_TYPES) == {SHARE_RESOURCE_REPORT, SHARE_RESOURCE_STORY}
        and SHARE_RESOURCE_PREP_SUMMARY not in SHAREABLE_RESOURCE_TYPES
    ) else 0


    m.update(_evaluate_04b())
    return m


def _raises(fn, *exc) -> bool:
    try:
        fn()
    except exc:
        return True
    except Exception:  # noqa: BLE001 - a different error is not the guarded outcome
        return False
    return False


def _evaluate_04b() -> dict:
    """04B gates: lifecycle, roles, invitations, consent, immediate revocation, deletion, isolation, admin metadata only."""
    m: dict = {}
    repo, ws, share, mail = _harness()
    xf = OwnershipTransferService(workspaces=repo, transfers=OwnershipTransferRepository(repo.session_factory), accounts=ws._accounts, email=mail)  # noqa: SLF001

    def token():
        return mail.sent[-1].body.split("token=")[1].split()[0]

    w = ws.create_workspace(user_id=1, name="Team")["id"]        # alice owns; bob member; carol admin
    ws.invite(user_id=1, workspace_id=w, email="bob@x.com")
    ws.accept_invitation(user_id=2, token=token())
    ws.invite(user_id=1, workspace_id=w, email="carol@x.com", role="workspace_admin")
    ws.accept_invitation(user_id=4, token=token())

    # verified_email_required: eve holds an UNVERIFIED account on eve@x.com; an invitation to that address cannot be answered
    # until the address is proven, the refusal does not consume it, and she cannot even list it.
    ws.invite(user_id=1, workspace_id=w, email="eve@x.com")
    tok_eve = token()
    refused = _raises(lambda: ws.accept_invitation(user_id=5, token=tok_eve), WorkspacePermissionError)
    pending_after = any(i["email"] == "eve@x.com" and i["status"] == "pending" for i in repo.list_invitations_for_workspace(w))
    hidden = ws.list_my_workspaces(user_id=5, email="eve@x.com", email_verified=False)["invited"] == []
    m["verified_email_required"] = 1 if (refused and pending_after and hidden and repo.member_role(w, 5) is None) else 0

    # atomic_accept_single_winner: many concurrent accepts of ONE invitation, exactly one wins and one membership row exists.
    ws.invite(user_id=1, workspace_id=w, email="dave@x.com")
    inv = [i for i in repo.list_invitations_for_workspace(w) if i["email"] == "dave@x.com"][0]
    results: list[str] = []
    gate = threading.Barrier(6)

    def _go():
        gate.wait()
        try:
            out, _ = repo.decide_invitation(invitation_id=inv["id"], user_id=6, email="dave@x.com", accept=True)
        except Exception:  # noqa: BLE001 - a lost race on a locked SQLite file is not a second winner
            out = "error"
        results.append(out)

    threads = [threading.Thread(target=_go) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    from sqlalchemy import func, select
    from src.persistence import WorkspaceMembership
    with repo.session_factory() as sess:
        rows = sess.scalar(select(func.count()).select_from(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == w, WorkspaceMembership.user_id == 6)) or 0
    m["atomic_accept_single_winner"] = 1 if (results.count("ok") == 1 and rows == 1) else 0

    # revoked_invitation_unusable: a revoked invitation can be neither accepted nor declined.
    ws.invite(user_id=1, workspace_id=w, email="mallory@x.com")
    tok_m = token()
    inv_m = [i for i in repo.list_invitations_for_workspace(w) if i["email"] == "mallory@x.com"][0]
    ws.revoke_invitation(user_id=1, workspace_id=w, invitation_id=inv_m["id"])
    m["revoked_invitation_unusable"] = 1 if (
        _raises(lambda: ws.accept_invitation(user_id=3, token=tok_m), ConflictError)
        and _raises(lambda: ws.decline_invitation(user_id=3, token=tok_m), ConflictError)
        and repo.member_role(w, 3) is None) else 0

    # claim_is_conditional: a revoke landing between the read of an invitation and the claim wins (the claim is a conditional UPDATE,
    # so it cannot accept a revoked invitation or create a membership). Deterministic interleaving on a second connection.
    import re
    from sqlalchemy import event, text
    ws.invite(user_id=1, workspace_id=w, email="mallory@x.com")
    inv_c = [i for i in repo.list_invitations_for_workspace(w) if i["email"] == "mallory@x.com" and i["status"] == "pending"][0]
    engine = repo.session_factory.kw["bind"]
    hit: list[int] = []

    def _interleave(conn, cursor, statement, parameters, context, executemany):
        if not hit and statement.lstrip().upper().startswith("SELECT") and re.search(r"FROM workspaces\s+WHERE", statement):
            hit.append(1)
            with engine.begin() as other:
                other.execute(text("UPDATE workspace_invitations SET status = 'revoked' WHERE id = :i"), {"i": inv_c["id"]})

    event.listen(engine, "before_cursor_execute", _interleave)
    try:
        outcome, _ = repo.decide_invitation(invitation_id=inv_c["id"], user_id=3, email="mallory@x.com", accept=True)
    finally:
        event.remove(engine, "before_cursor_execute", _interleave)
    m["claim_is_conditional"] = 1 if (hit and outcome == "used" and repo.member_role(w, 3) is None) else 0

    # admin_role_semantics: carol (admin) manages plain members only.
    ok_invite = not _raises(lambda: ws.invite(user_id=4, workspace_id=w, email="mallory@x.com"), Exception)
    denied = [
        _raises(lambda: ws.invite(user_id=4, workspace_id=w, email="x@y.com", role="workspace_admin"), WorkspacePermissionError),
        _raises(lambda: ws.remove_member(user_id=4, workspace_id=w, target_user_id=1), ConflictError, WorkspacePermissionError),
        _raises(lambda: xf.propose(user_id=4, workspace_id=w, new_owner_user_id=4, confirm_name="Team"), WorkspacePermissionError),
        _raises(lambda: ws.archive_workspace(user_id=4, workspace_id=w), WorkspacePermissionError),
        _raises(lambda: ws.delete_workspace(user_id=4, workspace_id=w, confirm_name="Team"), WorkspacePermissionError),
        _raises(lambda: ws.change_member_role(user_id=4, workspace_id=w, target_user_id=2, role="workspace_admin"), WorkspacePermissionError),
    ]
    m["admin_role_semantics"] = 1 if (ok_invite and all(denied)) else 0

    # last_owner_protected: the sole owner can neither leave nor be removed; ownership moves only by transfer.
    m["last_owner_protected"] = 1 if (
        _raises(lambda: ws.leave(user_id=1, workspace_id=w), ConflictError)
        and _raises(lambda: ws.remove_member(user_id=4, workspace_id=w, target_user_id=1), ConflictError, WorkspacePermissionError)
        and repo.count_active_owners(w) == 1) else 0

    # consent_required: a share without the explicit acknowledgement creates nothing.
    before = len(repo.list_shares_by_owner(1))
    no_consent = _raises(lambda: share.share(user_id=1, workspace_id=w, resource_type="interview_report", resource_id="r1"), ValidationError)
    m["consent_required"] = 1 if (no_consent and len(repo.list_shares_by_owner(1)) == before) else 0

    # removal_revokes_member_shares and removed_member_loses_read: bob shares r2, then is removed.
    share.share(user_id=2, workspace_id=w, resource_type="interview_report", resource_id="r2", consent=True)
    readable = share.can_view(user_id=1, resource_type="interview_report", resource_id="r2") == 2
    ws.remove_member(user_id=1, workspace_id=w, target_user_id=2)
    m["removal_revokes_member_shares"] = 1 if (readable and not repo.list_shares_by_owner(2)) else 0
    share.share(user_id=1, workspace_id=w, resource_type="interview_report", resource_id="r1", consent=True)
    m["removed_member_loses_read"] = 1 if share.can_view(user_id=2, resource_type="interview_report", resource_id="r1") is None else 0

    # member_list_hides_addresses: a plain member sees labels, never another member's address, nor pending invitations.
    ws.invite(user_id=1, workspace_id=w, email="bob@x.com")
    ws.accept_invitation(user_id=2, token=token())
    detail = ws.get_workspace_detail(user_id=2, workspace_id=w)
    others = [x for x in detail["members"] if not x["is_me"]]
    m["member_list_hides_addresses"] = 1 if (others and all("email" not in x for x in others)
                                            and "pending_invitations" not in detail) else 0

    # owner_departure_cuts_shares: when the sharer stops being a member, readers lose access at once.
    can_before = share.can_view(user_id=2, resource_type="interview_report", resource_id="r1") == 1
    repo.set_membership_status(workspace_id=w, user_id=1, status="removed")      # stands in for any path that ends the sharer's membership
    cut = share.can_view(user_id=2, resource_type="interview_report", resource_id="r1") is None
    repo.set_membership_status(workspace_id=w, user_id=1, status="active")
    m["owner_departure_cuts_shares"] = 1 if (can_before and cut) else 0

    # archive: shares revoked atomically, new shares refused, restore never revives a revoked grant.
    still = share.can_view(user_id=2, resource_type="interview_report", resource_id="r1") == 1
    ws.archive_workspace(user_id=1, workspace_id=w)
    gone = share.can_view(user_id=2, resource_type="interview_report", resource_id="r1") is None
    m["archived_share_refused"] = 1 if _raises(
        lambda: share.share(user_id=1, workspace_id=w, resource_type="interview_report", resource_id="r1", consent=True),
        ConflictError) else 0
    ws.restore_workspace(user_id=1, workspace_id=w)
    m["archive_revokes_and_restore_does_not_revive"] = 1 if (
        still and gone and share.can_view(user_id=2, resource_type="interview_report", resource_id="r1") is None) else 0

    # workspace_delete_revokes_all: typed confirmation required; every grant, membership and invitation row disappears.
    share.share(user_id=1, workspace_id=w, resource_type="interview_report", resource_id="r1", consent=True)
    wrong = _raises(lambda: ws.delete_workspace(user_id=1, workspace_id=w, confirm_name="nope"), ValidationError)
    ws.delete_workspace(user_id=1, workspace_id=w, confirm_name="Team")
    from src.persistence import ShareGrant, WorkspaceInvitation
    with repo.session_factory() as sess:
        leftovers = sum(int(sess.scalar(select(func.count()).select_from(model).where(model.workspace_id == w)) or 0)
                        for model in (ShareGrant, WorkspaceMembership, WorkspaceInvitation))
    m["workspace_delete_revokes_all"] = 1 if (
        wrong and leftovers == 0 and share.can_view(user_id=2, resource_type="interview_report", resource_id="r1") is None
        and _raises(lambda: ws.get_workspace_detail(user_id=2, workspace_id=w), WorkspaceNotFoundError)) else 0

    # admin_enrolment_guard: an operator cannot enrol a platform-staff account (that would expose shared content).
    from src.admin_repository import AdminUserRepository
    from src.persistence import PLATFORM_ROLE_ADMIN
    w2 = ws.create_workspace(user_id=1, name="Other")["id"]
    with repo.session_factory() as sess:
        sess.get(User, 3).platform_role = PLATFORM_ROLE_ADMIN
        sess.commit()
    m["admin_enrolment_guard"] = 1 if (
        _raises(lambda: AdminUserRepository(repo.session_factory).add_member(w2, 3, "workspace_member"), ConflictError)
        and repo.member_role(w2, 3) is None) else 0
        # ---- 04B completion: two-step ownership transfer ------------------------------------------------------------------
    import json
    import re as _re
    from sqlalchemy import select as _select
    from src.persistence import AuditEvent, WorkspaceOwnershipTransfer as _T

    def _team(owner: int, name: str, members: tuple[int, ...]) -> int:
        wid = ws.create_workspace(user_id=owner, name=name)["id"]
        for uid in members:
            repo.upsert_membership(workspace_id=wid, user_id=uid, role="workspace_member")
        return wid

    def _tok() -> str:
        return mail.sent[-1].body.split("token=")[1].split()[0]

    t1 = _team(4, "T1", (2, 6))                                     # carol owns; bob(2) and dave(6) are verified members
    xf.propose(user_id=4, workspace_id=t1, new_owner_user_id=2, confirm_name="T1", former_owner_role="workspace_admin")
    raw = _tok()
    early = repo.member_role(t1, 4) == "workspace_owner" and repo.member_role(t1, 2) == "workspace_member"
    wrong_person = _raises(lambda: xf.accept(user_id=6, token=raw), WorkspaceNotFoundError)            # a token bound to bob is useless to dave
    xf.accept(user_id=2, token=raw)
    swapped = repo.member_role(t1, 2) == "workspace_owner" and repo.member_role(t1, 4) == "workspace_admin" and repo.count_active_owners(t1) == 1
    m["transfer_two_step_no_early_move"] = 1 if (early and wrong_person and swapped) else 0
    m["transfer_replay_and_expiry_refused"] = 0
    replay = _raises(lambda: xf.accept(user_id=2, token=raw), ConflictError)

    t2 = _team(1, "T2", (5, 6))                                     # eve(5) never verified her address; dave(6) is verified
    unverified = _raises(lambda: xf.propose(user_id=1, workspace_id=t2, new_owner_user_id=5, confirm_name="T2"), ValidationError)
    xf.propose(user_id=1, workspace_id=t2, new_owner_user_id=6, confirm_name="T2")
    raw2 = _tok()
    with repo.session_factory() as sess:                            # the deadline passes: the server refuses and marks it expired
        row = sess.scalar(_select(_T).where(_T.workspace_id == t2))
        row.expires_at = utcnow() - timedelta(minutes=1)
        sess.commit()
    expired = _raises(lambda: xf.accept(user_id=6, token=raw2), ConflictError) and repo.member_role(t2, 1) == "workspace_owner"
    m["transfer_unverified_recipient_refused"] = 1 if unverified else 0
    m["transfer_replay_and_expiry_refused"] = 1 if (replay and expired) else 0

    t3 = _team(1, "T3", (6,))
    xf.propose(user_id=1, workspace_id=t3, new_owner_user_id=6, confirm_name="T3")
    th = hash_token(_tok())
    trepo = OwnershipTransferRepository(repo.session_factory)
    wins: list[str] = []
    gate = threading.Barrier(6)

    def _go(kind: str) -> None:
        gate.wait()
        try:
            if kind == "accept":
                wins.append("accept" if trepo.accept(token_hash=th, user_id=6, email_hash=transfer_email_hash("dave@x.com"))[0] == "ok" else "-")
            else:
                wins.append("cancel" if trepo.cancel(workspace_id=t3, user_id=1)[0] == "ok" else "-")
        except Exception:  # noqa: BLE001 - a lost race on a locked SQLite file is not a second winner
            wins.append("-")

    threads = [threading.Thread(target=_go, args=(k,)) for k in ("accept", "cancel", "accept", "cancel", "accept", "cancel")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    with repo.session_factory() as sess:
        final = sess.scalar(_select(_T.status).where(_T.workspace_id == t3))
    m["transfer_atomic_single_winner"] = 1 if (len([x for x in wins if x != "-"]) == 1 and repo.count_active_owners(t3) == 1
                                               and ((final == "accepted") == (repo.member_role(t3, 6) == "workspace_owner"))) else 0

    t4 = _team(1, "T4", (6,))
    xf.propose(user_id=1, workspace_id=t4, new_owner_user_id=6, confirm_name="T4")
    ws.leave(user_id=6, workspace_id=t4)
    m["transfer_party_departure_cancels"] = 1 if (trepo.pending_for_workspace(t4) is None and repo.member_role(t4, 1) == "workspace_owner") else 0

    with repo.session_factory() as sess:
        rows = sess.scalars(_select(AuditEvent).where(AuditEvent.event_type.like("workspace.transfer_%"))).all()
        blob = json.dumps([(e.event_type, e.context, e.target_id, e.target_type) for e in rows], default=str)
    allowed = {"transfer_id", "actor_role", "former_owner_role", "outcome", "reason"}
    m["transfer_audit_metadata_only"] = 1 if (
        rows and all(set(e.context or {}) <= allowed for e in rows) and "@" not in blob and "x.com" not in blob
        and raw not in blob and raw2 not in blob and "T1" not in blob) else 0
    return m


GATES = {
    "membership_scope": 1, "cross_workspace_isolation": 1, "private_by_default": 1,
    "explicit_share_required": 1, "share_owner_validation": 1, "share_workspace_validation": 1,
    "share_revocation": 1, "deleted_resource_invalidation": 1, "invite_single_use": 1,
    "invite_expiry": 1, "role_escalation_prevention": 1, "admin_not_data_superuser": 1,
    "foreign_invite_rejected": 1, "operational_allowlist_truthful": 1,
    # 04B
    "verified_email_required": 1, "atomic_accept_single_winner": 1, "revoked_invitation_unusable": 1,
    "consent_required": 1, "archived_share_refused": 1, "archive_revokes_and_restore_does_not_revive": 1,
    "admin_role_semantics": 1, "last_owner_protected": 1, "removal_revokes_member_shares": 1,
    "workspace_delete_revokes_all": 1, "removed_member_loses_read": 1, "owner_departure_cuts_shares": 1,
    "admin_enrolment_guard": 1, "member_list_hides_addresses": 1, "claim_is_conditional": 1,
    # 04B completion: two-step ownership transfer
    "transfer_two_step_no_early_move": 1, "transfer_unverified_recipient_refused": 1, "transfer_replay_and_expiry_refused": 1,
    "transfer_atomic_single_winner": 1, "transfer_party_departure_cancels": 1, "transfer_audit_metadata_only": 1,
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
