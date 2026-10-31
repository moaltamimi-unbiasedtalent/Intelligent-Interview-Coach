"""Workspace invitation links use the configured application origin."""
from urllib.parse import parse_qs, urlsplit

from tests._workspaces_04b_world import World


def test_workspace_invitation_uses_configured_origin_and_keeps_token_private(monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "https://synthetic.example.test/")
    world = World()
    try:
        world.user("owner")
        wid = world.workspace("owner")
        response = world.post("owner", f"/workspaces/{wid}/invite", {"email": "recipient@example.test"})
        assert response.status_code == 200
        assert response.json()["email_delivery"] == "submitted"
        assert "token" not in response.text
        message = world.mail.last_for("workspace_invitation")
        link = next(line.strip() for line in message.body.splitlines() if "/workspaces/accept?" in line)
        parsed = urlsplit(link)
        assert (parsed.scheme, parsed.netloc, parsed.path) == ("https", "synthetic.example.test", "/workspaces/accept")
        token = parse_qs(parsed.query)["token"][0]
        assert token not in response.text
        with world.repo.session_factory() as session:
            from sqlalchemy import select
            from src.persistence import WorkspaceInvitation
            invitation = session.scalar(select(WorkspaceInvitation).where(WorkspaceInvitation.workspace_id == wid))
            assert invitation.token_hash != token
    finally:
        world.close()
