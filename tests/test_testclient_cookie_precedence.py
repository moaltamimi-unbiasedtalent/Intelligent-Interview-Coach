"""Regression guard for the CI failure of PR #212: the test harness must treat a per-request cookie as THE credential for that request.

Root cause (reproduced with a minimal Starlette app, no Ask4Mo code): when a TestClient holds a cookie in its jar and a request also passes ``cookies=`` with the same
name, httpx sends BOTH values in one ``Cookie`` header and the server keeps the last. starlette 1.3 emitted ``jar; per-request`` and 1.9 emits ``per-request; jar``,
so on a fresh install every "act as user A while the jar holds user B" check silently acted as B (the identity evaluator's cross_user_isolation fell to 0 of 3 while the
server was correct). ``tests/_client_compat.py`` (installed on import of the ``tests`` package) provides a wrapper that makes the per-request cookie authoritative on every version.
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient


def _app():
    async def login(request):
        r = JSONResponse({"ok": True})
        r.set_cookie("sess", request.query_params["who"])
        return r

    async def logout(request):
        r = JSONResponse({"ok": True})
        r.delete_cookie("sess")
        return r

    async def who(request):
        return JSONResponse({"header": request.headers.get("cookie"), "sess": request.cookies.get("sess")})

    return Starlette(routes=[Route("/login", login, methods=["POST"]), Route("/logout", logout, methods=["POST"]), Route("/who", who)])


def test_a_per_request_cookie_overrides_a_jar_cookie_of_the_same_name():
    c = TestClient(_app())
    c.post("/login?who=alice")
    c.post("/login?who=bob")                                   # the jar now holds bob, the most recent login
    out = c.get("/who", cookies={"sess": "alice"}).json()
    assert out["sess"] == "alice" and out["header"] == "sess=alice"          # exactly one value is sent, and it is the per-request one


def test_the_jar_session_is_kept_for_requests_without_a_per_request_cookie():
    c = TestClient(_app())
    c.post("/login?who=bob")
    c.get("/who", cookies={"sess": "alice"})
    assert c.get("/who").json()["sess"] == "bob"               # the override is for one request only


def test_a_cookie_the_response_deletes_or_replaces_is_not_resurrected():
    c = TestClient(_app())
    c.post("/login?who=bob")
    c.post("/logout", cookies={"sess": "bob"})                 # the server clears the cookie
    assert c.get("/who").json()["sess"] is None
    c.post("/login?who=carol")
    c.get("/who", cookies={"sess": "dave"})
    assert c.get("/who").json()["sess"] == "carol"


def test_two_users_on_one_client_stay_isolated_through_the_real_identity_stack():
    """The exact shape of the identity evaluator's cross-user check, against the real application (no provider)."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("eval_identity_platform", Path(__file__).resolve().parents[1] / "scripts/eval_identity_platform.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    metrics = mod.run()
    assert metrics["cross_user_isolation"] == (3, 3)
