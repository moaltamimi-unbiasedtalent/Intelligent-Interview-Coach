"""07A engineering hygiene: blocking calls inside ``async def`` (they stall the event loop that serves every other request).

Two independent proofs, both offline and deterministic:

1. STATIC (AST): no ``async def`` in ``src`` calls a blocking primitive or a known blocking project seam directly. Work is offloaded with ``run_in_threadpool`` / an executor (a
   nested function, a lambda or a callable passed as an argument is not a direct call, so offloaded work is not flagged). There is NO allow-list: a new offender fails the suite
   and must be fixed, never suppressed. The scanner is itself tested on source that reproduces each pre-fix pattern.
2. BEHAVIOURAL: for every offender 07A found and fixed, the real route (or middleware) is driven through the real ASGI app while the blocking dependency is replaced by a
   deliberate 0.4 s ``time.sleep``; a monitor coroutine measures the longest event-loop stall. Offloaded work leaves the loop free (stall well under 0.3 s); the pre-fix code stalls
   for the full 0.4 s.
"""

from __future__ import annotations

import ast
import asyncio
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from tests.test_admin_foundation_w10_1 import PW, Env  # noqa: F401  (PW re-exported for readers)

ROOT = Path(__file__).resolve().parents[1]
BLOCK_SECONDS = 0.4
STALL_LIMIT = 0.3

# ---------------------------------------------------------------------------------------------------------------------------------------------------- the scanner
# (owner module, attribute) pairs that block: matched on the call's owner name and attribute, so `str.join` or `dict.get` never match.
BLOCKING_ATTRS = {
    ("time", "sleep"), ("os", "system"), ("subprocess", "run"), ("subprocess", "call"), ("subprocess", "check_call"), ("subprocess", "check_output"), ("subprocess", "Popen"),
    ("requests", "get"), ("requests", "post"), ("requests", "put"), ("requests", "delete"), ("requests", "request"), ("urllib.request", "urlopen"), ("request", "urlopen"),
    ("socket", "create_connection"), ("sqlite3", "connect"), ("shutil", "copy"), ("shutil", "copyfile"), ("shutil", "rmtree"), ("shutil", "move"),
    ("httpx", "get"), ("httpx", "post"), ("httpx", "put"), ("httpx", "delete"), ("httpx", "request"),
}
# Any attribute call with one of these names (pathlib / file-like blocking IO and lock/semaphore waits) unless it is awaited.
BLOCKING_ANY_OWNER = {"read_text", "write_text", "read_bytes", "write_bytes", "acquire", "__exit__", "__enter__", "commit", "executescript"}
# Plain names of blocking project seams (database reads, rate limiter, malware scan, recorders, store/runtime work).
BLOCKING_NAMES = {"open", "enforce", "ensure_not_paused", "enforce_scan", "_scan_or_reject", "record_event", "admit", "sleep"}
# Objects whose methods are synchronous service, repository, store or engine calls in this codebase.
BLOCKING_OWNER_OBJECTS = {"svc", "service", "runtime", "repo", "repository", "receiver", "store", "pause", "limiter", "ops", "audit_repo", "stepup", "step_up", "session_factory", "sf",
                          "engine", "provider"}


def _owner_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_owner_name(node.value)}.{node.attr}"
    return ""


class _AsyncScanner(ast.NodeVisitor):
    """Collects blocking direct calls in the body of one async function (nested defs and lambdas are separate scopes: offloaded callables live there)."""

    def __init__(self) -> None:
        self.hits: list[tuple[int, str]] = []
        self._awaited: set[int] = set()

    def visit_FunctionDef(self, node):  # noqa: N802 - a nested sync function is a callable to be offloaded, not code running on the loop
        return

    visit_AsyncFunctionDef = visit_FunctionDef  # nested async defs are scanned as their own functions by the module walk
    visit_Lambda = visit_FunctionDef

    def visit_Await(self, node):  # noqa: N802
        if isinstance(node.value, ast.Call):
            self._awaited.add(id(node.value))
        self.generic_visit(node)

    def visit_Call(self, node):  # noqa: N802
        fn = node.func
        label = None
        if isinstance(fn, ast.Name):
            if fn.id in BLOCKING_NAMES:
                label = fn.id
        elif isinstance(fn, ast.Attribute):
            owner = _owner_name(fn.value)
            if (owner, fn.attr) in BLOCKING_ATTRS:
                label = f"{owner}.{fn.attr}"
            elif fn.attr in BLOCKING_ANY_OWNER and id(node) not in self._awaited:
                label = f"{owner}.{fn.attr}"
            elif owner.split(".")[0] in BLOCKING_OWNER_OBJECTS and id(node) not in self._awaited:
                label = f"{owner}.{fn.attr}"
        if label is not None and id(node) not in self._awaited:
            self.hits.append((node.lineno, label))
        self.generic_visit(node)


def blocking_calls_in_source(source: str) -> list[tuple[str, int, str]]:
    """(async function name, line, call) for every blocking direct call inside an async function of ``source``."""
    out: list[tuple[str, int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.AsyncFunctionDef):
            scanner = _AsyncScanner()
            for stmt in node.body:
                scanner.visit(stmt)
            out += [(node.name, line, label) for line, label in scanner.hits]
    return out


def async_function_count(source: str) -> int:
    return sum(isinstance(n, ast.AsyncFunctionDef) for n in ast.walk(ast.parse(source)))


def test_no_async_function_in_src_calls_a_blocking_primitive_directly():
    offenders: list[str] = []
    scanned = 0
    for path in sorted((ROOT / "src").rglob("*.py")):
        text = path.read_text()
        scanned += async_function_count(text)
        for func, line, label in blocking_calls_in_source(text):
            offenders.append(f"{path.relative_to(ROOT)}:{line} async {func}() calls {label}")
    assert scanned >= 40, f"the scanner saw only {scanned} async functions: it is not scanning src"
    assert offenders == [], "blocking calls inside async functions (offload with run_in_threadpool; do not suppress):\n" + "\n".join(offenders)


@pytest.mark.parametrize("source,expected", [
    ("async def f():\n    time.sleep(1)\n", "time.sleep"),
    ("async def f(svc):\n    return svc.upload(1)\n", "svc.upload"),
    ("async def f(pause):\n    ensure_not_paused('ocr', pause)\n", "ensure_not_paused"),
    ("async def f(user_id):\n    enforce('x', user_id)\n", "enforce"),
    ("async def f(runtime):\n    runtime.transcribe(b'')\n", "runtime.transcribe"),
    ("async def f(lease):\n    lease.__exit__(None, None, None)\n", "lease.__exit__"),
    ("async def f(self):\n    self._sem.acquire(timeout=1)\n", "self._sem.acquire"),
    ("async def f(p):\n    p.read_text()\n", "p.read_text"),
    ("async def f():\n    open('x').read()\n", "open"),
    ("async def f():\n    record_event('request', 'a', 'b', 'success')\n", "record_event"),
    ("async def f(repo):\n    with repo.session_factory() as s:\n        s.commit()\n", "repo.session_factory"),
])
def test_the_scanner_detects_each_pre_fix_pattern(source, expected):
    assert expected in {label for _f, _l, label in blocking_calls_in_source(source)}


@pytest.mark.parametrize("source", [
    "async def f(svc):\n    return await run_in_threadpool(svc.upload, 1)\n",
    "async def f(svc):\n    return await run_in_threadpool(lambda: svc.upload(1))\n",
    "async def f(svc):\n    def work():\n        return svc.upload(1)\n    return await run_in_threadpool(work)\n",
    "async def f(loop, sem):\n    return await loop.run_in_executor(None, lambda: sem.acquire(timeout=1))\n",
    "async def f(request):\n    data = await request.json()\n    return ', '.join(data)\n",
    "async def f(client):\n    return await client.get('x')\n",
])
def test_the_scanner_accepts_offloaded_and_awaited_work(source):
    assert blocking_calls_in_source(source) == []


# ---------------------------------------------------------------------------------------------------------------------------------------------------- behavioural proof
async def _measure(request_coro):
    """Run ``request_coro`` while a monitor coroutine records the longest event-loop stall (gap above its own 10 ms tick)."""
    gaps: list[float] = []
    done = False

    async def monitor():
        last = time.perf_counter()
        while not done:
            await asyncio.sleep(0.01)
            now = time.perf_counter()
            gaps.append(now - last - 0.01)
            last = now

    task = asyncio.create_task(monitor())
    await asyncio.sleep(0.03)                                  # let the monitor start ticking before the work under test begins
    try:
        result = await request_coro
    finally:
        done = True
        await task
    return result, max(gaps or [0.0])


def _slow(result=None, exc: Exception | None = None):
    """A blocking callable (what the offender used to call on the loop): holds its thread for BLOCK_SECONDS, then returns or raises."""
    def run(*a, **k):
        time.sleep(BLOCK_SECONDS)
        if exc is not None:
            raise exc
        return result
    return run


class AsyncWorld:
    def __init__(self):
        self.env = Env()
        self.cookies = {role: self.env.user(role)[1] for role in ("platform_admin", "knowledge_admin")}

    async def request(self, method, path, *, role=None, **kw):
        app = self.env.app
        transport = httpx.ASGITransport(app=app)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                cookies = self.cookies[role] if role else None
                return await client.request(method, "/api/v1" + path, cookies=cookies, **kw)

    def close(self):
        self.env.close()


@pytest.fixture(scope="module")
def aw():
    w = AsyncWorld()
    yield w
    w.close()


@pytest.fixture(autouse=True)
def _fresh_limiter():
    from src.api import rate_limit as rl

    rl.reset_rate_limiter(rl.InMemoryRateLimiter())
    yield
    rl.reset_rate_limiter(rl.InMemoryRateLimiter())


def stall_of(aw: AsyncWorld, method: str, path: str, **kw) -> tuple[httpx.Response, float]:
    return asyncio.run(_measure(aw.request(method, path, **kw)))


def test_speech_transcription_does_not_block_the_event_loop(aw, monkeypatch):
    from src.speech.runtime import SpeechRuntime
    from src.speech_service import SpeechError

    monkeypatch.setattr(SpeechRuntime, "transcribe", _slow(exc=SpeechError("off", category="unavailable")))
    r, stall = stall_of(aw, "POST", "/speech/transcriptions", files={"audio": ("a.wav", b"RIFF", "audio/wav")}, data={"language": "en"})
    assert r.status_code == 503 and stall < STALL_LIMIT, (r.status_code, stall)


def test_speech_limiter_does_not_block_the_event_loop(aw, monkeypatch):
    import src.api.routes.speech as speech

    monkeypatch.setattr(speech, "enforce", _slow())
    r, stall = stall_of(aw, "POST", "/speech/transcriptions", files={"audio": ("a.wav", b"RIFF", "audio/wav")}, data={"language": "en"})
    assert r.status_code == 503 and stall < STALL_LIMIT, (r.status_code, stall)


def test_stripe_webhook_limiter_does_not_block_the_event_loop(aw, monkeypatch):
    import src.api.routes.billing_webhooks as hooks

    monkeypatch.setattr(hooks, "enforce", _slow())
    r, stall = stall_of(aw, "POST", "/billing/webhooks/stripe", content=b"{}", headers={"stripe-signature": "t=1,v1=ab"})
    assert r.status_code == 503 and stall < STALL_LIMIT, (r.status_code, stall)


def test_document_upload_scan_and_processing_do_not_block_the_event_loop(aw, monkeypatch):
    import src.api.routes.documents as docs
    from src.application.documents_service import DocumentsApplicationService

    monkeypatch.setattr(docs, "_scan_or_reject", _slow())
    monkeypatch.setattr(DocumentsApplicationService, "upload", _slow(exc=RuntimeError("stop after the blocking call")))
    r, stall = stall_of(aw, "POST", "/documents", files={"file": ("cv.txt", b"hello", "text/plain")}, data={"category": "other"})
    assert stall < STALL_LIMIT, (r.status_code, stall)
    assert r.status_code in (500, 503)                                                          # the fake service raised: the point is the loop stayed free


def test_document_upload_pause_and_limiter_do_not_block_the_event_loop(aw, monkeypatch):
    import src.api.guards as guards

    monkeypatch.setattr(guards, "ensure_not_paused", _slow(exc=RuntimeError("stop")))      # the durable pause read (database) the upload admission performs
    r, stall = stall_of(aw, "POST", "/documents", files={"file": ("cv.txt", b"hello", "text/plain")}, data={"category": "other"})
    assert stall < STALL_LIMIT, (r.status_code, stall)
    r, stall = stall_of(aw, "POST", "/documents/1/replace", files={"file": ("cv.txt", b"hello", "text/plain")})
    assert stall < STALL_LIMIT, (r.status_code, stall)


def test_document_replace_does_not_block_the_event_loop(aw, monkeypatch):
    import src.api.routes.documents as docs
    from src.application.documents_service import DocumentsApplicationService

    monkeypatch.setattr(docs, "_scan_or_reject", _slow())
    monkeypatch.setattr(DocumentsApplicationService, "replace", _slow(exc=RuntimeError("stop after the blocking call")))
    r, stall = stall_of(aw, "POST", "/documents/1/replace", files={"file": ("cv.txt", b"hello", "text/plain")})
    assert stall < STALL_LIMIT, (r.status_code, stall)


def test_admin_knowledge_upload_does_not_block_the_event_loop(aw, monkeypatch):
    from src.knowledge_admin.service import KnowledgeAdminService

    monkeypatch.setattr(KnowledgeAdminService, "create_source", _slow(result={"ok": True}))
    monkeypatch.setattr(KnowledgeAdminService, "add_version", _slow(result={"ok": True}))
    form = {"language": "en", "authority_level": "1", "title": "t"}
    r, stall = stall_of(aw, "POST", "/admin/knowledge/sources", role="knowledge_admin", files={"file": ("a.txt", b"x", "text/plain")}, data=form)
    assert r.status_code == 201 and stall < STALL_LIMIT, (r.status_code, r.text[:200], stall)
    r, stall = stall_of(aw, "POST", "/admin/knowledge/sources/abc/versions", role="knowledge_admin", files={"file": ("a.txt", b"x", "text/plain")}, data=form)
    assert r.status_code == 201 and stall < STALL_LIMIT, (r.status_code, r.text[:200], stall)


@pytest.mark.parametrize("path,body", [("/admin/integrations/openrouter/credentials/api_key", {"value": "x" * 12}),
                                       ("/admin/integrations/openrouter/credentials/api_key/remove", {"confirm": True})])
def test_admin_credential_handlers_do_not_block_the_event_loop(aw, monkeypatch, path, body):
    from src.admin_security.errors import StepUpRequired
    from src.admin_security.stepup import StepUpService

    monkeypatch.setattr(StepUpService, "require", _slow(exc=StepUpRequired("Confirm your password to continue.")))
    r, stall = stall_of(aw, "POST", path, role="platform_admin", json=body)
    assert r.status_code == 403 and r.json()["error"]["code"] == "step_up_required" and stall < STALL_LIMIT, (r.status_code, r.text[:200], stall)


def test_operational_telemetry_middleware_does_not_block_the_event_loop(aw, monkeypatch):
    from src.reporting import telemetry

    telemetry.install(aw.env.repo.session_factory)
    try:
        monkeypatch.setattr(telemetry, "record_event", _slow(result=True))
        r, stall = stall_of(aw, "POST", "/voice/realtime/session", json={"locale": "en", "surface": "practice"})
    finally:
        telemetry.uninstall()
    assert r.status_code == 503 and stall < STALL_LIMIT, (r.status_code, stall)


def test_the_governed_lease_release_does_not_block_the_event_loop(monkeypatch):
    """ai_operation's dependency joins the lease-heartbeat thread on exit (up to 2 s). Driven for real with a held reservation (the quota gate stays False: the reservation is
    stubbed at the module seam), the join must run in the worker pool."""
    from src import ai_protection
    from src.application.lease import Heartbeat

    exits: list[str] = []
    monkeypatch.setattr(Heartbeat, "__exit__", lambda self, *a: (time.sleep(BLOCK_SECONDS), exits.append("exit"))[1])
    quota = SimpleNamespace(renew=lambda key: None, commit=lambda key: None, release=lambda key: None)
    monkeypatch.setattr(ai_protection, "admit", lambda *a, **k: False)
    monkeypatch.setattr(ai_protection, "_reserve_quota", lambda *a, **k: (quota, True))
    monkeypatch.setattr(ai_protection, "persist_scope", lambda *a, **k: None)
    dep = ai_protection.ai_operation("career", "chat")

    async def exercise():
        request = SimpleNamespace(headers={}, path_params={})
        gen = dep(request=request, user_id=1, pause=None, repo=SimpleNamespace(session_factory=None))
        await gen.__anext__()
        await gen.aclose()                                     # the finally block (lease release) runs here

    _r, stall = asyncio.run(_measure(exercise()))
    assert exits == ["exit"] and stall < STALL_LIMIT, (exits, stall)


def test_p10e_http_guard_waits_for_a_concurrency_slot_off_the_event_loop():
    """The paid-run guard used a blocking semaphore acquire in its async send path: with every slot held the loop froze for the full request timeout."""
    from src.p10e.errors import LiveRunRefused
    from src.p10e.httpguard import HttpGuard

    guard = HttpGuard.__new__(HttpGuard)
    guard._sem = threading.BoundedSemaphore(1)
    guard._sem.acquire()                                       # the only slot is held, as by an in-flight sync caller
    guard.limits = SimpleNamespace(request_timeout_s=BLOCK_SECONDS)
    guard._classify = lambda request: "inference"
    guard._prepare = lambda request, kw: ("model", 1, 1)

    def refuse(code, message):
        raise LiveRunRefused(code, message)

    guard._refuse = refuse

    async def go():
        request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        with pytest.raises(LiveRunRefused) as exc:
            await guard._send_async(None, None, request, {})
        return exc.value

    refused, stall = asyncio.run(_measure(go()))
    assert "concurrency limit is saturated" in str(refused) and stall < STALL_LIMIT, (refused.args, stall)
