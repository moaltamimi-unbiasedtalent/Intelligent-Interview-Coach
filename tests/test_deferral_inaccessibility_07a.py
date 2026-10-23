"""07A PG-10 / REQ-DEFER-01: ONE consolidated suite proving every DEFERRED or GATED feature family is unreachable for Candidates and Admins while its code-defined gate is off.

OFFLINE and DETERMINISTIC: the real FastAPI app over throwaway SQLite databases, no provider, no network (any non-loopback connect and every provider seam is recorded and fails
the test), no live credential. The families, gate constants, routes, expected refusals, UI paths and texts all come from the single table in ``tests/_deferral_table_07a.py``;
the frontend half (vitest + Playwright) reads the generated JSON mirror of that table. Nothing here enables, builds or weakens a gated feature or changes a gate value.

The suite FAILS when a new route appears under a gated prefix or keyword without being listed in the table (test_route_inventory_*), when a new gate-like constant appears in
``src`` without being classified, and when a UI route directory carrying a gated keyword is added without being listed.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import io
import re
import socket
import struct
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from src.api import rate_limit as rl
from tests import _deferral_table_07a as T
from tests._auth_factories import build_auth_app
from tests.test_admin_foundation_w10_1 import PW, Env

ROOT = Path(__file__).resolve().parents[1]
V1 = T.API
LOOPBACK = ("127.0.0.1", "::1", "localhost", "testserver")


# ---------------------------------------------------------------------------------------------------------------------------------- offline + no-provider recorder
class Calls(list):
    """Recorded provider/network calls. ``fixture`` counts invocations of the in-process FIXTURE speech engines (a fixture is not a provider: the Admin readiness probe legitimately
    exercises it), which the refused speech routes must never reach."""

    def __init__(self):
        super().__init__()
        self.fixture: list[str] = []


@pytest.fixture(autouse=True)
def provider_calls(monkeypatch):
    """Records (and fails on) every network attempt and every provider seam. The test body asserts nothing was recorded at teardown, so a swallowed error cannot hide a call."""
    calls = Calls()
    real = socket.socket.connect

    def guard(self, addr, *a, **k):
        host = addr[0] if isinstance(addr, tuple) else str(addr)
        if host not in LOOPBACK and not str(host).startswith("/"):
            calls.append(("network", str(host)))
            raise AssertionError(f"outbound network attempt to {host}")
        return real(self, addr, *a, **k)

    monkeypatch.setattr(socket.socket, "connect", guard)

    def recorder(label):
        def _rec(*a, **k):
            calls.append((label,))
            raise AssertionError(f"provider seam {label} was called")
        return _rec

    from src.billing import provider_state, stripe_provider
    from src.speech import stt_whisper, tts_kyutai
    from src.voice import realtime

    monkeypatch.setattr(stripe_provider, "build_stripe_client", recorder("stripe_client"))
    monkeypatch.setattr(provider_state.StripeStateReader, "__init__", recorder("stripe_state_reader"))
    for cls, attr in ((stt_whisper.LocalWhisperEngine, "transcribe"), (stt_whisper.OpenAIWhisperApiEngine, "transcribe"),
                      (tts_kyutai.LocalPocketTtsEngine, "synthesize"),
                      (realtime.OpenAiRealtimeProvider, "mint_session"), (realtime.FakeRealtimeProvider, "mint_session")):
        monkeypatch.setattr(cls, attr, recorder(f"{cls.__name__}.{attr}"))
    for cls, attr in ((stt_whisper.FixtureWhisperEngine, "transcribe"), (tts_kyutai.FixtureTtsEngine, "synthesize")):
        original = getattr(cls, attr)

        def counting(self, *a, _orig=original, _label=f"{cls.__name__}.{attr}", **k):
            calls.fixture.append(_label)
            return _orig(self, *a, **k)
        monkeypatch.setattr(cls, attr, counting)
    rl.reset_rate_limiter(rl.InMemoryRateLimiter())
    yield calls
    rl.reset_rate_limiter(rl.InMemoryRateLimiter())
    assert calls == [], f"a provider or network call happened: {calls}"


# ---------------------------------------------------------------------------------------------------------------------------------- personas
class World:
    """Four authenticated personas on the real app (test environment) plus the unauthenticated persona on the real app in PRODUCTION mode (fail-closed 401)."""

    def __init__(self):
        self.env = Env()
        self.c = self.env.c
        self.cookies: dict[str, dict] = {}
        self.ids: dict[str, int] = {}
        for persona, role in ((T.CAND, "user"), (T.SUPPORT, "support_operator"), (T.BILLING, "billing_admin"), (T.PLATFORM, "platform_admin")):
            self.ids[persona], self.cookies[persona] = self.env.user(role)
        app, _repo, _mail = build_auth_app("production")
        self.anon_client = TestClient(app)
        self.anon_client.__enter__()

    def close(self):
        self.anon_client.__exit__(None, None, None)
        self.env.close()

    def call(self, persona: str, route: T.Route, extra_headers: dict | None = None):
        client = self.anon_client if persona == T.ANON else self.c
        kw: dict = {"headers": {**route.headers, **(extra_headers or {})}}
        if persona != T.ANON:
            kw["cookies"] = self.cookies[persona]
        if route.upload:
            kw["files"] = {"audio": ("a.wav", wav_bytes(), "audio/wav")}
            kw["data"] = {"language": "en"}
        elif route.body is not None:
            kw["json"] = route.body
        return client.request(route.method, V1 + route.path, **kw)


def wav_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<h", 0) * 1600)
    return buf.getvalue()


@pytest.fixture(scope="module")
def world():
    w = World()
    yield w
    w.close()


def table_rows():
    return [pytest.param(f, r, id=f"{f.id}:{r.method} {r.path.split('?')[0]}") for f in T.FAMILIES for r in f.routes]


# ================================================================================ 1. the table itself and the gate constants =======================================
def _reconcile():
    spec = importlib.util.spec_from_file_location("reconcile_issues_07a", ROOT / "scripts/production/reconcile_issues.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_table_lists_each_family_exactly_once_and_every_gate_exists():
    ids = [f.id for f in T.FAMILIES]
    assert len(ids) == len(set(ids)) and set(ids) == {"billing_checkout", "stripe_webhook", "mail_delivery_webhook", "billing_reconciliation", "speech_server", "realtime_voice", "compensation_v2",
                                                       "international_sources", "history_gating", "model_profile_gating"}
    seen: set[tuple[str, str]] = set()
    for f in T.FAMILIES:
        for r in f.routes:
            key = (r.method, r.path.split("?")[0])
            assert key not in seen, f"{key} is listed twice"
            seen.add(key)
            assert set(r.expect) == set(T.PERSONAS), key


def test_every_gate_constant_is_false_reusing_the_reconciliation_check_list():
    """The reconciliation script's own GATE_CONSTANTS list is the baseline (reused, not duplicated); the table must cover all of it and may add to it."""
    rec = _reconcile()
    baseline = {tuple(x) for x in rec.GATE_CONSTANTS}
    in_table = {g for f in T.FAMILIES for g in f.gates}
    assert baseline <= in_table, f"a reconciliation gate is not assigned to any family: {sorted(baseline - in_table)}"
    for module, name in sorted(baseline | in_table | set(T.ADDITIONAL_GATES)):
        assert getattr(importlib.import_module(module), name) is False, f"{module}.{name} is not False: every deferral that relies on it is invalid"


def _module_level_bool_constants() -> dict[tuple[str, str], bool]:
    found: dict[tuple[str, str], bool] = {}
    for path in sorted((ROOT / "src").rglob("*.py")):
        module = ".".join(path.relative_to(ROOT).with_suffix("").parts)
        if module.endswith(".__init__"):
            module = module[: -len(".__init__")]
        for node in ast.parse(path.read_text()).body:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            value = getattr(node, "value", None)
            if isinstance(value, ast.Constant) and isinstance(value.value, bool):
                for t in targets:
                    if isinstance(t, ast.Name) and T.GATE_NAME_PATTERN.match(t.id):
                        found[(module, t.id)] = value.value
    return found


def test_a_new_gate_like_constant_must_be_classified_and_false():
    """Discovery scan: every module-level boolean named *_ENFORCED / *_AUTHORIZED / *_ENABLED / *_APPROVED in src is a gate. A new one fails here until it is added to a family or
    ADDITIONAL_GATES (so the deferral evidence cannot silently miss a gate), and a True one fails outright."""
    rec = _reconcile()
    known = {tuple(x) for x in rec.GATE_CONSTANTS} | {g for f in T.FAMILIES for g in f.gates} | set(T.ADDITIONAL_GATES) | set(T.SAFETY_CONTROLS_ON)
    found = _module_level_bool_constants()
    assert found, "the scan found no gate constants: the scanner is broken"
    unclassified = sorted(set(found) - known)
    assert not unclassified, f"unclassified gate-like constants (add them to tests/_deferral_table_07a.py): {unclassified}"
    assert not [k for k, v in found.items() if v is not False and k not in T.SAFETY_CONTROLS_ON], f"a gate-like constant is True: {[k for k, v in found.items() if v is not False and k not in T.SAFETY_CONTROLS_ON]}"
    assert all(found[k] is True for k in T.SAFETY_CONTROLS_ON), "a safety control that must stay ON was switched off"
    assert known <= set(found), f"the table names a gate constant that does not exist: {sorted(known - set(found))}"


def test_the_frontend_json_mirror_is_generated_from_the_table():
    assert T.MIRROR.read_text() == T.render_json(), "regenerate with: python -m tests._deferral_table_07a --write"


# ================================================================================ 2. route-inventory guard (fails on an unlisted route) ===========================
def _openapi_routes(app) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for path, ops in app.openapi()["paths"].items():
        rel = path[len(V1):] if path.startswith(V1) else path
        for method in ops:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                out.add((method.upper(), re.sub(r"\{[^}]+\}", "{}", rel)))
    return out


def _is_gated(path: str) -> bool:
    if path in T.GATED_PATH_COINCIDENCE:
        return False
    if path.startswith(T.GATED_PATH_PREFIXES):
        return True
    segments = {tok for seg in path.strip("/").split("/") for tok in {seg, *seg.split("-")}}
    return bool(segments & T.GATED_PATH_TOKENS)


def _normalise(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def _listed_normalised() -> set[tuple[str, str]]:
    listed: set[tuple[str, str]] = set()
    for method, path in T.all_listed_routes():
        # table paths use a concrete unknown id where the route has a parameter: map them back to the OpenAPI template by position
        listed.add((method, path))
    return listed


def _template_of(path: str, templates: set[str]) -> str | None:
    """Match a concrete table path ('/admin/billing/invoices/deferral07a-unknown') to its OpenAPI template ('/admin/billing/invoices/{}')."""
    if path in templates:
        return path
    parts = path.strip("/").split("/")
    for tpl in templates:
        tparts = tpl.strip("/").split("/")
        if len(tparts) == len(parts) and all(t == "{}" or t == p for t, p in zip(tparts, parts)):
            return tpl
    return None


def test_route_inventory_every_gated_route_is_listed_and_every_listed_route_exists():
    from src.api.main import create_app

    app = create_app()
    actual = _openapi_routes(app)
    templates = {p for _m, p in actual}
    listed = {(m, _template_of(p, templates) or p) for m, p in _listed_normalised()}
    gated_actual = {(m, p) for m, p in actual if _is_gated(p)}
    unlisted = sorted(gated_actual - listed)
    assert not unlisted, f"routes under a gated prefix or keyword are not listed in tests/_deferral_table_07a.py (list them with their documented refusal): {unlisted}"
    ghosts = sorted(listed - actual)
    assert not ghosts, f"the table lists routes that do not exist: {ghosts}"
    assert gated_actual, "the guard matched no route: its tokens are broken"


def test_the_route_inventory_guard_really_fails_for_a_new_gated_route():
    """Self-test of the guard: a route added under a gated prefix (and one under a gated keyword) is detected as unlisted."""
    from fastapi import APIRouter

    from src.api.main import create_app

    app = create_app()
    extra = APIRouter()
    extra.add_api_route("/billing/portal-session", lambda: {}, methods=["POST"])
    extra.add_api_route("/admin/stripe/sync", lambda: {}, methods=["POST"])
    extra.add_api_route("/compensation/benchmarks", lambda: {}, methods=["GET"])
    extra.add_api_route("/ordinary-new-feature", lambda: {}, methods=["GET"])
    app.include_router(extra, prefix=V1)
    actual = _openapi_routes(app)
    templates = {p for _m, p in actual}
    listed = {(m, _template_of(p, templates) or p) for m, p in _listed_normalised()}
    unlisted = {(m, p) for m, p in actual if _is_gated(p)} - listed
    assert {("POST", "/billing/portal-session"), ("POST", "/admin/stripe/sync"), ("GET", "/compensation/benchmarks")} <= unlisted
    assert ("GET", "/ordinary-new-feature") not in unlisted


@pytest.mark.parametrize("family", [f for f in T.FAMILIES if f.forbidden_prefixes], ids=lambda f: f.id)
def test_families_without_an_api_have_no_route_under_their_prefixes(family):
    from src.api.main import create_app

    paths = {p for _m, p in _openapi_routes(create_app())}
    for prefix in family.forbidden_prefixes:
        assert not [p for p in paths if p == prefix or p.startswith(prefix + "/")], f"{family.id}: a route exists under {prefix}"


# ================================================================================ 3. every gated route x every persona (documented refusal) ========================
@pytest.mark.parametrize("persona", T.PERSONAS)
@pytest.mark.parametrize("family,route", table_rows())
def test_each_gated_route_gives_the_documented_answer_to_each_persona(world, provider_calls, family, route, persona):
    r = world.call(persona, route)
    expected = route.expect[persona]
    assert r.status_code == expected, f"{family.id} {route.method} {route.path} as {persona}: {r.status_code} {r.text[:200]}"
    assert r.status_code < 500 or expected == 503, "a server error is never a refusal"
    assert r.status_code != 500
    body = r.text
    for pattern in route.text_absent:
        assert not re.search(pattern, body, re.I), f"{family.id} {route.path} as {persona} leaked {pattern!r}: {body[:200]}"
    assert "Traceback" not in body and "File \"" not in body
    if route.code and persona in route.code_personas and expected >= 400:
        assert r.json()["error"]["code"] == route.code, (route.path, persona, r.text[:200])
    if expected == 200 and route.json_equals:
        data = r.json()
        for key, value in route.json_equals.items():
            assert data.get(key) == value, f"{route.path} as {persona}: {key} is {data.get(key)!r}, expected {value!r}"
    assert provider_calls == []
    if route.path in ("/speech/transcriptions", "/speech/synthesis") or route.path.startswith("/voice/realtime/session"):
        assert provider_calls.fixture == [], "a refused speech route reached an engine"


def test_refusals_carry_the_stable_envelope_and_no_provider_internals(world):
    """Every 4xx/5xx the table documents uses the one safe error envelope {error: {code, message, request_id}}."""
    for family in T.FAMILIES:
        for route in family.routes:
            r = world.call(T.CAND, route)
            if r.status_code >= 400:
                err = r.json()["error"]
                assert set(err) >= {"code", "message", "request_id"} and r.headers.get("x-request-id"), (route.path, r.text[:200])


# ================================================================================ 4. configuration can never open a gate ==========================================
@pytest.mark.parametrize("provider,stripe_env", [("mock", None), ("stripe_managed_payments", "sandbox"), ("stripe_managed_payments", "live"), ("not-a-provider", None)])
def test_configuring_a_billing_provider_does_not_open_checkout(world, monkeypatch, provider_calls, provider, stripe_env):
    monkeypatch.setenv("BILLING_PROVIDER", provider)
    if stripe_env:
        monkeypatch.setenv("STRIPE_ENVIRONMENT", stripe_env)
    route = next(r for f in T.FAMILIES for r in f.routes if r.path == "/billing/checkout-sessions")
    for persona in (T.CAND, T.PLATFORM):
        r = world.call(persona, route)
        assert r.status_code == 503, (provider, stripe_env, persona, r.status_code, r.text[:200])
        assert "checkout.stripe.com" not in r.text and "cs_test_" not in r.text
    avail = world.call(T.CAND, next(r for f in T.FAMILIES for r in f.routes if r.path.startswith("/billing/checkout/availability")))
    assert avail.json()["available"] is False
    assert provider_calls == []


def test_a_signed_looking_webhook_is_refused_before_anything_is_stored(world):
    """STRIPE_WEBHOOK_AUTHORIZED is False: even a well-formed event with a signature header is refused 503, nothing is stored or enqueued, and no secret or signature is echoed."""
    from src.persistence import BillingProviderEvent, Job

    def counts():
        with world.env.repo.session_factory() as s:
            return s.scalar(select(func.count()).select_from(BillingProviderEvent)), s.scalar(select(func.count()).select_from(Job))

    before = counts()
    body = b'{"id":"evt_deferral07a_1","object":"event","type":"customer.subscription.updated","livemode":false,"created":1800000000,"data":{"object":{"id":"sub_1"}}}'
    for sig in ("t=1800000000,v1=" + "ab" * 32, "", "garbage"):
        for persona in (T.ANON, T.CAND, T.PLATFORM):
            client = world.anon_client if persona == T.ANON else world.c
            r = client.post(f"{V1}/billing/webhooks/stripe", content=body, headers={"stripe-signature": sig, "content-type": "application/json"},
                            cookies=world.cookies.get(persona, {}))
            assert r.status_code == 503 and "evt_deferral07a_1" not in r.text
            assert not sig or sig not in r.text
    assert counts() == before


def test_the_reconcile_scheduler_enqueues_nothing_and_the_runtime_reader_is_null(world):
    from src.billing import policy as P
    from src.billing import provider_state
    from src.billing.scheduler import schedule_tick
    from src.jobs.service import JobService
    from src.persistence import Job

    sf = world.env.repo.session_factory
    assert schedule_tick(sf, JobService(sf), reader_available=True)["reason"] == "scheduler_disabled"      # the default comes from the code constant
    assert schedule_tick(sf, JobService(sf), reader_available=True, enabled=False)["scheduled"] is False
    with sf() as s:
        assert s.scalar(select(func.count()).select_from(Job).where(Job.job_type == P.JOB_PROVIDER_RECONCILE)) == 0
    assert isinstance(provider_state.build_runtime_reader(), provider_state.NullStateReader)
    with pytest.raises(provider_state.ProviderStateConfiguration) as exc:
        provider_state.build_authorized_reader(None, "sandbox")
    assert "not_authorized" in str(exc.value)


def test_no_application_code_builds_a_real_provider_reader_or_stripe_client():
    """Static: the only code that may construct StripeStateReader / call build_authorized_reader / build_stripe_client lives in the billing provider modules (a wiring added
    elsewhere would let configuration alone open a provider seam)."""
    allowed = {"src/billing/provider_state.py", "src/billing/stripe_provider.py"}
    offenders = []
    for path in (ROOT / "src").rglob("*.py"):
        rel = str(path.relative_to(ROOT))
        if rel in allowed:
            continue
        text = path.read_text()
        if re.search(r"\b(StripeStateReader\(|build_authorized_reader\(|build_stripe_client\()", text):
            offenders.append(rel)
    assert offenders == [], offenders


def test_admin_recovery_after_step_up_is_refused_because_the_reader_is_null_and_calls_nothing(world, provider_calls):
    """The authorised Admin path to the gated provider reads: with a fresh step-up the recovery actions are still refused (reader_unavailable or not found), never executed."""
    from src.persistence import BillingProviderLink, Job

    ops = f"{V1}/admin/billing/operations"
    for persona in (T.BILLING, T.PLATFORM):
        ck = world.cookies[persona]
        up = world.c.post(f"{ops}/step-up", json={"password": PW}, cookies=ck)
        assert up.status_code == 200 and up.json()["elevated"] is True
        for i, tail in enumerate(("events/deferral07a-unknown/retry", "events/deferral07a-unknown/requeue", "subscriptions/deferral07a-unknown/reconcile")):
            r = world.c.post(f"{ops}/{tail}", json={"reason": "operator check 07a"}, headers={"Idempotency-Key": f"deferral07a-{persona}-{i:02d}0001"}, cookies=ck)
            assert r.status_code in (200, 404, 409, 422), (persona, tail, r.status_code, r.text[:200])
            if r.status_code == 200:
                assert r.json()["status"] == "refused" and r.json()["result"] in ("reader_unavailable", "not_found"), r.text[:200]
    with world.env.repo.session_factory() as s:
        assert s.scalar(select(func.count()).select_from(BillingProviderLink)) == 0
        assert s.scalar(select(func.count()).select_from(Job).where(Job.job_type.like("billing_%"))) == 0
    assert provider_calls == []


def test_admin_speech_selection_is_recorded_but_never_makes_server_speech_operational(world, provider_calls):
    """An authorised administrator can SELECT server speech (policy data) but the code constants still refuse: transcription and synthesis stay 503 for every persona."""
    ck = world.cookies[T.PLATFORM]
    cur = world.c.get(f"{V1}/admin/speech", cookies=ck).json()
    r = world.c.put(f"{V1}/admin/speech", cookies=ck, json={"expected_revision": cur["config"]["revision"], "reason": "07A deferral check", "stt_enabled": True, "tts_enabled": True})
    assert r.status_code == 200, r.text[:300]
    for route in next(f for f in T.FAMILIES if f.id == "speech_server").routes:
        if route.path in ("/speech/transcriptions", "/speech/synthesis"):
            for persona in (T.CAND, T.PLATFORM):
                out = world.call(persona, route)
                assert out.status_code == 503 and out.json()["error"]["code"] == "speech_unavailable"
    caps = world.c.get(f"{V1}/speech/capabilities", cookies=world.cookies[T.CAND]).json()
    assert caps["server_stt_languages"] == [] and caps["server_tts_languages"] == []
    overview = world.c.get(f"{V1}/admin/speech", cookies=ck).json()
    for leg in ("stt", "tts"):
        assert overview[leg]["operational"] is False and overview[leg]["live_authorized"] is False, overview[leg]
    assert not any(overview["authorization"].values()), overview["authorization"]
    assert provider_calls == []


def test_realtime_voice_stays_unavailable_when_enabled_without_a_provider_key(world, monkeypatch):
    """The flag alone (no key) never mints a session; a configured-but-keyless deployment answers 503 with the turn-based fallback. (The realtime family has NO code constant: see the evidence.)"""
    monkeypatch.setenv("REALTIME_VOICE_ENABLED", "true")
    monkeypatch.delenv("REALTIME_VOICE_API_KEY", raising=False)
    status = world.c.get(f"{V1}/voice/realtime/status", cookies=world.cookies[T.CAND]).json()
    assert status["available"] is False and status["fallback"] == "turn_based_voice"
    r = world.c.post(f"{V1}/voice/realtime/session", json={"locale": "en", "surface": "practice"}, cookies=world.cookies[T.CAND])
    assert r.status_code == 503
    caps = world.c.get("/api/capabilities")
    assert caps.status_code == 200 and caps.json()["realtime_voice_enabled"] is False


# ================================================================================ 5. history and model-profile gating behave as "not live" =====================
def test_history_window_is_not_applied_to_any_persona_while_the_gate_is_off(world):
    from tests.test_history_entitlements_p2b import seed

    uid, ck = world.ids[T.CAND], world.cookies[T.CAND]
    ids = seed(world.env, uid, 6, prefix="d07a")
    r = world.c.get(f"{V1}/history/interviews", cookies=ck).json()
    assert r["access"] == {"restricted": False, "window": None, "hidden_count": 0}
    assert sorted(i["id"] for i in r["interviews"]) == sorted(ids)
    oldest = world.c.get(f"{V1}/history/interviews/{ids[0]}", cookies=ck)
    assert oldest.status_code == 200                                          # nothing is hidden, nothing is "history_not_available"
    foreign = world.c.get(f"{V1}/history/interviews/{ids[0]}", cookies=world.cookies[T.SUPPORT])
    assert foreign.status_code == 404                                         # ownership isolation is unaffected by the gate


def test_practice_model_profile_selector_is_refused_while_the_gate_is_off_and_calls_no_provider():
    from tests.test_model_profile_entitlements_p2c import Plans, RecordingDomain, create, practice_client

    domain = RecordingDomain()
    c = practice_client(Plans(), domain)
    for profile in ("fast", "advanced"):
        r = create(c, 1, model_profile=profile)
        assert r.status_code == 422 and r.json()["error"]["code"] == "model_profile_not_available"
    assert domain.calls == []


# ================================================================================ 6. Compensation V2 and international sources: no API, no import, not operational
def _src_import_offenders(forbidden: tuple[str, ...]) -> list[str]:
    offenders: list[str] = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        rel = path.relative_to(ROOT)
        if rel.parts[:2] == ("src", "knowledge_foundation") or rel.as_posix() == "src/persistence.py":
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            for n in names:
                if any(n == f or n.startswith(f + ".") for f in forbidden):
                    offenders.append(f"{rel}: {n}")
    return offenders


@pytest.mark.parametrize("family", [f for f in T.FAMILIES if f.no_import_modules], ids=lambda f: f.id)
def test_no_candidate_facing_code_imports_the_deferred_knowledge_foundation(family):
    assert _src_import_offenders(family.no_import_modules) == []


def test_international_and_compensation_v2_readiness_is_not_operational():
    from src.knowledge_foundation import readiness

    report = readiness.assess()
    assert report["countries"], "the readiness report lists no country"
    for code, row in report["countries"].items():
        assert row["operational_today"] is False, code
        assert row["compensation_v2_records_linkable_today"] == 0 and row["approved_compensation_v2_sources"] == 0, code


def test_capabilities_expose_no_deferred_feature_and_keep_the_seven_locales(world):
    r = world.c.get("/api/capabilities", cookies=world.cookies[T.CAND])
    assert r.status_code == 200
    data = r.json()
    assert data["realtime_voice_enabled"] is False
    assert not [k for k in data if re.search(r"compensation|international|global|billing|checkout|stripe|speech_server|salary", k)], list(data)
    assert set(data["active_candidate_locales"]) <= {"en", "de", "fr", "es", "it", "pt", "nl"} and "ru" not in data["active_candidate_locales"]


def test_deferred_locales_are_not_registered():
    from src import locales

    codes = set(locales.SUPPORTED_LOCALE_CODES)
    assert not codes & {"zh", "hi", "ar"}, "Mandarin, Hindi and Arabic are R1.3 and must not be registered"
    assert "ru" not in locales.ACTIVE_CANDIDATE_LOCALES
