"""Ownership-transfer notices use the normal configured origin, never request hosts."""

import logging
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select

from src import persistence as P
from src.ownership_transfer_repository import hash_token, transfer_email_hash
from tests._workspaces_04b_world import API, World


def _require(condition: bool, category: str) -> None:
    """Keep notice URLs, tokens and addresses out of assertion failure output."""
    if not condition:
        pytest.fail(category, pytrace=False)


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Host": "untrusted.example.test"},
        {
            "X-Forwarded-Host": "untrusted.example.test",
            "X-Forwarded-Proto": "http",
            "Forwarded": "host=untrusted.example.test;proto=http",
        },
    ],
    ids=["configured-origin", "host-cannot-override", "forwarded-host-cannot-override"],
)
def test_transfer_notice_uses_configured_origin_and_preserves_pending_privacy(
    monkeypatch, caplog, headers
):
    monkeypatch.setenv("APP_BASE_URL", "  https://configured.example.test:9443///  ")
    monkeypatch.setenv("FRONTEND_ORIGINS", "https://other.example.test")
    world = World()
    try:
        owner = world.user("owner")
        recipient = world.user("recipient")
        wid = world.workspace("owner")
        world.join("owner", wid, "recipient")
        _require(world.step_up("owner").status_code == 200, "owner_step_up_required")

        caplog.clear()
        caplog.set_level(logging.DEBUG)
        mail_count = len(world.mail.sent)
        response = world.c.post(
            f"{API}/workspaces/{wid}/transfer",
            json={
                "new_owner_user_id": recipient["uid"],
                "confirm_name": "Alpha",
                "former_owner_role": P.WORKSPACE_ROLE_MEMBER,
            },
            cookies=owner["ck"],
            headers=headers,
        )
        _require(response.status_code == 200, "proposal_must_succeed")
        body = response.json()
        _require(body.get("status") == "pending", "proposal_must_remain_pending")
        _require(body.get("email_delivery") == "submitted", "notice_must_be_submitted")
        _require("token" not in response.text.lower(), "response_must_not_contain_token_field")

        captured = world.mail.sent[mail_count:]
        _require(len(captured) == 1, "exactly_one_notice_required")
        message = captured[0]
        _require(message.category == "ownership_transfer", "transfer_notice_category_required")
        _require(message.to == recipient["email"], "notice_must_be_recipient_bound")
        links = [
            line.strip()
            for line in message.body.splitlines()
            if "/workspaces/transfer/accept?" in line
        ]
        _require(len(links) == 1, "exactly_one_transfer_link_required")
        parsed = urlsplit(links[0])
        _require(
            (parsed.scheme, parsed.netloc, parsed.path)
            == ("https", "configured.example.test:9443", "/workspaces/transfer/accept"),
            "notice_must_use_configured_origin_and_exact_path",
        )
        query = parse_qs(parsed.query)
        _require(set(query) == {"token"}, "notice_must_use_existing_token_contract")
        _require(len(query["token"]) == 1 and bool(query["token"][0]), "one_token_required")
        token = query["token"][0]
        _require(not parsed.fragment, "notice_must_not_add_fragment")
        _require(token not in response.text, "raw_token_must_not_enter_response")
        _require(token not in caplog.text, "raw_token_must_not_enter_logs")
        _require(recipient["email"] not in caplog.text, "recipient_must_not_enter_logs")

        with world.repo.session_factory() as session:
            transfers = session.scalars(
                select(P.WorkspaceOwnershipTransfer).where(
                    P.WorkspaceOwnershipTransfer.workspace_id == wid
                )
            ).all()
            _require(len(transfers) == 1, "exactly_one_transfer_must_be_persisted")
            transfer = transfers[0]
            _require(transfer.status == "pending", "persisted_proposal_must_remain_pending")
            _require(
                transfer.proposer_user_id == owner["uid"]
                and transfer.recipient_user_id == recipient["uid"],
                "persisted_transfer_must_bind_both_accounts",
            )
            _require(
                transfer.former_owner_role == P.WORKSPACE_ROLE_MEMBER,
                "explicit_former_owner_role_must_be_preserved",
            )
            _require(
                transfer.token_hash == hash_token(token) and transfer.token_hash != token,
                "only_token_hash_must_be_persisted",
            )
            _require(
                transfer.recipient_email_hash == transfer_email_hash(recipient["email"])
                and transfer.recipient_email_hash != recipient["email"],
                "recipient_address_must_be_hash_bound",
            )
            owners = session.scalars(
                select(P.WorkspaceMembership.user_id).where(
                    P.WorkspaceMembership.workspace_id == wid,
                    P.WorkspaceMembership.status == P.MEMBERSHIP_STATUS_ACTIVE,
                    P.WorkspaceMembership.role == P.WORKSPACE_ROLE_OWNER,
                )
            ).all()
            _require(owners == [owner["uid"]], "one_original_owner_must_remain_until_acceptance")
    finally:
        world.close()
