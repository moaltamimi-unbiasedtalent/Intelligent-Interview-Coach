"""P10B-W9.12 - documents CURRENT email-verification behaviour (product policy decision pending).

Not a requirement: if the owner later chooses to enforce verification, these tests are the ones that change.
Current behaviour: registration sends a verification email; sign-in and normal candidate use do NOT require it;
following the link marks the account verified; provider-verified (OIDC) emails are the only basis for account linking.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests._auth_factories import build_auth_app, cookies_for, login_token, register

PW = "correcthorsebattery"


def test_unverified_account_can_sign_in_and_use_candidate_features_today():
    app, _repo, mail = build_auth_app()
    with TestClient(app) as c:
        assert register(c, "new@example.com", PW).status_code in (200, 201, 202)
        assert any("verify" in m.body.lower() for m in mail.sent)           # a verification email IS sent
        token = login_token(c, "new@example.com", PW)
        assert token                                                          # sign-in does not require verification
        me = c.get("/api/v1/auth/me", cookies=cookies_for(token)).json()
        assert me["email_verified"] is False
        assert c.get("/api/v1/opportunities", cookies=cookies_for(token)).status_code == 200


def test_following_the_verification_link_marks_the_account_verified():
    app, _repo, mail = build_auth_app()
    with TestClient(app) as c:
        register(c, "v@example.com", PW)
        raw = mail.sent[-1].body.split("token=")[1].split()[0]
        assert c.post("/api/v1/auth/verify-email", json={"token": raw}).status_code == 200
        token = login_token(c, "v@example.com", PW)
        assert c.get("/api/v1/auth/me", cookies=cookies_for(token)).json()["email_verified"] is True
