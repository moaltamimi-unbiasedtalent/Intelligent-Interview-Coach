"""SEC-W10-01 reproduction (kept as a permanent regression): deactivation must end live sessions."""

from fastapi.testclient import TestClient

from tests._auth_factories import account_repo, build_auth_app, cookies_for, login_token, register

PW = "correcthorsebattery"


def test_sec_w10_01_session_survives_deactivation_repro():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "admin@x.com", PW)
        register(c, "victim@x.com", PW)
        admin_tok = login_token(c, "admin@x.com", PW)
        victim_tok = login_token(c, "victim@x.com", PW)
        accts = account_repo(repo)
        admin_id = c.get("/api/v1/auth/me", cookies=cookies_for(admin_tok)).json()["user_id"]
        victim_id = c.get("/api/v1/auth/me", cookies=cookies_for(victim_tok)).json()["user_id"]
        accts.set_platform_role(admin_id, "platform_admin")
        assert c.get("/api/v1/auth/me", cookies=cookies_for(victim_tok)).status_code == 200
        r = c.post(f"/api/v1/admin/users/{victim_id}/status", json={"status": "deactivated"},
                   cookies=cookies_for(admin_tok))
        assert r.status_code == 200
        # SEC-W10-01: the pre-deactivation session must no longer authenticate.
        assert c.get("/api/v1/auth/me", cookies=cookies_for(victim_tok)).status_code == 401
