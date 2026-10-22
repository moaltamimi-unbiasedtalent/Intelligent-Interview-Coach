"""04B completion (REQ-OWN-07): two-step workspace ownership transfer with verified acceptance and immutable audit.

OD-WS-TRANSFER is still an OWNER DECISION; these tests pin the PROVISIONAL RECOMMENDED DEFAULT, they do not claim an approval.

Everything runs over the real FastAPI app on a temporary SQLite database with the in-memory mail sender: no network, no provider, no paid call.
Races are deterministic interleavings (a second connection acts between the read and the claim, like the 04B invitation tests) plus a bounded thread burst.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import timedelta

import pytest
from sqlalchemy import event, func, select, text

from src import persistence as P
from src.application.account_deletion_service import AccountDeletionService
from src.ownership_transfer_repository import AUDIT_EVENTS, OwnershipTransferRepository, hash_token, transfer_email_hash
from src.workspace_repository import WorkspaceRepository
from tests._auth_factories import account_repo
from tests._workspaces_04b_world import API, PW, World, build_team  # noqa: F401

T = P.WorkspaceOwnershipTransfer


@pytest.fixture(name="w")
def _world():
    world = World()
    yield world
    world.close()


@pytest.fixture(name="team")
def _team(w):
    return build_team(w)


def _transfers(w, wid):
    with w.repo.session_factory() as s:
        return [(t.status, t.proposer_user_id, t.recipient_user_id, t.former_owner_role, t.decided_reason)
                for t in s.scalars(select(T).where(T.workspace_id == wid).order_by(T.id)).all()]


def _audit(w, wid=None):
    with w.repo.session_factory() as s:
        q = select(P.AuditEvent).where(P.AuditEvent.event_type.in_(AUDIT_EVENTS)).order_by(P.AuditEvent.id)
        if wid is not None:
            q = q.where(P.AuditEvent.target_id == str(wid))
        return [(e.event_type, e.actor_user_id, dict(e.context or {})) for e in s.scalars(q).all()]


def _owner_ids(w, wid):
    with w.repo.session_factory() as s:
        return [m.user_id for m in s.scalars(select(P.WorkspaceMembership).where(
            P.WorkspaceMembership.workspace_id == wid, P.WorkspaceMembership.role == P.WORKSPACE_ROLE_OWNER,
            P.WorkspaceMembership.status == P.MEMBERSHIP_STATUS_ACTIVE)).all()]


def _set_row(w, wid, **values):
    with w.repo.session_factory() as s:
        row = s.scalar(select(T).where(T.workspace_id == wid).order_by(T.id.desc()))
        for k, v in values.items():
            setattr(row, k, v)
        s.commit()


# ============================================================================================================ state machine

def test_happy_path_two_steps_swaps_roles_and_keeps_exactly_one_owner(team):
    w, wa, _wb = team
    alice, adam = w.u["alice"]["uid"], w.u["adam"]["uid"]
    r = w.propose("alice", wa, "adam", name="Alpha", role="workspace_admin")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending" and body["viewer_role"] == "proposer" and body["former_owner_role"] == "workspace_admin"
    assert body["email_delivery"] == "submitted" and "token" not in json.dumps(body).lower()
    tok = w.token()

    # nothing has moved yet: the owner is still the owner
    assert _owner_ids(w, wa) == [alice]
    assert w.get("alice", f"/workspaces/{wa}").json()["my_role"] == "workspace_owner"

    acc = w.post("adam", "/workspaces/transfers/accept", {"token": tok})
    assert acc.status_code == 200 and acc.json()["owner_user_id"] == adam
    assert _owner_ids(w, wa) == [adam]
    assert w.get("alice", f"/workspaces/{wa}").json()["my_role"] == "workspace_admin"              # as chosen in the proposal
    assert w.get("adam", f"/workspaces/{wa}").json()["capabilities"]["can_delete"] is True
    assert _transfers(w, wa) == [("accepted", alice, adam, "workspace_admin", "accepted")]
    # the former owner can no longer administer ownership or propose again
    assert w.post("alice", f"/workspaces/{wa}/archive").status_code == 403
    assert w.propose("alice", wa, "adam", name="Alpha").status_code == 403


def test_former_owner_defaults_to_plain_member_and_unknown_roles_are_refused(team):
    w, wa, _wb = team
    assert w.step_up("alice").status_code == 200
    bad = w.post("alice", f"/workspaces/{wa}/transfer", {"new_owner_user_id": w.u["mia"]["uid"], "confirm_name": "Alpha", "former_owner_role": "workspace_owner"})
    assert bad.status_code == 422
    tok = w.transfer("alice", wa, "mia")
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok}).status_code == 200
    assert w.get("alice", f"/workspaces/{wa}").json()["my_role"] == "workspace_member"


def test_decline_cancel_and_the_recipient_or_proposer_only_rules(team):
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")
    tid = w.get("mia", f"/workspaces/{wa}/transfer").json()["transfer"]["id"]
    # only the recipient may decline; the proposer, another member and an outsider get 404 (nothing is revealed)
    for who in ("alice", "adam", "max", "olga", "ivan"):
        assert w.post(who, f"/workspaces/transfers/{tid}/decline").status_code == 404, who
    assert w.post("mia", f"/workspaces/transfers/{tid}/decline").json() == {"status": "declined"}
    assert _transfers(w, wa)[-1][0] == "declined"
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok}).status_code == 409        # a declined proposal cannot be accepted
    assert w.post("mia", f"/workspaces/transfers/{tid}/decline").status_code == 409                # nor declined twice
    assert _owner_ids(w, wa) == [w.u["alice"]["uid"]]

    # a new proposal after a terminal one is allowed; only the proposer cancels
    w.transfer("alice", wa, "max")
    for who in ("max", "adam", "mia", "olga", "ivan"):
        assert w.post(who, f"/workspaces/{wa}/transfer/cancel").status_code == 404, who
    assert w.post("alice", f"/workspaces/{wa}/transfer/cancel").json() == {"status": "cancelled"}
    assert w.post("alice", f"/workspaces/{wa}/transfer/cancel").status_code == 404                  # nothing open any more
    assert [s[0] for s in _transfers(w, wa)] == ["declined", "cancelled"]


def test_one_open_transfer_per_workspace(team):
    w, wa, _wb = team
    w.transfer("alice", wa, "mia")
    again = w.propose("alice", wa, "max", name="Alpha")
    assert again.status_code == 409 and "open ownership transfer" in again.json()["error"]["message"]
    assert w.propose("alice", wa, "mia", name="Alpha").status_code == 409
    assert len([t for t in _transfers(w, wa) if t[0] == "pending"]) == 1


def test_propose_validation_and_authorization(team):
    w, wa, wb = team
    # roles: only the owner; an admin, a member and non-members never see the step-up prompt
    for who, code in (("adam", 403), ("mia", 403), ("olga", 404), ("ivan", 404)):
        assert w.propose(who, wa, "max", name="Alpha", step_up=False).status_code == code, who
    mia = w.u["mia"]["uid"]
    base = {"new_owner_user_id": mia, "confirm_name": "Alpha"}
    # the step-up comes before any state change
    r = w.post("alice", f"/workspaces/{wa}/transfer", base)
    assert r.status_code == 403 and r.json()["error"]["code"] == "step_up_required"
    assert _transfers(w, wa) == []
    assert w.step_up("alice").status_code == 200
    assert w.post("alice", f"/workspaces/{wa}/transfer", {**base, "confirm_name": ""}).status_code == 422
    assert w.post("alice", f"/workspaces/{wa}/transfer", {**base, "confirm_name": "alpha"}).status_code == 422      # exact, case sensitive
    assert w.post("alice", f"/workspaces/{wa}/transfer", {**base, "new_owner_user_id": w.u["alice"]["uid"]}).status_code == 422
    assert w.post("alice", f"/workspaces/{wa}/transfer", {**base, "new_owner_user_id": w.u["olga"]["uid"]}).status_code == 422    # not a member
    assert w.post("alice", f"/workspaces/{wa}/transfer", {**base, "new_owner_user_id": 99999}).status_code == 422
    assert w.post("alice", f"/workspaces/{wa}/transfer", {**base, "surprise": 1}).status_code == 422                           # strict body
    assert _transfers(w, wa) == []
    # an archived workspace cannot be proposed
    w.post("alice", f"/workspaces/{wa}/archive")
    assert w.post("alice", f"/workspaces/{wa}/transfer", base).status_code == 409
    w.post("alice", f"/workspaces/{wa}/restore")
    assert w.post("alice", f"/workspaces/{wa}/transfer", base).status_code == 200
    assert wb != wa


def test_step_up_must_be_a_correct_password_on_this_session(team):
    w, wa, _wb = team
    wrong = w.post("alice", "/workspaces/transfers/step-up", {"password": "not-the-password"})
    assert wrong.status_code == 403 and wrong.json()["error"]["code"] == "step_up_failed"
    assert w.get("alice", "/workspaces/transfers/step-up").json()["elevated"] is False
    assert w.propose("alice", wa, "mia", name="Alpha", step_up=False).status_code == 403
    assert w.step_up("alice").status_code == 200
    assert w.get("alice", "/workspaces/transfers/step-up").json()["elevated"] is True
    # elevation belongs to the session of the person who confirmed: another account is not elevated by it
    assert w.get("adam", "/workspaces/transfers/step-up").json()["elevated"] is False
    assert w.propose("alice", wa, "mia", name="Alpha", step_up=False).status_code == 200
    w2 = w.post("alice", "/workspaces/transfers/step-up", {})
    assert w2.status_code == 422


def test_unverified_or_inactive_recipient_is_refused_at_proposal(team):
    w, wa, _wb = team
    w.user("eve")
    w.join("alice", wa, "eve")                                          # joining requires a verified address, so flip it after the fact
    with w.repo.session_factory() as s:
        s.get(P.User, w.u["eve"]["uid"]).email_verified = False
        s.commit()
    r = w.propose("alice", wa, "eve", name="Alpha")
    assert r.status_code == 422 and "verified" in r.json()["error"]["message"]
    with w.repo.session_factory() as s:
        s.get(P.User, w.u["eve"]["uid"]).email_verified = True
        s.get(P.User, w.u["eve"]["uid"]).status = P.ACCOUNT_STATUS_DEACTIVATED if hasattr(P, "ACCOUNT_STATUS_DEACTIVATED") else "deactivated"
        s.commit()
    assert w.propose("alice", wa, "eve", name="Alpha", step_up=False).status_code == 422
    assert _transfers(w, wa) == []


def test_workspace_with_more_than_one_owner_cannot_be_transferred(team):
    w, wa, _wb = team
    with w.repo.session_factory() as s:                                   # e.g. a platform operator added a second owner
        m = s.scalar(select(P.WorkspaceMembership).where(P.WorkspaceMembership.workspace_id == wa, P.WorkspaceMembership.user_id == w.u["adam"]["uid"]))
        m.role = P.WORKSPACE_ROLE_OWNER
        s.commit()
    r = w.propose("alice", wa, "mia", name="Alpha")
    assert r.status_code == 409 and _transfers(w, wa) == []


# ===================================================================================================== bound, verified acceptance

def test_the_token_is_bound_to_the_recipient_account(team):
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")
    # nobody else can use, preview or even confirm the existence of the proposal with the token
    for who in ("alice", "adam", "max", "olga", "ivan"):
        assert w.post(who, "/workspaces/transfers/accept", {"token": tok}).status_code == 404, who
        assert w.post(who, "/workspaces/transfers/preview", {"token": tok}).status_code == 404, who
    assert _owner_ids(w, wa) == [w.u["alice"]["uid"]] and _transfers(w, wa)[0][0] == "pending"
    # nonsense tokens look exactly the same
    assert w.post("mia", "/workspaces/transfers/accept", {"token": "x" * 40}).status_code == 404
    assert w.post("mia", "/workspaces/transfers/accept", {"token": ""}).status_code == 422
    prev = w.post("mia", "/workspaces/transfers/preview", {"token": tok})
    assert prev.status_code == 200 and prev.json()["workspace_name"] == "Alpha" and prev.json()["viewer_role"] == "recipient"
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok}).status_code == 200


def test_acceptance_requires_a_still_verified_and_still_bound_address(team):
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")
    with w.repo.session_factory() as s:
        s.get(P.User, w.u["mia"]["uid"]).email_verified = False
        s.commit()
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok}).status_code == 403
    assert w.post("mia", "/workspaces/transfers/preview", {"token": tok}).status_code == 403
    with w.repo.session_factory() as s:
        s.get(P.User, w.u["mia"]["uid"]).email_verified = True
        s.get(P.User, w.u["mia"]["uid"]).email = "someone.else@x.com"        # the address changed after the proposal was bound to the old one
        s.commit()
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok}).status_code == 403
    assert _owner_ids(w, wa) == [w.u["alice"]["uid"]]
    with w.repo.session_factory() as s:
        s.get(P.User, w.u["mia"]["uid"]).email = "mia@x.com"
        s.commit()
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok}).status_code == 200


def test_replayed_and_expired_tokens_are_refused(team):
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok}).status_code == 200
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok}).status_code == 409          # replay
    assert w.post("alice", "/workspaces/transfers/accept", {"token": tok}).status_code == 404
    assert _owner_ids(w, wa) == [w.u["mia"]["uid"]]

    # a second workspace: the deadline passes, the SERVER refuses and records the expiry (no client or job is involved)
    w2 = w.workspace("olga", "Bravo2")
    w.join("olga", w2, "max")
    tok2 = w.transfer("olga", w2, "max", name="Bravo2")
    _set_row(w, w2, expires_at=P.utcnow() - timedelta(seconds=1))
    r = w.post("max", "/workspaces/transfers/accept", {"token": tok2})
    assert r.status_code == 409 and "expired" in r.json()["error"]["message"]
    assert _transfers(w, w2)[0][0] == "expired" and _owner_ids(w, w2) == [w.u["olga"]["uid"]]
    assert w.post("max", "/workspaces/transfers/accept", {"token": tok2}).status_code == 409
    assert [e[0] for e in _audit(w, w2)] == ["workspace.transfer_proposed", "workspace.transfer_expired"]


def test_expiry_is_enforced_on_every_read_and_every_decision_and_frees_the_workspace(team):
    w, wa, _wb = team
    w.transfer("alice", wa, "mia")
    assert w.get("alice", f"/workspaces/{wa}/transfer").json()["transfer"]["expires_at"]
    _set_row(w, wa, expires_at=P.utcnow() - timedelta(minutes=1))
    assert w.get("mia", f"/workspaces/{wa}/transfer").json() == {"transfer": None}                   # reading expires it
    assert w.get("alice", "/workspaces/transfers/mine").json() == {"transfers": []}
    assert _transfers(w, wa)[0][0] == "expired"
    # the expired proposal does not block a new one
    assert w.propose("alice", wa, "max", name="Alpha").status_code == 200
    # decline and cancel of an overdue proposal also report expiry, once
    _set_row(w, wa, expires_at=P.utcnow() - timedelta(minutes=1))
    tid = _transfers(w, wa)
    assert w.post("alice", f"/workspaces/{wa}/transfer/cancel").status_code == 409
    assert [t[0] for t in tid][-1] == "pending" and _transfers(w, wa)[-1][0] == "expired"
    assert len([e for e in _audit(w, wa) if e[0] == "workspace.transfer_expired"]) == 2


def test_the_ttl_is_seven_days(team):
    w, wa, _wb = team
    r = w.propose("alice", wa, "mia", name="Alpha")
    from datetime import datetime
    exp = datetime.fromisoformat(r.json()["expires_at"])
    delta = exp - datetime.now(exp.tzinfo)
    assert timedelta(days=6, hours=23) < delta <= timedelta(days=7, seconds=5)


def test_archived_workspace_refuses_acceptance_without_changing_anything(team):
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")
    w.post("alice", f"/workspaces/{wa}/archive")
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok}).status_code == 409
    assert w.post("mia", "/workspaces/transfers/preview", {"token": tok}).status_code == 409
    assert _owner_ids(w, wa) == [w.u["alice"]["uid"]]
    w.post("alice", f"/workspaces/{wa}/restore")
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok}).status_code == 200


def test_roles_changing_under_a_pending_transfer_make_acceptance_fail_closed(team):
    """If the world changed behind the proposal (the proposer is no longer the owner, or the recipient is), acceptance cancels it instead of swapping."""
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")
    with w.repo.session_factory() as s:                                  # e.g. a platform operator demoted the proposer
        s.scalar(select(P.WorkspaceMembership).where(P.WorkspaceMembership.workspace_id == wa, P.WorkspaceMembership.user_id == w.u["alice"]["uid"])).role = P.WORKSPACE_ROLE_ADMIN
        s.commit()
    r = w.post("mia", "/workspaces/transfers/accept", {"token": tok})
    assert r.status_code == 409 and "no longer valid" in r.json()["error"]["message"]
    assert _transfers(w, wa)[0][0] == "cancelled" and _transfers(w, wa)[0][4] == "invalid_state"
    assert _audit(w, wa)[-1][0] == "workspace.transfer_cancelled" and _audit(w, wa)[-1][2]["reason"] == "invalid_state"
    with w.repo.session_factory() as s:
        assert [m.role for m in s.scalars(select(P.WorkspaceMembership).where(P.WorkspaceMembership.workspace_id == wa, P.WorkspaceMembership.user_id == w.u["mia"]["uid"]))] == [P.WORKSPACE_ROLE_MEMBER]


# ================================================================================================== visibility / isolation matrix

def test_who_can_see_a_pending_transfer(team):
    w, wa, wb = team
    w.transfer("alice", wa, "mia")
    p = w.get("alice", f"/workspaces/{wa}/transfer").json()["transfer"]
    r = w.get("mia", f"/workspaces/{wa}/transfer").json()["transfer"]
    assert p["viewer_role"] == "proposer" and r["viewer_role"] == "recipient" and p["id"] == r["id"]
    assert set(p) == {"id", "workspace_id", "status", "viewer_role", "former_owner_role", "expires_at", "created_at", "counterpart_label"}
    assert "@" not in json.dumps(p) + json.dumps(r) or "***" in json.dumps(p) + json.dumps(r)        # a masked label at most, never an address
    assert w.get("adam", f"/workspaces/{wa}/transfer").json() == {"transfer": None}                 # another member: no hint that one exists
    assert w.get("max", f"/workspaces/{wa}/transfer").json() == {"transfer": None}
    for who in ("olga", "ivan"):
        assert w.get(who, f"/workspaces/{wa}/transfer").status_code == 404
    assert w.get("olga", f"/workspaces/{wb}/transfer").json() == {"transfer": None}                  # her own workspace has none
    mine_a = w.get("alice", "/workspaces/transfers/mine").json()["transfers"]
    mine_m = w.get("mia", "/workspaces/transfers/mine").json()["transfers"]
    assert [t["workspace_name"] for t in mine_a] == ["Alpha"] == [t["workspace_name"] for t in mine_m]
    for who in ("adam", "max", "olga", "ivan"):
        assert w.get(who, "/workspaces/transfers/mine").json() == {"transfers": []}


def test_cross_workspace_and_cross_user_isolation_matrix(team):
    w, wa, wb = team
    tok_a = w.transfer("alice", wa, "mia")
    w.join("olga", wb, "ivan")
    tok_b = w.transfer("olga", wb, "ivan", name="Bravo")
    # each token works only for its own recipient in its own workspace
    assert w.post("ivan", "/workspaces/transfers/accept", {"token": tok_a}).status_code == 404
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok_b}).status_code == 404
    # a proposer cannot cancel, and a recipient cannot decline, the other workspace's transfer
    assert w.post("alice", f"/workspaces/{wb}/transfer/cancel").status_code == 404
    ida = w.get("mia", f"/workspaces/{wa}/transfer").json()["transfer"]["id"]
    assert w.post("ivan", f"/workspaces/transfers/{ida}/decline").status_code == 404
    # the owner of A cannot propose in B, and B's owner cannot propose in A
    assert w.propose("alice", wb, "ivan", name="Bravo").status_code == 404
    assert w.propose("olga", wa, "mia", name="Alpha").status_code == 404
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok_a}).status_code == 200
    assert w.post("ivan", "/workspaces/transfers/accept", {"token": tok_b}).status_code == 200
    assert _owner_ids(w, wa) == [w.u["mia"]["uid"]] and _owner_ids(w, wb) == [w.u["ivan"]["uid"]]


def test_every_new_route_requires_a_session_in_production():
    world = World("production")
    try:
        for method, path, body in (
            ("GET", "/workspaces/transfers/mine", None), ("GET", "/workspaces/transfers/step-up", None),
            ("POST", "/workspaces/transfers/step-up", {"password": "x"}), ("POST", "/workspaces/transfers/preview", {"token": "t"}),
            ("POST", "/workspaces/transfers/accept", {"token": "t"}), ("POST", "/workspaces/transfers/1/decline", None),
            ("GET", "/workspaces/1/transfer", None),
            ("POST", "/workspaces/1/transfer", {"new_owner_user_id": 2, "confirm_name": "x"}), ("POST", "/workspaces/1/transfer/cancel", None),
        ):
            r = world.c.request(method, f"{API}{path}", json=body)
            assert r.status_code == 401, (method, path, r.status_code)
    finally:
        world.close()


# ===================================================================================================================== races

def _engine(w):
    return w.repo.session_factory.kw["bind"]


def test_accept_vs_cancel_interleaving_yields_exactly_one_outcome(team):
    """A cancel that lands BETWEEN the accept's read and its claim must win: the claim is a conditional UPDATE, so the accept changes nothing
    and no role moves (deterministic interleaving, no threads)."""
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")
    trepo = OwnershipTransferRepository(w.repo.session_factory)
    fired: list[int] = []

    def interleave(conn, cursor, statement, parameters, context, executemany):
        if not fired and statement.lstrip().upper().startswith("SELECT") and re.search(r"FROM workspaces\s+WHERE", statement):
            fired.append(1)
            assert OwnershipTransferRepository(w.repo.session_factory).cancel(workspace_id=wa, user_id=w.u["alice"]["uid"])[0] == "ok"

    engine = _engine(w)
    event.listen(engine, "before_cursor_execute", interleave)
    try:
        outcome, _ = trepo.accept(token_hash=hash_token(tok), user_id=w.u["mia"]["uid"], email_hash=transfer_email_hash("mia@x.com"))
    finally:
        event.remove(engine, "before_cursor_execute", interleave)
    assert fired and outcome == "used"
    assert _transfers(w, wa)[0][0] == "cancelled" and _owner_ids(w, wa) == [w.u["alice"]["uid"]]
    kinds = [e[0] for e in _audit(w, wa)]
    assert kinds == ["workspace.transfer_proposed", "workspace.transfer_cancelled"]                  # exactly one decision recorded, no accept


def test_cancel_vs_accept_interleaving_yields_exactly_one_outcome(team):
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")
    fired: list[int] = []

    def interleave(conn, cursor, statement, parameters, context, executemany):
        if not fired and statement.lstrip().upper().startswith("SELECT") and re.search(r"FROM workspace_ownership_transfers", statement) and "workspace_id" in statement:
            fired.append(1)
            out, _ = OwnershipTransferRepository(w.repo.session_factory).accept(
                token_hash=hash_token(tok), user_id=w.u["mia"]["uid"], email_hash=transfer_email_hash("mia@x.com"))
            assert out == "ok"

    engine = _engine(w)
    event.listen(engine, "before_cursor_execute", interleave)
    try:
        out, _ = OwnershipTransferRepository(w.repo.session_factory).cancel(workspace_id=wa, user_id=w.u["alice"]["uid"])
    finally:
        event.remove(engine, "before_cursor_execute", interleave)
    assert fired and out in ("used", "not_found")                                                  # the accept won; the cancel changed nothing
    assert _transfers(w, wa)[0][0] == "accepted" and _owner_ids(w, wa) == [w.u["mia"]["uid"]]
    assert [e[0] for e in _audit(w, wa)] == ["workspace.transfer_proposed", "workspace.transfer_accepted"]


def test_expiry_winning_between_read_and_claim_stops_the_accept(team):
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")
    fired: list[int] = []

    def interleave(conn, cursor, statement, parameters, context, executemany):
        if not fired and statement.lstrip().upper().startswith("SELECT") and re.search(r"FROM workspaces\s+WHERE", statement):
            fired.append(1)
            with _engine(w).begin() as other:                           # the expiry job claimed the row first
                other.execute(text("UPDATE workspace_ownership_transfers SET status = 'expired' WHERE workspace_id = :w"), {"w": wa})

    engine = _engine(w)
    event.listen(engine, "before_cursor_execute", interleave)
    try:
        out, _ = OwnershipTransferRepository(w.repo.session_factory).accept(
            token_hash=hash_token(tok), user_id=w.u["mia"]["uid"], email_hash=transfer_email_hash("mia@x.com"))
    finally:
        event.remove(engine, "before_cursor_execute", interleave)
    assert fired and out == "used" and _owner_ids(w, wa) == [w.u["alice"]["uid"]]


def test_a_membership_that_ends_between_read_and_claim_cannot_be_swapped_in(team):
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")
    fired: list[int] = []

    def interleave(conn, cursor, statement, parameters, context, executemany):
        if not fired and statement.lstrip().upper().startswith("SELECT") and re.search(r"FROM workspaces\s+WHERE", statement):
            fired.append(1)
            WorkspaceRepository(w.repo.session_factory).end_membership(workspace_id=wa, user_id=w.u["mia"]["uid"], status=P.MEMBERSHIP_STATUS_LEFT)

    engine = _engine(w)
    event.listen(engine, "before_cursor_execute", interleave)
    try:
        out, _ = OwnershipTransferRepository(w.repo.session_factory).accept(
            token_hash=hash_token(tok), user_id=w.u["mia"]["uid"], email_hash=transfer_email_hash("mia@x.com"))
    finally:
        event.remove(engine, "before_cursor_execute", interleave)
    assert fired and out in ("used", "invalid")
    assert _owner_ids(w, wa) == [w.u["alice"]["uid"]] and _transfers(w, wa)[0][0] == "cancelled"


def test_concurrent_accepts_and_cancels_have_exactly_one_winner(team):
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")
    trepo = OwnershipTransferRepository(w.repo.session_factory)
    out: list[str] = []
    gate = threading.Barrier(8)

    def go(kind: str):
        gate.wait()
        try:
            if kind == "accept":
                out.append("accept" if trepo.accept(token_hash=hash_token(tok), user_id=w.u["mia"]["uid"], email_hash=transfer_email_hash("mia@x.com"))[0] == "ok" else "-")
            else:
                out.append("cancel" if trepo.cancel(workspace_id=wa, user_id=w.u["alice"]["uid"])[0] == "ok" else "-")
        except Exception:                      # a lost race on a locked SQLite file is not a second winner
            out.append("-")

    ts = [threading.Thread(target=go, args=(k,)) for k in ("accept", "cancel") * 4]
    [t.start() for t in ts]
    [t.join() for t in ts]
    winners = [x for x in out if x != "-"]
    assert len(winners) <= 1, out
    status = _transfers(w, wa)[0][0]
    owners = _owner_ids(w, wa)
    assert len(owners) == 1
    if status == "accepted":
        assert owners == [w.u["mia"]["uid"]] and winners == ["accept"]
    elif status == "cancelled":
        assert owners == [w.u["alice"]["uid"]] and winners == ["cancel"]
    kinds = [e[0] for e in _audit(w, wa)]
    assert kinds.count("workspace.transfer_accepted") + kinds.count("workspace.transfer_cancelled") <= 1


def test_concurrent_proposals_create_one_open_transfer(team):
    w, wa, _wb = team
    trepo = OwnershipTransferRepository(w.repo.session_factory)
    exp = P.utcnow() + timedelta(days=7)
    out: list[str] = []
    gate = threading.Barrier(6)

    def go(i: int):
        gate.wait()
        try:
            out.append(trepo.propose(workspace_id=wa, proposer_user_id=w.u["alice"]["uid"], recipient_user_id=w.u["mia"]["uid"],
                                     recipient_email_hash="h" * 64, former_owner_role="workspace_member", token_hash=f"{i:064d}", expires_at=exp)[0])
        except Exception:
            out.append("error")

    ts = [threading.Thread(target=go, args=(i,)) for i in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert out.count("ok") == 1, out
    assert len([t for t in _transfers(w, wa) if t[0] == "pending"]) == 1
    assert len([e for e in _audit(w, wa) if e[0] == "workspace.transfer_proposed"]) == 1


def test_the_database_itself_refuses_a_second_open_transfer(team):
    from sqlalchemy.exc import IntegrityError

    w, wa, _wb = team
    w.transfer("alice", wa, "mia")
    with w.repo.session_factory() as s:
        s.add(T(workspace_id=wa, proposer_user_id=w.u["alice"]["uid"], recipient_user_id=w.u["max"]["uid"], former_owner_role="workspace_member",
                token_hash="z" * 64, recipient_email_hash="h" * 64, status="pending", expires_at=P.utcnow() + timedelta(days=1)))
        with pytest.raises(IntegrityError):
            s.commit()


# ============================================================================================ leaving, removal, deactivation

def test_recipient_leaving_or_being_removed_cancels_the_transfer(team):
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")
    assert w.post("mia", f"/workspaces/{wa}/leave").status_code == 200
    assert _transfers(w, wa)[0][0] == "cancelled" and _transfers(w, wa)[0][4] == "membership_ended"
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok}).status_code == 409
    a = _audit(w, wa)
    assert [e[0] for e in a] == ["workspace.transfer_proposed", "workspace.transfer_cancelled"] and a[-1][2]["reason"] == "membership_ended"

    tok2 = w.transfer("alice", wa, "max")
    assert w.post("alice", f"/workspaces/{wa}/members/{w.u['max']['uid']}/remove").status_code == 200
    assert [t[0] for t in _transfers(w, wa)] == ["cancelled", "cancelled"]
    assert w.post("max", "/workspaces/transfers/accept", {"token": tok2}).status_code in (404, 409)


def test_platform_operator_removal_and_deactivation_cancel_the_transfer(team):
    from src.admin_repository import AdminUserRepository

    w, wa, _wb = team
    admin_repo = AdminUserRepository(w.repo.session_factory)
    w.transfer("alice", wa, "mia")
    admin_repo.remove_member(wa, w.u["mia"]["uid"])
    assert _transfers(w, wa)[0][:1] == ("cancelled",) and _transfers(w, wa)[0][4] == "membership_ended"

    w.transfer("alice", wa, "max")
    admin_repo.set_status(w.u["max"]["uid"], P.ACCOUNT_STATUS_DEACTIVATED if hasattr(P, "ACCOUNT_STATUS_DEACTIVATED") else "deactivated")
    assert _transfers(w, wa)[1][0] == "cancelled" and _transfers(w, wa)[1][4] == "account_deactivated"

    w.transfer("alice", wa, "adam")
    admin_repo.set_status(w.u["alice"]["uid"], P.ACCOUNT_STATUS_DEACTIVATED if hasattr(P, "ACCOUNT_STATUS_DEACTIVATED") else "deactivated")      # the PROPOSER
    assert _transfers(w, wa)[2][0] == "cancelled" and _transfers(w, wa)[2][4] == "account_deactivated"
    assert _owner_ids(w, wa) == [w.u["alice"]["uid"]]                                              # never orphaned, never silently moved
    reasons = [e[2].get("reason") for e in _audit(w, wa) if e[0] == "workspace.transfer_cancelled"]
    assert reasons == ["membership_ended", "account_deactivated", "account_deactivated"]


def test_deleting_the_recipient_account_cancels_and_never_orphans(team):
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")
    assert w.post("mia", "/auth/account/delete").status_code == 200
    assert _transfers(w, wa) == []                                                                  # the deleted user's rows go with the account
    a = _audit(w, wa)
    assert [e[0] for e in a] == ["workspace.transfer_proposed", "workspace.transfer_cancelled"] and a[-1][2]["reason"] == "account_deleted"
    assert _owner_ids(w, wa) == [w.u["alice"]["uid"]]
    assert w.post("max", "/workspaces/transfers/accept", {"token": tok}).status_code == 404
    assert w.propose("alice", wa, "max", name="Alpha").status_code == 200                           # the workspace is free to transfer again


def test_deleting_the_proposer_account_cancels_and_the_04b_successor_logic_stays(team):
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")
    assert w.post("alice", "/auth/account/delete").status_code == 200
    with w.repo.session_factory() as s:
        assert s.get(P.Workspace, wa).owner_user_id == w.u["adam"]["uid"]                           # the admin is the successor, exactly as in 04B
    assert _owner_ids(w, wa) == [w.u["adam"]["uid"]] and _transfers(w, wa) == []
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok}).status_code == 404
    a = _audit(w, wa)
    assert a[-1][0] == "workspace.transfer_cancelled" and a[-1][2]["reason"] == "account_deleted"


def test_deleting_a_workspace_with_an_open_transfer_removes_it_and_records_the_cancel(team):
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")
    assert w.post("alice", f"/workspaces/{wa}/delete", {"confirm_name": "Alpha"}).status_code == 200
    with w.repo.session_factory() as s:
        assert s.scalar(select(func.count()).select_from(T).where(T.workspace_id == wa)) == 0
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok}).status_code == 404
    a = _audit(w, wa)
    assert [e[0] for e in a] == ["workspace.transfer_proposed", "workspace.transfer_cancelled"] and a[-1][2]["reason"] == "workspace_deleted"


def test_other_transfers_are_untouched_by_an_unrelated_membership_change(team):
    w, wa, _wb = team
    w.transfer("alice", wa, "mia")
    assert w.post("max", f"/workspaces/{wa}/leave").status_code == 200                              # a third member leaves
    assert _transfers(w, wa)[0][0] == "pending"


# ========================================================================================================== immutable audit

def test_one_audit_record_per_state_change_with_metadata_only(team):
    w, wa, _wb = team
    w.user("zed")
    w.join("alice", wa, "zed")
    w.call("alice", "PATCH", f"/workspaces/{wa}", {"name": "Confidential Phoenix Programme"})
    name = "Confidential Phoenix Programme"
    # proposed -> accepted
    tok = w.transfer("alice", wa, "mia", name=name)
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok}).status_code == 200
    # proposed -> declined
    w.transfer("mia", wa, "max", name=name)
    mid = w.get("max", f"/workspaces/{wa}/transfer").json()["transfer"]["id"]
    assert w.post("max", f"/workspaces/transfers/{mid}/decline").status_code == 200
    # proposed -> cancelled
    w.transfer("mia", wa, "adam", name=name)
    assert w.post("mia", f"/workspaces/{wa}/transfer/cancel").status_code == 200
    # proposed -> expired
    w.transfer("mia", wa, "zed", name=name)
    _set_row(w, wa, expires_at=P.utcnow() - timedelta(minutes=5))
    w.get("mia", f"/workspaces/{wa}/transfer")
    a = _audit(w, wa)
    assert [e[0] for e in a] == [
        "workspace.transfer_proposed", "workspace.transfer_accepted",
        "workspace.transfer_proposed", "workspace.transfer_declined",
        "workspace.transfer_proposed", "workspace.transfer_cancelled",
        "workspace.transfer_proposed", "workspace.transfer_expired"]
    allowed = {"transfer_id", "actor_role", "former_owner_role", "outcome", "reason"}
    assert all(set(e[2]) <= allowed for e in a)
    assert [e[1] for e in a][:2] == [w.u["alice"]["uid"], w.u["mia"]["uid"]] and a[-1][1] is None   # the system expires, nobody acts
    assert {e[2]["outcome"] for e in a} == {"pending", "accepted", "declined", "cancelled", "expired"}
    blob = json.dumps(a, default=str)
    for forbidden in (name, "@", "x.com", tok, "alice", "mia"):
        assert forbidden not in blob, forbidden
    with w.repo.session_factory() as s:
        rows = s.scalars(select(P.AuditEvent).where(P.AuditEvent.event_type.in_(AUDIT_EVENTS))).all()
        assert {r.target_type for r in rows} == {"workspace"} and all(r.target_id == str(wa) for r in rows)


def test_the_audit_rows_are_append_only_in_the_database(team):
    w, wa, _wb = team
    w.transfer("alice", wa, "mia")
    with w.repo.session_factory() as s:
        row = s.scalars(select(P.AuditEvent).where(P.AuditEvent.event_type == "workspace.transfer_proposed")).one()
        rid = row.id
    with _engine(w).begin() as c:
        with pytest.raises(Exception, match="(?i)append|immutable|audit"):
            c.execute(text("UPDATE audit_events SET result = 'failure' WHERE id = :i"), {"i": rid})
    with _engine(w).begin() as c:
        with pytest.raises(Exception, match="(?i)append|immutable|audit"):
            c.execute(text("DELETE FROM audit_events WHERE id = :i"), {"i": rid})


def test_an_audit_failure_rolls_the_state_change_back(team):
    """The evidence is not optional for an ownership decision: if the audit row cannot be written, the transfer does not move."""
    w, wa, _wb = team
    tok = w.transfer("alice", wa, "mia")

    def refuse(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO AUDIT_EVENTS"):
            raise RuntimeError("audit store down")

    engine = _engine(w)
    event.listen(engine, "before_cursor_execute", refuse)
    try:
        with pytest.raises(RuntimeError):
            OwnershipTransferRepository(w.repo.session_factory).accept(
                token_hash=hash_token(tok), user_id=w.u["mia"]["uid"], email_hash=transfer_email_hash("mia@x.com"))
    finally:
        event.remove(engine, "before_cursor_execute", refuse)
    assert _transfers(w, wa)[0][0] == "pending" and _owner_ids(w, wa) == [w.u["alice"]["uid"]]
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok}).status_code == 200      # and it works once the store is back


def test_audit_context_keys_are_an_allow_list():
    from src.ownership_transfer_repository import _stage_audit

    class S:
        def add(self, _):
            raise AssertionError("must not be reached")

    with pytest.raises(ValueError):
        _stage_audit(S(), "workspace.transfer_proposed", actor_user_id=1, workspace_id=1, email="a@b.co")


def test_no_token_or_address_is_logged_or_stored_in_clear(team, caplog):
    w, wa, _wb = team
    caplog.set_level(logging.DEBUG)
    tok = w.transfer("alice", wa, "mia")
    w.post("mia", "/workspaces/transfers/preview", {"token": tok})
    w.post("mia", "/workspaces/transfers/accept", {"token": tok})
    w.post("mia", "/workspaces/transfers/accept", {"token": tok})
    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert tok not in logs and "mia@x.com" not in logs
    with w.repo.session_factory() as s:
        row = s.scalars(select(T)).first()
        stored = json.dumps([row.token_hash, row.recipient_email_hash])
    assert tok not in stored and "mia@x.com" not in stored
    assert row.token_hash == hash_token(tok) and row.recipient_email_hash == transfer_email_hash("mia@x.com") and len(row.token_hash) == 64


# ============================================================================================================ notice mail

def test_the_notice_is_guarded_localised_generic_and_goes_only_to_the_bound_recipient(team):
    w, wa, _wb = team
    account_repo(w.repo).set_interface_locale(w.u["mia"]["uid"], "de")
    w.call("alice", "PATCH", f"/workspaces/{wa}", {"name": "Secret Project Phoenix"})
    r = w.propose("alice", wa, "mia", name="Secret Project Phoenix")
    assert r.status_code == 200
    msg = w.mail.sent[-1]
    assert msg.category == "ownership_transfer" and msg.to == "mia@x.com"
    assert msg.subject.startswith("Der Inhaber") and msg.body.endswith("Ask More. Be More.")
    assert "/workspaces/transfer/accept?token=" in msg.body and "{" not in msg.body and "7 Tage" in msg.body
    assert "Secret Project Phoenix" not in msg.subject + msg.body and "alice" not in msg.body.lower()
    # English for a recipient whose interface language is English
    w.post("alice", f"/workspaces/{wa}/transfer/cancel")
    w.propose("alice", wa, "max", name="Secret Project Phoenix")
    assert w.mail.sent[-1].subject.startswith("An Ask4Mo workspace owner") and "7 days" in w.mail.sent[-1].body and w.mail.sent[-1].to == "max@x.com"


def test_the_notice_exists_in_all_eight_catalogues_without_user_text():
    from src.locales import SUPPORTED_LOCALE_CODES
    from src.mail.templates import render

    assert len(SUPPORTED_LOCALE_CODES) == 8
    subjects = set()
    for loc in SUPPORTED_LOCALE_CODES:
        out = render("ownership_transfer", locale=loc, link="https://app.example/x?token=T", expires_in_seconds=7 * 86400)
        assert out.locale == loc and "https://app.example/x?token=T" in out.body and "{" not in out.body and "}" not in out.body
        assert "7" in out.body and out.body.endswith("Ask More. Be More.") and out.subject
        subjects.add(out.subject)
    assert len(subjects) == 8
    # the existing lifetimes keep their hour phrasing
    assert "72 hours" in render("workspace_invitation", locale="en", link="l", expires_in_seconds=72 * 3600).body


def test_a_failing_mail_provider_never_breaks_or_fakes_the_proposal(team):
    w, wa, _wb = team

    class Boom:
        def send(self, m):
            raise RuntimeError("provider down")

    from src.api import dependencies as deps
    w.app.dependency_overrides[deps.get_email_sender] = lambda: Boom()
    r = w.propose("alice", wa, "mia", name="Alpha")
    assert r.status_code == 200 and r.json()["email_delivery"] == "not_submitted"
    assert _transfers(w, wa)[0][0] == "pending"                                                    # the proposer can cancel and try again


# ============================================================================================ Platform Admin: metadata only

def test_platform_admin_sees_only_that_a_transfer_is_pending(team):
    w, wa, wb = team
    w.user("root")
    account_repo(w.repo).set_platform_role(w.u["root"]["uid"], "platform_admin")
    r = w.get("root", f"/admin/workspaces/{wa}")
    assert r.status_code == 200 and r.json()["ownership_transfer_pending"] is False
    before = r.json()
    tok = w.transfer("alice", wa, "mia")
    r = w.get("root", f"/admin/workspaces/{wa}")
    assert r.json()["ownership_transfer_pending"] is True
    after = r.json()
    # the ONLY difference an operator can observe is the boolean: no party, role, deadline, token or address of the proposal is added
    assert {**after, "ownership_transfer_pending": False} == before
    for forbidden in (tok, "former_owner_role", "recipient", "proposer", "expires_at", "token_hash"):
        assert forbidden not in r.text, forbidden
    assert w.get("root", f"/admin/workspaces/{wb}").json()["ownership_transfer_pending"] is False
    # an operator has no transfer endpoint of any kind, and cannot read or act on the proposal
    assert w.get("root", f"/workspaces/{wa}/transfer").status_code == 404
    assert w.post("root", "/workspaces/transfers/accept", {"token": tok}).status_code == 404
    assert w.post("root", f"/workspaces/{wa}/transfer/cancel").status_code == 404
    _set_row(w, wa, expires_at=P.utcnow() - timedelta(minutes=1))
    assert w.get("root", f"/admin/workspaces/{wa}").json()["ownership_transfer_pending"] is False   # an overdue proposal no longer counts
    assert not any("transfer" in p for p in (w.app.openapi()["paths"].keys()) if p.startswith("/api/v1/admin"))


# ================================================================================================================ migration

def _alembic(tmp_path, monkeypatch):
    from tests.test_billing_f1_qualification import _alembic as make

    return make(tmp_path, monkeypatch)


def _rev():
    from tests._alembic_head import revisions

    found = [(rev, down) for rev, (down, _name) in revisions().items() if rev.endswith("_workspace_ownership_transfers")]
    assert len(found) == 1
    return found[0][0], found[0][1][0]


def test_migration_is_additive_and_chained_from_a_single_predecessor():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from tests._alembic_head import assert_chain, number, repository_head

    rev, prev = _rev()
    assert_chain(require=(prev, rev))
    assert number(rev) == number(prev) + 1
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == [repository_head()]
    assert script.get_revision(rev).down_revision == prev


def test_migration_upgrade_preserves_data_and_downgrade_is_fail_closed(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    cfg, url = _alembic(tmp_path, monkeypatch)
    rev, prev = _rev()
    command.upgrade(cfg, prev)
    eng = create_engine(url)
    with eng.begin() as c:
        assert "workspace_ownership_transfers" not in {r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    # a workspace that exists BEFORE the migration must survive it unchanged
    with sessionmaker(bind=eng)() as s:
        u1 = P.User(subject="a", provider="dev", email="a@example.com")
        u2 = P.User(subject="b", provider="dev", email="b@example.com")
        s.add_all([u1, u2])
        s.flush()
        ws = P.Workspace(owner_user_id=u1.id, name="Pre-existing", status="active")
        s.add(ws)
        s.flush()
        s.add_all([P.WorkspaceMembership(workspace_id=ws.id, user_id=u1.id, role="workspace_owner", status="active"),
                   P.WorkspaceMembership(workspace_id=ws.id, user_id=u2.id, role="workspace_member", status="active")])
        s.commit()
        ids = (u1.id, u2.id, ws.id)
    command.upgrade(cfg, rev)
    with eng.begin() as c:
        assert c.execute(text("SELECT name, owner_user_id FROM workspaces")).all() == [("Pre-existing", ids[0])]
        assert c.execute(text("SELECT COUNT(*) FROM workspace_memberships")).scalar() == 2
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(workspace_ownership_transfers)"))}
        assert {"workspace_id", "proposer_user_id", "recipient_user_id", "former_owner_role", "token_hash", "recipient_email_hash", "status", "expires_at"} <= cols
        idx = {r[1]: r[2] for r in c.execute(text("PRAGMA index_list(workspace_ownership_transfers)"))}
        assert idx["uq_ownership_transfer_one_open"] == 1 and idx["ix_ownership_transfers_token"] == 1                 # both unique
        # the partial unique index lets history coexist but refuses a second open row
        ins = ("INSERT INTO workspace_ownership_transfers (workspace_id, proposer_user_id, recipient_user_id, former_owner_role, token_hash, "
               "recipient_email_hash, status, expires_at, created_at, updated_at) VALUES (:w, :p, :r, 'workspace_member', :t, 'h', :s, '2030-01-01', '2026-01-01', '2026-01-01')")
        c.execute(text(ins), {"w": ids[2], "p": ids[0], "r": ids[1], "t": "t1", "s": "declined"})
        c.execute(text(ins), {"w": ids[2], "p": ids[0], "r": ids[1], "t": "t2", "s": "pending"})
    with pytest.raises(Exception):
        with eng.begin() as c:
            c.execute(text(ins), {"w": ids[2], "p": ids[0], "r": ids[1], "t": "t3", "s": "pending"})
    with pytest.raises(Exception):                                       # the status vocabulary is closed
        with eng.begin() as c:
            c.execute(text(ins), {"w": ids[2], "p": ids[0], "r": ids[1], "t": "t4", "s": "bogus"})
    # fail closed: ANY row, even a terminal one, blocks the downgrade and nothing is deleted
    with pytest.raises(Exception, match="Refusing to downgrade .*_workspace_ownership_transfers"):
        command.downgrade(cfg, prev)
    with eng.begin() as c:
        assert c.execute(text("SELECT COUNT(*) FROM workspace_ownership_transfers")).scalar() == 2
        c.execute(text("DELETE FROM workspace_ownership_transfers"))
    command.downgrade(cfg, prev)                                         # once removed deliberately, it proceeds and removes only its own table
    with eng.begin() as c:
        assert "workspace_ownership_transfers" not in {r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        assert c.execute(text("SELECT COUNT(*) FROM workspaces")).scalar() == 1 and c.execute(text("SELECT COUNT(*) FROM workspace_memberships")).scalar() == 2
    command.upgrade(cfg, rev)                                            # and the upgrade can be repeated


def test_migration_matches_the_orm_model(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, inspect

    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "head")
    insp = inspect(create_engine(url))
    migrated = {c["name"] for c in insp.get_columns("workspace_ownership_transfers")}
    assert migrated == {c.name for c in T.__table__.columns}
    fks = {(fk["referred_table"], fk["options"].get("ondelete")) for fk in insp.get_foreign_keys("workspace_ownership_transfers")}
    assert fks == {("workspaces", "CASCADE"), ("users", "CASCADE")}
