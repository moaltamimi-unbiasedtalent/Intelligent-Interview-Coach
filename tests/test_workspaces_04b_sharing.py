"""04B Workspaces completion (REQ-OWN-07), part 2: explicit sharing, immediate revocation, deletion correctness, audit, production.

Same harness as part 1 (``tests/_workspaces_04b_world.py``); offline, no provider, no paid call.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from src import persistence as P
from tests._auth_factories import account_repo
from tests._workspaces_04b_world import API, PW, World, build_team  # noqa: F401


@pytest.fixture(name="w")
def _world():
    world = World()
    yield world
    world.close()


@pytest.fixture(name="team")
def _team(w):
    return build_team(w)

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
    assert set(view["resource"]) == {"id", "title", "situation", "task", "action", "result", "competencies", "status", "verification", "updated_at"}   # 04A: the same fixed allow-list plus the verification LABEL (never claim, answer or Opportunity ids)
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
    tok = w.transfer("alice", wa, "mia", name="Renamed")          # 04B completion: two steps, propose then the recipient accepts
    assert w.post("mia", "/workspaces/transfers/accept", {"token": tok}).status_code == 200
    w.post("mia", f"/workspaces/{wa}/delete", {"confirm_name": "Renamed"})
    with w.repo.session_factory() as s:
        events = s.scalars(select(P.AuditEvent).where(P.AuditEvent.event_type.like("workspace.%") | P.AuditEvent.event_type.like("share.%"))).all()
        types = {e.event_type for e in events}
        blob = json.dumps([(e.event_type, e.context, e.target_id, e.target_type) for e in events], default=str)
    expected = {"workspace.created", "workspace.invite_created", "workspace.invite_accepted", "workspace.invite_revoked",
                "workspace.member_role_changed", "workspace.renamed", "workspace.member_removed", "workspace.member_left",
                "workspace.archived", "workspace.restored", "workspace.transfer_proposed", "workspace.transfer_accepted", "workspace.deleted",
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
