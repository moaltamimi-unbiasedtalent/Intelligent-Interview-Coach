"""Shared world for the 04B workspace tests: a running app plus named personas (each a registered account, verified unless stated)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src import persistence as P
from src.api.rate_limit import reset_rate_limiter
from tests._auth_factories import build_auth_app, cookies_for, login_token, register, verify_email

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


def build_team(w: "World"):
    """owner(alice) + admin(adam) + member(mia) + member2(max) in workspace A; outsider(olga) in her own workspace B; ivan has no workspace."""
    for n in ("alice", "adam", "mia", "max", "olga", "ivan"):
        w.user(n)
    wa = w.workspace("alice", "Alpha")
    w.join("alice", wa, "adam", "workspace_admin")
    w.join("alice", wa, "mia")
    w.join("alice", wa, "max")
    wb = w.workspace("olga", "Bravo")
    return w, wa, wb
