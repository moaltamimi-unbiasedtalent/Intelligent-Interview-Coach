"""04B Workspaces completion (REQ-OWN-07): lifecycle, roles, invitations, consent, revocation, deletion, isolation.

Everything runs over the real FastAPI app against a temporary SQLite database with the in-memory mail sender: no network, no
provider, no paid call. Backend authorization is proven at the API boundary (REQ-OWN-07 W5), not through the UI.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src import persistence as P
from src.api.rate_limit import reset_rate_limiter
from src.workspace_repository import MAX_PENDING_INVITATIONS, WorkspaceRepository
from tests._auth_factories import account_repo, build_auth_app, cookies_for, login_token, register, verify_email

PW = "correcthorsebattery"
API = "/api/v1"


class World:
    """A running app plus named personas. Every persona is a registered, VERIFIED account unless created otherwise."""

    def __init__(self, env: str = "test"):
        self.app, self.repo, self.mail = build_auth_app(env)
        self.c = TestClient(self.app)
        self.c.__enter__()
        self.u: dict[str, dict] = {}

    def close(self):
        self.c.__exit__(None, None, None)

    def user(self, name: str, *, verified: bool = True) -> dict:
        email = f"{name}@x.com"
        reset_rate_limiter()                    # test infrastructure: a persona is not a brute-force attempt (register is 8 per IP per hour)
        register(self.c, email, PW)
        if verified:
            verify_email(self.repo, email)
        token = login_token(self.c, email, PW)
        ck = cookies_for(token)
        uid = self.c.get(f"{API}/auth/me", cookies=ck).json()["user_id"]
        self.u[name] = {"email": email, "ck": ck, "uid": uid}
        return self.u[name]

    def call(self, who: str, method: str, path: str, json_body=None):
        return self.c.request(method, f"{API}{path}", json=json_body, cookies=self.u[who]["ck"])

    def get(self, who, path):
        return self.call(who, "GET", path)

    def post(self, who, path, body=None):
        return self.call(who, "POST", path, body if body is not None else None)

    def token(self) -> str:
        return self.mail.sent[-1].body.split("token=")[1].split()[0]

    # -- compound helpers --------------------------------------------------------------------------------------------
    def workspace(self, owner: str, name: str = "Alpha") -> int:
        r = self.post(owner, "/workspaces", {"name": name})
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def join(self, owner: str, wid: int, who: str, role: str = "workspace_member") -> None:
        r = self.post(owner, f"/workspaces/{wid}/invite", {"email": self.u[who]["email"], "role": role})
        assert r.status_code == 200, r.text
        a = self.post(who, "/workspaces/invitations/accept", {"token": self.token()})
        assert a.status_code == 200, a.text

    def story(self, who: str, title: str = "My win") -> str:
        r = self.post(who, "/stories", {"title": title, "status": "user_created", "situation": "Led a team of five"})
        assert r.status_code in (200, 201), r.text
        return str(r.json()["id"])

    def report(self, who: str) -> str:
        with self.repo.session_factory() as s:
            iv = P.Interview(user_id=self.u[who]["uid"], configuration={"target_role": "PM"}, status="completed")
            s.add(iv)
            s.flush()
            s.add(P.Report(interview_id=iv.id, report={"overall_score": 90, "summary": "Great"}))
            s.commit()
            return str(iv.id)

    def share(self, who, wid, rtype, rid, consent=True):
        return self.post(who, "/shares", {"workspace_id": wid, "resource_type": rtype, "resource_id": rid, "consent": consent})


@pytest.fixture
def w():
    world = World()
    yield world
    world.close()


@pytest.fixture
def team(w):
    """owner(alice) + admin(adam) + member(mia) + member2(max) in workspace A; outsider(olga) in her own workspace B."""
    for n in ("alice", "adam", "mia", "max", "olga", "ivan"):
        w.user(n)
    wa = w.workspace("alice", "Alpha")
    w.join("alice", wa, "adam", "workspace_admin")
    w.join("alice", wa, "mia")
    w.join("alice", wa, "max")
    wb = w.workspace("olga", "Bravo")
    return w, wa, wb


# =========================================================================================================== lifecycle

def test_create_rename_and_validation(w):
    w.user("alice"); w.user("adam"); w.user("olga")
    wid = w.workspace("alice")
    assert w.post("alice", "/workspaces", {"name": "   "}).status_code == 422
    assert w.post("alice", "/workspaces", {"name": "x" * 121}).status_code == 422
    r = w.call("alice", "PATCH", f"/workspaces/{wid}", {"name": "  Renamed \t Team "})
    assert r.status_code == 200 and r.json()["name"] == "Renamed Team"              # whitespace and control characters normalised
    assert w.call("alice", "PATCH", f"/workspaces/{wid}", {"name": ""}).status_code == 422
    w.join("alice", wid, "adam", "workspace_admin")
    assert w.call("adam", "PATCH", f"/workspaces/{wid}", {"name": "By admin"}).status_code == 200
    assert w.call("olga", "PATCH", f"/workspaces/{wid}", {"name": "Hijack"}).status_code == 404     # not a member: existence hidden
    assert w.get("alice", f"/workspaces/{wid}").json()["name"] == "By admin"


def test_owner_can_own_a_bounded_number_of_workspaces(w):
    w.user("alice")
    for i in range(20):
        assert w.post("alice", "/workspaces", {"name": f"W{i}"}).status_code == 200
    assert w.post("alice", "/workspaces", {"name": "one too many"}).status_code == 409


def test_archive_restore_and_the_archived_state(team):
    w, wa, _wb = team
    rid = w.story("mia")
    assert w.share("mia", wa, "story", rid).status_code == 200
    assert w.get("max", f"/shares/resource/story/{rid}").status_code == 200

    # only the owner archives; admin and member are refused
    assert w.post("adam", f"/workspaces/{wa}/archive").status_code == 403
    assert w.post("mia", f"/workspaces/{wa}/archive").status_code == 403
    r = w.post("alice", f"/workspaces/{wa}/archive")
    assert r.status_code == 200 and r.json()["status"] == "deactivated"
    assert w.post("alice", f"/workspaces/{wa}/archive").status_code == 200                 # idempotent

    # archived: grants revoked at once, no new invitations / renames / shares / role changes, members can still read the page and leave
    assert w.get("max", f"/shares/resource/story/{rid}").status_code == 404
    assert w.get("mia", f"{'/workspaces'}/{wa}").status_code == 200
    assert w.post("alice", f"/workspaces/{wa}/invite", {"email": "new@x.com"}).status_code == 409
    assert w.call("alice", "PATCH", f"/workspaces/{wa}", {"name": "Nope"}).status_code == 409
    assert w.share("mia", wa, "story", rid).status_code == 409
    assert w.post("alice", f"/workspaces/{wa}/members/{w.u['mia']['uid']}/role", {"role": "workspace_admin"}).status_code == 409

    # restore: owner only; a revoked grant does NOT come back
    assert w.post("adam", f"/workspaces/{wa}/restore").status_code == 403
    assert w.post("alice", f"/workspaces/{wa}/restore").json()["status"] == "active"
    assert w.get("max", f"/shares/resource/story/{rid}").status_code == 404
    assert w.get("mia", "/shares/mine").json()["shares"] == []
    assert w.share("mia", wa, "story", rid).status_code == 200                              # consent given again
    assert w.get("max", f"/shares/resource/story/{rid}").status_code == 200


def test_delete_requires_owner_and_typed_name_and_revokes_everything(team):
    w, wa, _wb = team
    rid = w.story("mia")
    w.share("mia", wa, "story", rid)
    w.post("alice", f"/workspaces/{wa}/invite", {"email": w.u["ivan"]["email"]})
    pending_tok = w.token()

    assert w.post("adam", f"/workspaces/{wa}/delete", {"confirm_name": "Alpha"}).status_code == 403
    assert w.post("mia", f"/workspaces/{wa}/delete", {"confirm_name": "Alpha"}).status_code == 403
    assert w.post("olga", f"/workspaces/{wa}/delete", {"confirm_name": "Alpha"}).status_code == 404
    assert w.post("alice", f"/workspaces/{wa}/delete", {"confirm_name": "alpha"}).status_code == 422     # exact name
    assert w.post("alice", f"/workspaces/{wa}/delete", {}).status_code == 422
    r = w.post("alice", f"/workspaces/{wa}/delete", {"confirm_name": "Alpha"})
    assert r.status_code == 200 and r.json()["members_removed"] == 4 and r.json()["shares_removed"] == 1

    for who in ("alice", "adam", "mia", "max"):
        assert w.get(who, f"/workspaces/{wa}").status_code == 404
        assert w.get(who, f"/workspaces/{wa}/shares").status_code == 404
    assert w.get("max", f"/shares/resource/story/{rid}").status_code == 404
    assert w.get("max", "/shares/with-me").json()["shares"] == []
    assert w.post("ivan", "/workspaces/invitations/accept", {"token": pending_tok}).status_code == 404   # invitation row is gone
    with w.repo.session_factory() as s:
        for model in (P.ShareGrant, P.WorkspaceMembership, P.WorkspaceInvitation):
            assert s.scalars(select(model).where(model.workspace_id == wa)).first() is None
    # nothing the members OWN was deleted
    assert w.get("mia", f"/stories/{rid}").status_code == 200


# ============================================================================================ roles and authorization

def _state(w, wid):
    with w.repo.session_factory() as s:
        ws = s.get(P.Workspace, wid)
        members = sorted((m.user_id, m.role, m.status) for m in s.scalars(select(P.WorkspaceMembership).where(P.WorkspaceMembership.workspace_id == wid)))
        invs = sorted((i.id, i.status) for i in s.scalars(select(P.WorkspaceInvitation).where(P.WorkspaceInvitation.workspace_id == wid)))
        shares = sorted((g.id, g.status) for g in s.scalars(select(P.ShareGrant).where(P.ShareGrant.workspace_id == wid)))
        return ws.name, ws.status, ws.owner_user_id, members, invs, shares


def _all_routes(w, wid, target_uid, inv_id, token):
    """Every workspace-scoped route with a body that would SUCCEED for an owner, as (name, method, path, body)."""
    return [
        ("detail", "GET", f"/workspaces/{wid}", None),
        ("shares", "GET", f"/workspaces/{wid}/shares", None),
        ("rename", "PATCH", f"/workspaces/{wid}", {"name": "Pwned"}),
        ("invite", "POST", f"/workspaces/{wid}/invite", {"email": "z@x.com"}),
        ("invite_admin", "POST", f"/workspaces/{wid}/invite", {"email": "z2@x.com", "role": "workspace_admin"}),
        ("revoke_invite", "POST", f"/workspaces/{wid}/invitations/{inv_id}/revoke", None),
        ("role", "POST", f"/workspaces/{wid}/members/{target_uid}/role", {"role": "workspace_admin"}),
        ("remove", "POST", f"/workspaces/{wid}/members/{target_uid}/remove", None),
        ("transfer", "POST", f"/workspaces/{wid}/transfer", {"new_owner_user_id": target_uid, "confirm_name": "Alpha"}),
        ("archive", "POST", f"/workspaces/{wid}/archive", None),
        ("deactivate", "POST", f"/workspaces/{wid}/deactivate", None),
        ("restore", "POST", f"/workspaces/{wid}/restore", None),
        ("delete", "POST", f"/workspaces/{wid}/delete", {"confirm_name": "Alpha"}),
        ("leave", "POST", f"/workspaces/{wid}/leave", None),
    ]


@pytest.mark.parametrize("persona", ["other_workspace_owner", "invited_not_accepted", "removed", "left", "unverified"])
def test_no_non_member_can_touch_any_workspace_route(team, persona):
    """404 (never 403, never success) for every workspace-scoped route, and nothing changes: a member of workspace B reading A,
    a removed member, a member who left, an invited-but-not-accepted account, an account with an unverified address."""
    w, wa, wb = team
    w.post("alice", f"/workspaces/{wa}/invite", {"email": w.u["ivan"]["email"]})                  # ivan: invited, not accepted
    inv_id = w.get("alice", f"/workspaces/{wa}").json()["pending_invitations"][0]["id"]
    w.user("rita"); w.user("lena"); w.user("uma", verified=False)
    w.join("alice", wa, "rita"); w.join("alice", wa, "lena")
    w.post("alice", f"/workspaces/{wa}/members/{w.u['rita']['uid']}/remove")
    w.post("lena", f"/workspaces/{wa}/leave")
    who = {"other_workspace_owner": "olga", "invited_not_accepted": "ivan",
           "removed": "rita", "left": "lena", "unverified": "uma"}[persona]
    before = _state(w, wa)
    target = w.u["mia"]["uid"]
    for name, method, path, body in _all_routes(w, wa, target, inv_id, "x"):
        r = w.call(who, method, path, body)
        assert r.status_code == 404, (persona, name, r.status_code, r.text)
    assert _state(w, wa) == before


def test_member_and_admin_role_matrix_over_every_route(team):
    w, wa, _wb = team
    w.post("alice", f"/workspaces/{wa}/invite", {"email": w.u["ivan"]["email"]})
    inv_id = w.get("alice", f"/workspaces/{wa}").json()["pending_invitations"][0]["id"]
    adam, mia = w.u["adam"]["uid"], w.u["mia"]["uid"]
    before = _state(w, wa)

    # a plain member: may read the workspace (labels only) and its share list and may leave; every management route is 403
    denied_for_member = {"rename", "invite", "invite_admin", "revoke_invite", "role", "remove", "transfer", "archive",
                         "deactivate", "restore", "delete"}
    for name, method, path, body in _all_routes(w, wa, w.u["max"]["uid"], inv_id, "x"):
        if name in ("leave",):
            continue
        r = w.call("mia", method, path, body)
        expected = 403 if name in denied_for_member else 200
        assert r.status_code == expected, ("member", name, r.status_code, r.text)
    assert _state(w, wa) == before

    # an admin: may rename, invite and revoke plain-member invitations and remove plain members; never admin invites, role changes,
    # transfer, archive, restore, delete, or removing the owner or another admin
    for name, method, path, body in (
        ("invite_admin", "POST", f"/workspaces/{wa}/invite", {"email": "q@x.com", "role": "workspace_admin"}),
        ("role", "POST", f"/workspaces/{wa}/members/{mia}/role", {"role": "workspace_admin"}),
        ("transfer", "POST", f"/workspaces/{wa}/transfer", {"new_owner_user_id": adam, "confirm_name": "Alpha"}),
        ("archive", "POST", f"/workspaces/{wa}/archive", None),
        ("restore", "POST", f"/workspaces/{wa}/restore", None),
        ("delete", "POST", f"/workspaces/{wa}/delete", {"confirm_name": "Alpha"}),
        ("remove_owner", "POST", f"/workspaces/{wa}/members/{w.u['alice']['uid']}/remove", None),
    ):
        r = w.call("adam", method, path, body)
        assert r.status_code in (403, 409), ("admin", name, r.status_code, r.text)
        assert r.status_code != 200
    assert _state(w, wa) == before
    assert w.call("adam", "PATCH", f"/workspaces/{wa}", {"name": "Admin renamed"}).status_code == 200
    assert w.post("adam", f"/workspaces/{wa}/invite", {"email": "ok@x.com"}).status_code == 200
    assert w.post("adam", f"/workspaces/{wa}/invitations/{inv_id}/revoke").status_code == 200
    assert w.post("adam", f"/workspaces/{wa}/members/{w.u['max']['uid']}/remove").status_code == 200


def test_admin_cannot_remove_another_admin_or_revoke_an_admin_invitation(team):
    w, wa, _wb = team
    w.user("ada2")
    w.join("alice", wa, "ada2", "workspace_admin")
    assert w.post("adam", f"/workspaces/{wa}/members/{w.u['ada2']['uid']}/remove").status_code == 403
    w.post("alice", f"/workspaces/{wa}/invite", {"email": "x1@x.com", "role": "workspace_admin"})
    inv = [i for i in w.get("alice", f"/workspaces/{wa}").json()["pending_invitations"] if i["email"] == "x1@x.com"][0]
    assert w.post("adam", f"/workspaces/{wa}/invitations/{inv['id']}/revoke").status_code == 403
    assert w.post("alice", f"/workspaces/{wa}/invitations/{inv['id']}/revoke").status_code == 200
    # the owner removes an admin
    assert w.post("alice", f"/workspaces/{wa}/members/{w.u['ada2']['uid']}/remove").status_code == 200


def test_role_changes_owner_only_and_never_touch_the_owner(team):
    w, wa, _wb = team
    mia, alice = w.u["mia"]["uid"], w.u["alice"]["uid"]
    assert w.post("alice", f"/workspaces/{wa}/members/{mia}/role", {"role": "workspace_admin"}).json() == {"user_id": mia, "role": "workspace_admin", "changed": True}
    assert w.post("alice", f"/workspaces/{wa}/members/{mia}/role", {"role": "workspace_admin"}).json()["changed"] is False
    assert w.post("alice", f"/workspaces/{wa}/members/{mia}/role", {"role": "workspace_member"}).json()["changed"] is True
    assert w.post("alice", f"/workspaces/{wa}/members/{mia}/role", {"role": "workspace_owner"}).status_code == 422   # ownership moves only by transfer
    assert w.post("alice", f"/workspaces/{wa}/members/{mia}/role", {"role": "boss"}).status_code == 422
    assert w.post("alice", f"/workspaces/{wa}/members/{alice}/role", {"role": "workspace_member"}).status_code == 422  # not your own role
    assert w.post("alice", f"/workspaces/{wa}/members/{w.u['olga']['uid']}/role", {"role": "workspace_admin"}).status_code == 404   # not a member
    # an admin's new rights are real, and removing them takes effect on the next request
    w.post("alice", f"/workspaces/{wa}/members/{mia}/role", {"role": "workspace_admin"})
    assert w.post("mia", f"/workspaces/{wa}/invite", {"email": "n@x.com"}).status_code == 200
    w.post("alice", f"/workspaces/{wa}/members/{mia}/role", {"role": "workspace_member"})
    assert w.post("mia", f"/workspaces/{wa}/invite", {"email": "n2@x.com"}).status_code == 403


def test_last_owner_protection_and_ownership_transfer(team):
    w, wa, _wb = team
    alice, adam, mia = (w.u[n]["uid"] for n in ("alice", "adam", "mia"))
    # the only owner can neither leave nor be removed; the API says what to do
    assert w.post("alice", f"/workspaces/{wa}/leave").status_code == 409
    assert w.post("adam", f"/workspaces/{wa}/members/{alice}/remove").status_code == 409
    # transfer needs the exact workspace name and an ACTIVE member other than yourself
    assert w.post("alice", f"/workspaces/{wa}/transfer", {"new_owner_user_id": adam}).status_code == 422
    assert w.post("alice", f"/workspaces/{wa}/transfer", {"new_owner_user_id": adam, "confirm_name": "wrong"}).status_code == 422
    assert w.post("alice", f"/workspaces/{wa}/transfer", {"new_owner_user_id": alice, "confirm_name": "Alpha"}).status_code == 422
    assert w.post("alice", f"/workspaces/{wa}/transfer", {"new_owner_user_id": w.u["olga"]["uid"], "confirm_name": "Alpha"}).status_code == 422
    assert w.post("mia", f"/workspaces/{wa}/transfer", {"new_owner_user_id": mia, "confirm_name": "Alpha"}).status_code == 403
    r = w.post("alice", f"/workspaces/{wa}/transfer", {"new_owner_user_id": adam, "confirm_name": "Alpha"})
    assert r.status_code == 200 and r.json()["owner_user_id"] == adam
    detail = w.get("adam", f"/workspaces/{wa}").json()
    assert detail["my_role"] == "workspace_owner" and detail["capabilities"]["can_delete"] is True
    # the former owner is a plain member: no management, but may now leave
    assert w.get("alice", f"/workspaces/{wa}").json()["my_role"] == "workspace_member"
    assert w.post("alice", f"/workspaces/{wa}/archive").status_code == 403
    assert w.post("alice", f"/workspaces/{wa}/transfer", {"new_owner_user_id": alice, "confirm_name": "Alpha"}).status_code == 403
    assert w.post("alice", f"/workspaces/{wa}/leave").status_code == 200
    with w.repo.session_factory() as s:
        owners = s.scalars(select(P.WorkspaceMembership).where(
            P.WorkspaceMembership.workspace_id == wa, P.WorkspaceMembership.role == P.WORKSPACE_ROLE_OWNER,
            P.WorkspaceMembership.status == P.MEMBERSHIP_STATUS_ACTIVE)).all()
        assert [m.user_id for m in owners] == [adam]


def test_remove_member_ends_access_immediately_and_unshares(team):
    w, wa, _wb = team
    rid = w.story("mia")
    w.share("mia", wa, "story", rid)
    assert w.get("max", f"/shares/resource/story/{rid}").status_code == 200
    r = w.post("alice", f"/workspaces/{wa}/members/{w.u['mia']['uid']}/remove")
    assert r.status_code == 200 and r.json()["shares_revoked"] == 1
    assert w.get("mia", f"/workspaces/{wa}").status_code == 404                                  # the removed member sees nothing
    assert w.get("max", f"/shares/resource/story/{rid}").status_code == 404                      # and what she shared is gone
    assert w.get("max", "/shares/with-me").json()["shares"] == []
    assert w.get("mia", "/shares/mine").json()["shares"] == []
    assert w.post("alice", f"/workspaces/{wa}/members/{w.u['mia']['uid']}/remove").status_code == 404   # already gone
    assert w.post("alice", f"/workspaces/{wa}/members/{w.u['alice']['uid']}/remove").status_code in (409, 422)
    # a removed member can be invited again and starts with nothing shared
    w.join("alice", wa, "mia")
    assert w.get("max", f"/shares/resource/story/{rid}").status_code == 404


def test_leave_unshares_and_audits(team):
    w, wa, _wb = team
    rid = w.story("max")
    w.share("max", wa, "story", rid)
    r = w.post("max", f"/workspaces/{wa}/leave")
    assert r.status_code == 200 and r.json()["shares_revoked"] == 1
    assert w.get("mia", f"/shares/resource/story/{rid}").status_code == 404
    assert w.post("max", f"/workspaces/{wa}/leave").status_code == 404


def test_member_list_shows_labels_not_other_addresses(team):
    w, wa, _wb = team
    as_member = w.get("mia", f"/workspaces/{wa}").json()
    assert "pending_invitations" not in as_member
    for m in as_member["members"]:
        if m["is_me"]:
            assert m["email"] == "mia@x.com"
        else:
            assert "email" not in m and m["label"].endswith("***@x.com") and "alice@" not in json.dumps(m)
    as_owner = w.get("alice", f"/workspaces/{wa}").json()
    assert {m["email"] for m in as_owner["members"]} == {"alice@x.com", "adam@x.com", "mia@x.com", "max@x.com"}
    assert as_owner["capabilities"]["can_delete"] is True and as_member["capabilities"]["can_delete"] is False


# ================================================================================================== invitations

def test_invitation_lifecycle_accept_decline_revoke_expire(team):
    w, wa, _wb = team
    for n in ("dora", "dan", "eli", "fay", "gus"):
        w.user(n)
    # create -> pending visible to the owner, hashed at rest, ~72h expiry
    r = w.post("alice", f"/workspaces/{wa}/invite", {"email": "Dora@X.com"})
    assert r.status_code == 200 and r.json()["status"] == "pending" and r.json()["email_delivery"] == "submitted"
    raw = w.token()
    with w.repo.session_factory() as s:
        inv = s.scalars(select(P.WorkspaceInvitation).where(P.WorkspaceInvitation.workspace_id == wa, P.WorkspaceInvitation.email == "dora@x.com")).one()
        assert inv.email == "dora@x.com" and inv.token_hash != raw and raw not in json.dumps([inv.token_hash, inv.email])
        assert 71 * 3600 < (inv.expires_at.replace(tzinfo=P.utcnow().tzinfo) - P.utcnow()).total_seconds() <= 72 * 3600 + 5
    pend = w.get("alice", f"/workspaces/{wa}").json()["pending_invitations"]
    assert len(pend) == 1 and pend[0]["email"] == "dora@x.com" and "token" not in json.dumps(pend)

    # the invited account sees it (id, workspace name, role) but never the inviter's identity or the token
    listed = w.get("dora", "/workspaces").json()["invited"]
    assert len(listed) == 1 and listed[0]["workspace_name"] == "Alpha" and "email" not in listed[0] and "inviter_user_id" not in listed[0]
    assert w.get("dan", "/workspaces").json()["invited"] == []
    # accepting by id: only the addressee (a different verified account gets 404, not a hint)
    assert w.post("dan", f"/workspaces/invitations/{listed[0]['id']}/accept").status_code == 404
    assert w.post("dora", f"/workspaces/invitations/{listed[0]['id']}/accept").status_code == 200
    assert w.get("dora", f"/workspaces/{wa}").json()["my_role"] == "workspace_member"
    assert w.post("dora", f"/workspaces/invitations/{listed[0]['id']}/accept").status_code == 409     # one time
    assert w.post("dora", "/workspaces/invitations/accept", {"token": raw}).status_code == 409
    assert w.get("alice", f"/workspaces/{wa}").json()["pending_invitations"] == []

    # decline: consumed, never joins, cannot then be accepted
    w.post("alice", f"/workspaces/{wa}/invite", {"email": "dan@x.com"})
    tok = w.token()
    assert w.post("dan", "/workspaces/invitations/decline", {"token": tok}).status_code == 200
    assert w.post("dan", "/workspaces/invitations/accept", {"token": tok}).status_code == 409
    assert w.get("dan", f"/workspaces/{wa}").status_code == 404

    # revoke by an owner/admin: unusable afterwards
    w.post("alice", f"/workspaces/{wa}/invite", {"email": "eli@x.com"})
    tok = w.token()
    iid = [i for i in w.get("alice", f"/workspaces/{wa}").json()["pending_invitations"] if i["email"] == "eli@x.com"][0]["id"]
    assert w.post("mia", f"/workspaces/{wa}/invitations/{iid}/revoke").status_code == 403
    assert w.post("olga", f"/workspaces/{wa}/invitations/{iid}/revoke").status_code == 404
    assert w.post("alice", f"/workspaces/{wa}/invitations/{iid}/revoke").status_code == 200
    assert w.post("alice", f"/workspaces/{wa}/invitations/{iid}/revoke").status_code == 409            # no longer pending
    assert w.post("eli", "/workspaces/invitations/accept", {"token": tok}).status_code == 409
    assert w.get("eli", "/workspaces").json()["invited"] == []
    # the revoke route is scoped to ITS workspace: an invitation id of another workspace is not found
    w.post("olga", f"/workspaces/{_wb}/invite", {"email": "gus@x.com"})
    other = w.get("olga", f"/workspaces/{_wb}").json()["pending_invitations"][0]["id"]
    assert w.post("alice", f"/workspaces/{wa}/invitations/{other}/revoke").status_code == 404

    # expiry: an expired invitation cannot be accepted, declined or previewed, and is not offered to the invitee
    w.post("alice", f"/workspaces/{wa}/invite", {"email": "fay@x.com"})
    tok = w.token()
    with w.repo.session_factory() as s:
        row = s.scalars(select(P.WorkspaceInvitation).where(P.WorkspaceInvitation.email == "fay@x.com", P.WorkspaceInvitation.workspace_id == wa)).one()
        row.expires_at = P.utcnow() - timedelta(minutes=1)
        s.commit()
    assert w.get("fay", "/workspaces").json()["invited"] == []
    assert w.post("fay", "/workspaces/invitations/preview", {"token": tok}).status_code == 409
    assert w.post("fay", "/workspaces/invitations/accept", {"token": tok}).status_code == 409
    assert w.post("fay", "/workspaces/invitations/decline", {"token": tok}).status_code == 409
    assert w.get("fay", f"/workspaces/{wa}").status_code == 404
    assert [i["status"] for i in w.get("alice", f"/workspaces/{wa}").json()["pending_invitations"] if i["email"] == "fay@x.com"] == ["expired"]


def test_invitation_is_bound_to_a_verified_address(team):
    w, wa, _wb = team
    w.user("victim_addr", verified=False)            # registers the invitee's address but never proves it
    w.post("alice", f"/workspaces/{wa}/invite", {"email": "victim_addr@x.com"})
    tok = w.token()
    assert w.get("victim_addr", "/workspaces").json()["invited"] == []                       # does not even learn it exists
    assert w.post("victim_addr", "/workspaces/invitations/accept", {"token": tok}).status_code == 403
    assert w.post("victim_addr", "/workspaces/invitations/preview", {"token": tok}).status_code == 403
    assert w.post("victim_addr", "/workspaces/invitations/decline", {"token": tok}).status_code == 403
    iid = w.get("alice", f"/workspaces/{wa}").json()["pending_invitations"][0]["id"]
    assert w.post("victim_addr", f"/workspaces/invitations/{iid}/accept").status_code == 403
    assert w.get("victim_addr", f"/workspaces/{wa}").status_code == 404
    # the refusal did not consume the invitation: once the address is verified it works
    verify_email(w.repo, "victim_addr@x.com")
    assert w.post("victim_addr", "/workspaces/invitations/accept", {"token": tok}).status_code == 200
    # and a verified account with a DIFFERENT address can never use someone else's token
    w.post("alice", f"/workspaces/{wa}/invite", {"email": "ivan@x.com"})
    assert w.post("olga", "/workspaces/invitations/accept", {"token": w.token()}).status_code == 403


def test_preview_shows_the_name_only_to_the_invited_verified_account(team):
    w, wa, _wb = team
    w.post("alice", f"/workspaces/{wa}/invite", {"email": "ivan@x.com", "role": "workspace_admin"})
    tok = w.token()
    p = w.post("ivan", "/workspaces/invitations/preview", {"token": tok})
    assert p.status_code == 200 and p.json()["workspace_name"] == "Alpha" and p.json()["role"] == "workspace_admin"
    assert w.post("olga", "/workspaces/invitations/preview", {"token": tok}).status_code == 403
    assert w.post("ivan", "/workspaces/invitations/preview", {"token": "nope"}).status_code == 404
    assert w.get("ivan", f"/workspaces/{wa}").status_code == 404                                      # previewing joins nothing


def test_reinvite_supersedes_and_duplicates_are_refused(team):
    w, wa, _wb = team
    w.post("alice", f"/workspaces/{wa}/invite", {"email": "ivan@x.com"})
    first = w.token()
    w.post("alice", f"/workspaces/{wa}/invite", {"email": "IVAN@x.com"})
    second = w.token()
    assert first != second
    assert len(w.get("alice", f"/workspaces/{wa}").json()["pending_invitations"]) == 1        # one live token per address
    assert w.post("ivan", "/workspaces/invitations/accept", {"token": first}).status_code == 409
    assert w.post("ivan", "/workspaces/invitations/accept", {"token": second}).status_code == 200
    assert w.post("alice", f"/workspaces/{wa}/invite", {"email": "mia@x.com"}).status_code == 409    # already a member
    assert w.post("alice", f"/workspaces/{wa}/invite", {"email": "ivan@x.com"}).status_code == 409


@pytest.mark.parametrize("bad", ["", "no-at-sign", "a@b", "a b@x.com", "x@y.com\r\nBcc: z@z.com", "<a@x.com>", "a@x.com,b@x.com", "a@x.com;b@x.com", "'a'@x.com"])
def test_invalid_or_injecting_addresses_are_refused(team, bad):
    w, wa, _wb = team
    sent = len(w.mail.sent)
    r = w.post("alice", f"/workspaces/{wa}/invite", {"email": bad})
    assert r.status_code == 422, (bad, r.status_code)
    assert len(w.mail.sent) == sent


def test_pending_invitations_are_bounded(team):
    w, wa, _wb = team
    for i in range(MAX_PENDING_INVITATIONS):
        assert w.post("alice", f"/workspaces/{wa}/invite", {"email": f"p{i}@x.com"}).status_code == 200
    assert w.post("alice", f"/workspaces/{wa}/invite", {"email": "extra@x.com"}).status_code == 409
    assert w.post("alice", f"/workspaces/{wa}/invite", {"email": "p0@x.com"}).status_code == 200      # re-inviting an address is not growth


def test_invitation_email_uses_the_guarded_service_is_localised_and_generic(team):
    w, wa, _wb = team
    account_repo(w.repo).set_interface_locale(w.u["ivan"]["uid"], "de")
    w.call("alice", "PATCH", f"/workspaces/{wa}", {"name": "Secret Project Phoenix"})
    r = w.post("alice", f"/workspaces/{wa}/invite", {"email": "ivan@x.com"})
    assert r.status_code == 200
    msg = w.mail.sent[-1]
    assert msg.category == "workspace_invitation" and msg.to == "ivan@x.com"
    assert msg.subject.startswith("Du wurdest") and msg.body.endswith("Ask More. Be More.")
    assert "/workspaces/accept?token=" in msg.body and "{" not in msg.body
    assert "Secret Project Phoenix" not in msg.subject + msg.body and "alice" not in msg.body.lower()   # no user-authored text in the mail
    # an address with no account falls back to English
    w.post("alice", f"/workspaces/{wa}/invite", {"email": "nobody@x.com"})
    assert w.mail.sent[-1].subject.startswith("You have been invited")


def test_a_failing_mail_provider_never_breaks_or_fakes_an_invitation(team):
    w, wa, _wb = team

    class Boom:
        def send(self, m):
            raise RuntimeError("provider down")

    from src.api import dependencies as deps
    w.app.dependency_overrides[deps.get_email_sender] = lambda: Boom()
    r = w.post("alice", f"/workspaces/{wa}/invite", {"email": "ivan@x.com"})
    assert r.status_code == 200 and r.json()["email_delivery"] == "not_submitted"                  # honest: not "delivered", not "sent"
    pend = w.get("alice", f"/workspaces/{wa}").json()["pending_invitations"]
    assert len(pend) == 1                                                                           # the owner can revoke it or re-invite
    assert w.post("alice", f"/workspaces/{wa}/invitations/{pend[0]['id']}/revoke").status_code == 200


def test_concurrent_acceptance_has_exactly_one_winner(team):
    w, wa, _wb = team
    w.post("alice", f"/workspaces/{wa}/invite", {"email": "ivan@x.com"})
    repo = WorkspaceRepository(w.repo.session_factory)
    inv = repo.list_invitations_for_workspace(wa)[0]
    out: list[str] = []
    gate = threading.Barrier(8)

    def go():
        gate.wait()
        try:
            out.append(repo.decide_invitation(invitation_id=inv["id"], user_id=w.u["ivan"]["uid"], email="ivan@x.com", accept=True)[0])
        except Exception:                      # a lost race on a locked SQLite file is not a second winner
            out.append("error")

    ts = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert out.count("ok") == 1, out
    with w.repo.session_factory() as s:
        rows = s.scalars(select(P.WorkspaceMembership).where(P.WorkspaceMembership.workspace_id == wa, P.WorkspaceMembership.user_id == w.u["ivan"]["uid"])).all()
        assert len(rows) == 1 and rows[0].status == P.MEMBERSHIP_STATUS_ACTIVE
        assert s.scalars(select(P.WorkspaceInvitation).where(P.WorkspaceInvitation.id == inv["id"])).one().status == P.INVITATION_STATUS_ACCEPTED


def test_accept_and_decline_race_cannot_do_both(team):
    w, wa, _wb = team
    w.post("alice", f"/workspaces/{wa}/invite", {"email": "ivan@x.com"})
    repo = WorkspaceRepository(w.repo.session_factory)
    inv = repo.list_invitations_for_workspace(wa)[0]
    a = repo.decide_invitation(invitation_id=inv["id"], user_id=w.u["ivan"]["uid"], email="ivan@x.com", accept=False)[0]
    b = repo.decide_invitation(invitation_id=inv["id"], user_id=w.u["ivan"]["uid"], email="ivan@x.com", accept=True)[0]
    assert (a, b) == ("ok", "used") and repo.member_role(wa, w.u["ivan"]["uid"]) is None


def test_an_invitation_never_downgrades_an_existing_member(team):
    w, wa, _wb = team
    repo = WorkspaceRepository(w.repo.session_factory)
    exp = P.utcnow() + timedelta(hours=1)
    inv_id = repo.create_invitation(workspace_id=wa, inviter_user_id=w.u["alice"]["uid"], email="adam@x.com",
                                    token_hash="h" * 64, role=P.WORKSPACE_ROLE_MEMBER, expires_at=exp)
    out, _ = repo.decide_invitation(invitation_id=inv_id, user_id=w.u["adam"]["uid"], email="adam@x.com", accept=True)
    assert out == "ok" and repo.member_role(wa, w.u["adam"]["uid"]) == P.WORKSPACE_ROLE_ADMIN


def test_cannot_accept_into_an_archived_workspace(team):
    w, wa, _wb = team
    w.post("alice", f"/workspaces/{wa}/invite", {"email": "ivan@x.com"})
    tok = w.token()
    w.post("alice", f"/workspaces/{wa}/archive")
    assert w.get("ivan", "/workspaces").json()["invited"] == []
    assert w.post("ivan", "/workspaces/invitations/preview", {"token": tok}).status_code == 409
    assert w.post("ivan", "/workspaces/invitations/accept", {"token": tok}).status_code == 409
    assert w.get("ivan", f"/workspaces/{wa}").status_code == 404


# ========================================================================================== sharing and revocation

@pytest.mark.parametrize("kind", ["story", "interview_report"])
def test_explicit_consent_view_only_and_immediate_revocation(team, kind):
    w, wa, wb = team
    rid = w.story("mia") if kind == "story" else w.report("mia")
    # consent is mandatory: nothing is created without it
    for body in (False, None):
        payload = {"workspace_id": wa, "resource_type": kind, "resource_id": rid}
        if body is not None:
            payload["consent"] = body
        assert w.post("mia", "/shares", payload).status_code == 422
    assert w.get("mia", "/shares/mine").json()["shares"] == []
    assert w.get("max", f"/shares/resource/{kind}/{rid}").status_code == 404                  # joining shared nothing

    r = w.share("mia", wa, kind, rid)
    assert r.status_code == 200 and r.json()["permission"] == "view"
    sid = r.json()["share_id"]
    # members read; the workspace owner/admin are members too, outsiders and other-workspace members are not
    for ok in ("max", "alice", "adam", "mia"):
        assert w.get(ok, f"/shares/resource/{kind}/{rid}").status_code == 200, ok
    for no in ("olga", "ivan"):
        assert w.get(no, f"/shares/resource/{kind}/{rid}").status_code == 404, no
    # VIEW only: a member cannot change or delete the owner's item through any route, and cannot export it
    assert w.call("max", "DELETE", f"/shares/{sid}").status_code == 404
    if kind == "story":
        assert w.call("max", "PATCH", f"/stories/{rid}", {"title": "x"}).status_code == 404
        assert w.call("max", "DELETE", f"/stories/{rid}").status_code == 404
        assert w.get("max", f"/stories/{rid}").status_code == 404
    else:
        assert w.get("max", f"/reports/{rid}/export.json").status_code in (403, 404)
        assert w.get("max", f"/history/interviews/{rid}").status_code in (403, 404)
    # what is listed (derived data) follows the grant
    assert [s["resource_id"] for s in w.get("max", "/shares/with-me").json()["shares"]] == [rid]
    assert [s["resource_id"] for s in w.get("max", f"/workspaces/{wa}/shares").json()["shares"]] == [rid]
    # revoke: effective on the very next request for reads, lists and the workspace view
    assert w.call("mia", "DELETE", f"/shares/{sid}").status_code == 200
    assert w.get("max", f"/shares/resource/{kind}/{rid}").status_code == 404
    assert w.get("alice", f"/shares/resource/{kind}/{rid}").status_code == 404
    assert w.get("max", "/shares/with-me").json()["shares"] == []
    assert w.get("max", f"/workspaces/{wa}/shares").json()["shares"] == []
    assert w.call("mia", "DELETE", f"/shares/{sid}").status_code == 200                        # idempotent for the owner
    # and the owner still has her item
    assert w.get("mia", f"/stories/{rid}" if kind == "story" else f"/history/interviews/{rid}").status_code == 200


def test_shared_story_view_is_a_bounded_projection(team):
    w, wa, _wb = team
    rid = w.story("mia")
    w.share("mia", wa, "story", rid)
    view = w.get("max", f"/shares/resource/story/{rid}").json()
    assert view["shared_by_owner"] is True
    assert set(view["resource"]) == {"id", "title", "situation", "task", "action", "result", "competencies", "status", "updated_at"}
    # the owner's own listing still carries evidence links; the member never sees them
    assert "evidence_claim_ids" in w.get("mia", f"/stories/{rid}").json()


def test_workspace_share_list_is_metadata_only_and_member_only(team):
    w, wa, wb = team
    rid = w.story("mia", "Confidential launch story")
    w.share("mia", wa, "story", rid)
    listing = w.get("max", f"/workspaces/{wa}/shares")
    assert listing.status_code == 200
    item = listing.json()["shares"][0]
    assert item["resource_type"] == "story" and item["resource_id"] == rid and item["mine"] is False
    assert "owner_user_id" not in item and item["shared_by"] == "m***@x.com"
    assert "Confidential launch story" not in listing.text and "Led a team" not in listing.text    # never content
    assert w.get("mia", f"/workspaces/{wa}/shares").json()["shares"][0]["mine"] is True
    assert w.get("olga", f"/workspaces/{wa}/shares").status_code == 404
    assert w.get("ivan", f"/workspaces/{wa}/shares").status_code == 404


def test_sharer_label_masks_the_address(team):
    w, wa, _wb = team
    rid = w.story("mia")
    w.share("mia", wa, "story", rid)
    s = w.get("max", "/shares/with-me").json()["shares"][0]
    assert s["shared_by"] == "m***@x.com" and s["workspace_name"] == "Alpha"
    account_repo(w.repo).set_display_name(w.u["mia"]["uid"], "Mia Example")
    assert w.get("max", "/shares/with-me").json()["shares"][0]["shared_by"] == "Mia Example"


def test_a_share_is_scoped_to_its_workspace_and_the_sharers_membership(team):
    w, wa, wb = team
    rid = w.story("mia")
    assert w.share("mia", wb, "story", rid).status_code == 403                  # not a member of B
    assert w.share("max", wa, "story", rid).status_code == 403                  # not the owner of the item
    assert w.share("mia", wa, "preparation_summary", "1").status_code == 422    # not an operational resource type
    assert w.share("mia", wa, "story", "999999").status_code == 403             # unknown item: same answer as someone else's
    assert w.share("mia", wa, "story", "abc").status_code == 403
    w.share("mia", wa, "story", rid)
    # olga belongs to ANOTHER workspace and still cannot read A's item; the reverse holds for a share into B
    assert w.get("olga", f"/shares/resource/story/{rid}").status_code == 404
    rb = w.story("olga")
    w.share("olga", wb, "story", rb)
    for who in ("alice", "adam", "mia", "max"):
        assert w.get(who, f"/shares/resource/story/{rb}").status_code == 404


def test_deleting_the_source_item_stops_the_share(team):
    w, wa, _wb = team
    rid = w.story("mia")
    w.share("mia", wa, "story", rid)
    assert w.call("mia", "DELETE", f"/stories/{rid}").status_code == 200
    assert w.get("max", f"/shares/resource/story/{rid}").status_code == 404


def test_sharer_leaving_or_being_removed_cuts_access_even_without_a_status_sweep(team):
    """Defence in depth: the read decision itself requires the sharer to still be an ACTIVE member."""
    w, wa, _wb = team
    rid = w.story("mia")
    w.share("mia", wa, "story", rid)
    with w.repo.session_factory() as s:
        m = s.scalars(select(P.WorkspaceMembership).where(P.WorkspaceMembership.workspace_id == wa, P.WorkspaceMembership.user_id == w.u["mia"]["uid"])).one()
        m.status = P.MEMBERSHIP_STATUS_REMOVED        # bypasses the service on purpose: the grant row is still 'active'
        s.commit()
    assert w.get("max", f"/shares/resource/story/{rid}").status_code == 404
    assert w.get("max", "/shares/with-me").json()["shares"] == []


def test_platform_admin_gets_metadata_but_no_content_and_cannot_enrol_staff(team):
    w, wa, _wb = team
    w.user("root")
    account_repo(w.repo).set_platform_role(w.u["root"]["uid"], "platform_admin")
    rid = w.story("mia", "Private story title")
    w.share("mia", wa, "story", rid)
    r = w.get("root", f"/admin/workspaces/{wa}")
    assert r.status_code == 200 and r.json()["active_share_count"] == 1
    assert "Private story title" not in r.text and "Led a team" not in r.text and "story" not in json.dumps(r.json()["members"])
    assert w.get("root", f"/shares/resource/story/{rid}").status_code == 404                      # not a member: no access
    assert w.get("root", f"/workspaces/{wa}").status_code == 404
    # an operator cannot enrol platform staff (that would hand them every shared item)
    add = w.post("root", f"/admin/workspaces/{wa}/members", {"user_id": w.u["root"]["uid"]})
    assert add.status_code == 409 and w.get("root", f"/workspaces/{wa}").status_code == 404
    # ...but can still enrol an ordinary account (existing, audited admin operation)
    assert w.post("root", f"/admin/workspaces/{wa}/members", {"user_id": w.u["ivan"]["uid"]}).status_code == 200


# ============================================================================================ deletion correctness

def test_account_deletion_transfers_to_an_admin_first_and_removes_dangling_access(team):
    w, wa, wb = team
    rid = w.story("alice")
    w.share("alice", wa, "story", rid)
    w.post("alice", f"/workspaces/{wa}/invite", {"email": "ivan@x.com"})                          # invited BY the owner
    w.post("olga", f"/workspaces/{wb}/invite", {"email": "alice@x.com"})                          # invited TO the owner's address
    # a second workspace where the plain member joined BEFORE the admin: the admin must still be preferred
    wx = w.workspace("alice", "Xray")
    w.join("alice", wx, "mia")
    w.join("alice", wx, "adam", "workspace_admin")
    assert w.post("alice", "/auth/account/delete").status_code == 200
    with w.repo.session_factory() as s:
        assert s.get(P.Workspace, wa).owner_user_id == w.u["adam"]["uid"]
        assert s.get(P.Workspace, wx).owner_user_id == w.u["adam"]["uid"]                         # admin, not the older plain member
        roles = {m.user_id: m.role for m in s.scalars(select(P.WorkspaceMembership).where(P.WorkspaceMembership.workspace_id == wx))}
        assert roles == {w.u["adam"]["uid"]: P.WORKSPACE_ROLE_OWNER, w.u["mia"]["uid"]: P.WORKSPACE_ROLE_MEMBER}
        roles_a = {m.user_id: m.role for m in s.scalars(select(P.WorkspaceMembership).where(P.WorkspaceMembership.workspace_id == wa))}
        assert roles_a == {w.u["adam"]["uid"]: P.WORKSPACE_ROLE_OWNER, w.u["mia"]["uid"]: P.WORKSPACE_ROLE_MEMBER, w.u["max"]["uid"]: P.WORKSPACE_ROLE_MEMBER}
        assert s.scalars(select(P.ShareGrant).where(P.ShareGrant.owner_user_id == w.u["alice"]["uid"])).first() is None
        assert s.scalars(select(P.WorkspaceInvitation).where(P.WorkspaceInvitation.email == "alice@x.com")).first() is None   # PII removed
        assert s.scalars(select(P.WorkspaceInvitation).where(P.WorkspaceInvitation.inviter_user_id == w.u["alice"]["uid"])).first() is None
        audit = s.scalars(select(P.AuditEvent).where(P.AuditEvent.event_type == "workspace.ownership_transferred")).all()
        assert audit and audit[-1].context["reason"] == "account_deleted" and audit[-1].actor_user_id is None
    assert w.get("max", f"/shares/resource/story/{rid}").status_code == 404
    assert w.get("adam", f"/workspaces/{wa}").json()["my_role"] == "workspace_owner"
    assert w.get("adam", f"/workspaces/{wa}").json()["capabilities"]["can_delete"] is True


def test_account_deletion_of_a_sole_owner_removes_the_workspace_and_every_grant(w):
    for n in ("alice", "ivan"):
        w.user(n)
    wid = w.workspace("alice", "Solo")
    rid = w.story("alice")
    w.share("alice", wid, "story", rid)
    w.post("alice", f"/workspaces/{wid}/invite", {"email": "ivan@x.com"})
    tok = w.token()
    assert w.post("alice", "/auth/account/delete").status_code == 200
    with w.repo.session_factory() as s:
        assert s.get(P.Workspace, wid) is None
        for model in (P.ShareGrant, P.WorkspaceMembership, P.WorkspaceInvitation):
            assert s.scalars(select(model).where(model.workspace_id == wid)).first() is None
    assert w.post("ivan", "/workspaces/invitations/accept", {"token": tok}).status_code == 404


def test_member_account_deletion_removes_its_memberships_and_shares_only(team):
    w, wa, _wb = team
    rid = w.story("mia")
    w.share("mia", wa, "story", rid)
    assert w.post("mia", "/auth/account/delete").status_code == 200
    assert w.get("max", f"/shares/resource/story/{rid}").status_code == 404
    detail = w.get("alice", f"/workspaces/{wa}").json()
    assert detail["member_count"] == 3 and {m["email"] for m in detail["members"]} == {"alice@x.com", "adam@x.com", "max@x.com"}


# ======================================================================================================== audit

def test_audit_records_membership_role_and_share_changes_without_content(team):
    w, wa, _wb = team
    rid = w.story("mia", "Highly confidential story title")
    w.share("mia", wa, "story", rid)
    sid = w.get("mia", "/shares/mine").json()["shares"][0]["id"]
    w.post("alice", f"/workspaces/{wa}/members/{w.u['mia']['uid']}/role", {"role": "workspace_admin"})
    w.post("alice", f"/workspaces/{wa}/invite", {"email": "ivan@x.com"})
    inv = w.get("alice", f"/workspaces/{wa}").json()["pending_invitations"][0]["id"]
    w.post("alice", f"/workspaces/{wa}/invitations/{inv}/revoke")
    w.call("alice", "PATCH", f"/workspaces/{wa}", {"name": "Renamed"})
    w.call("mia", "DELETE", f"/shares/{sid}")
    w.post("alice", f"/workspaces/{wa}/members/{w.u['max']['uid']}/remove")
    w.post("adam", f"/workspaces/{wa}/leave")
    w.post("alice", f"/workspaces/{wa}/archive")
    w.post("alice", f"/workspaces/{wa}/restore")
    w.post("alice", f"/workspaces/{wa}/transfer", {"new_owner_user_id": w.u["mia"]["uid"], "confirm_name": "Renamed"})
    w.post("mia", f"/workspaces/{wa}/delete", {"confirm_name": "Renamed"})
    with w.repo.session_factory() as s:
        events = s.scalars(select(P.AuditEvent).where(P.AuditEvent.event_type.like("workspace.%") | P.AuditEvent.event_type.like("share.%"))).all()
        types = {e.event_type for e in events}
        blob = json.dumps([(e.event_type, e.context, e.target_id, e.target_type) for e in events], default=str)
    expected = {"workspace.created", "workspace.invite_created", "workspace.invite_accepted", "workspace.invite_revoked",
                "workspace.member_role_changed", "workspace.renamed", "workspace.member_removed", "workspace.member_left",
                "workspace.archived", "workspace.restored", "workspace.ownership_transferred", "workspace.deleted",
                "share.created", "share.revoked"}
    assert expected <= types, expected - types
    consent = [e for e in events if e.event_type == "share.created"][0].context
    assert consent["consent"] is True and consent["resource_type"] == "story" and consent["visible_to_members"] == 4
    # no content, no address, no token, no workspace or item name
    for forbidden in ("@", "Highly confidential", "Led a team", "Renamed", "Alpha", "token"):
        assert forbidden not in blob, forbidden


# ====================================================================================================== production

def test_every_new_route_requires_a_session_in_production():
    world = World("production")
    try:
        for method, path, body in (
            ("GET", "/workspaces/1", None), ("PATCH", "/workspaces/1", {"name": "x"}), ("POST", "/workspaces/1/invite", {"email": "a@b.co"}),
            ("POST", "/workspaces/1/invitations/1/revoke", None), ("POST", "/workspaces/invitations/preview", {"token": "t"}),
            ("POST", "/workspaces/invitations/1/accept", None), ("POST", "/workspaces/invitations/1/decline", None),
            ("POST", "/workspaces/1/members/2/role", {"role": "workspace_admin"}), ("POST", "/workspaces/1/members/2/remove", None),
            ("POST", "/workspaces/1/transfer", {"new_owner_user_id": 2, "confirm_name": "x"}), ("POST", "/workspaces/1/archive", None),
            ("POST", "/workspaces/1/restore", None), ("POST", "/workspaces/1/delete", {"confirm_name": "x"}),
            ("GET", "/workspaces/1/shares", None), ("POST", "/shares", {"workspace_id": 1, "resource_type": "story", "resource_id": "1", "consent": True}),
            ("DELETE", "/shares/1", None), ("GET", "/shares/resource/story/1", None),
        ):
            r = world.c.request(method, f"{API}{path}", json=body)
            assert r.status_code == 401, (method, path, r.status_code)
    finally:
        world.close()


def test_the_archived_status_is_only_ever_reached_through_the_service(team):
    """The legacy deactivate route is an alias of archive (same revocation)."""
    w, wa, _wb = team
    rid = w.story("mia")
    w.share("mia", wa, "story", rid)
    assert w.post("mia", f"/workspaces/{wa}/deactivate").status_code == 403
    assert w.post("alice", f"/workspaces/{wa}/deactivate").status_code == 200
    assert w.get("max", f"/shares/resource/story/{rid}").status_code == 404


def test_claim_is_a_conditional_update_not_check_then_act(team):
    """A revoke that lands BETWEEN the read of the invitation and the claim must win: the claim is `UPDATE ... WHERE status = pending`,
    so it affects no row, no membership is created and the revoked invitation stays revoked (deterministic interleaving, no threads)."""
    from sqlalchemy import event, text

    w, wa, _wb = team
    w.post("alice", f"/workspaces/{wa}/invite", {"email": "ivan@x.com"})
    repo = WorkspaceRepository(w.repo.session_factory)
    inv = repo.list_invitations_for_workspace(wa)[0]
    engine = w.repo.session_factory.kw["bind"]
    fired = []

    def interleave(conn, cursor, statement, parameters, context, executemany):
        # the repository has just read the (pending) invitation and is about to load the workspace: no cursor is open, no lock is held
        if not fired and statement.lstrip().upper().startswith("SELECT") and re.search(r"FROM workspaces\s+WHERE", statement):
            fired.append(1)
            with engine.begin() as other:       # a second connection: the owner revokes right now
                other.execute(text("UPDATE workspace_invitations SET status = 'revoked' WHERE id = :i"), {"i": inv["id"]})

    event.listen(engine, "before_cursor_execute", interleave)
    try:
        outcome, _ = repo.decide_invitation(invitation_id=inv["id"], user_id=w.u["ivan"]["uid"], email="ivan@x.com", accept=True)
    finally:
        event.remove(engine, "before_cursor_execute", interleave)
    assert fired, "the interleaving hook never ran"
    assert outcome == "used"
    assert repo.member_role(wa, w.u["ivan"]["uid"]) is None
    with w.repo.session_factory() as s:
        assert s.get(P.WorkspaceInvitation, inv["id"]).status == P.INVITATION_STATUS_REVOKED
