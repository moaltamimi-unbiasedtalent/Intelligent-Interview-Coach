"""Test-client compatibility: a per-request cookie is the credential for that request (installed on import of the ``tests`` package)."""

from __future__ import annotations

# --- Test-client cookie precedence (dependency-drift fix, 2026-10-21) -----------------------------------------------------------------------
# Many suites and evaluators sign several users in through ONE TestClient and then pass ``cookies={"ask4mo_session": token}`` per request to act as a
# specific user. httpx merges the client's cookie jar with the per-request cookies into ONE ``Cookie`` header that contains both values when they share
# a name. The order of the two values is not part of any contract: starlette's TestClient emitted ``jar; per-request`` up to 1.3 and ``per-request; jar``
# from 1.9, and the server's cookie parser keeps the LAST value, so on a fresh install the jar (the most recent login) silently overrode the user the test
# meant to act as, and every cross-user check failed (a harness artefact, proven with a minimal Starlette app; the Ask4Mo server was correct: separate
# clients return 404, 404, 200). A real browser never sends two same-name cookies for one scope. This wrapper restores the intended meaning, "a per-request
# cookie is the credential for that request", for every version: same-named jar cookies are held back for that request only and restored afterwards unless
# the response set that cookie. It changes no assertion and no application code, and it only affects tests and evaluators (which import this module first).
def _install_cookie_precedence() -> None:
    try:
        from starlette.testclient import TestClient
    except Exception:  # noqa: BLE001 - starlette is a base dependency, but never break collection over a test helper
        return
    if getattr(TestClient, "_ask4mo_cookie_precedence", False):
        return
    original = TestClient.request

    def request(self, method, url, *args, cookies=None, **kwargs):  # noqa: ANN001
        if not cookies:
            return original(self, method, url, *args, cookies=cookies, **kwargs)
        names = set(cookies.keys()) if hasattr(cookies, "keys") else {c.name for c in cookies.jar}
        held = [c for c in list(self.cookies.jar) if c.name in names]
        for c in held:
            self.cookies.jar.clear(c.domain, c.path, c.name)
        response = None
        try:
            response = original(self, method, url, *args, cookies=cookies, **kwargs)
            return response
        finally:
            touched = set()
            if response is not None:           # a Set-Cookie for the name (a new value OR a deletion) means the server decided its fate
                for header in response.headers.get_list("set-cookie"):
                    touched.add(header.split("=", 1)[0].strip())
            present = {c.name for c in self.cookies.jar}
            for c in held:
                if c.name not in present and c.name not in touched:      # untouched by the response: keep the session the client had
                    self.cookies.jar.set_cookie(c)

    TestClient.request = request
    TestClient._ask4mo_cookie_precedence = True




install = _install_cookie_precedence
install()
