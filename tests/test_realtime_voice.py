"""Capstone P7.5 / C1 realtime-voice backend tests.

Covers the session route (auth, availability/fallback, rate + concurrency bounds, the
ephemeral-secret boundary, cross-user isolation), the model-policy boundary, the capability
flag, admin metadata privacy, and the realtime module units — all with a deterministic fake
provider and ZERO paid/live calls. Also runs the offline invariant eval as a pytest.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_current_principal
from src.api.main import create_app
from src.api.routes.voice import (
    get_realtime_config,
    get_realtime_limiter,
    get_realtime_provider,
)
from src.application.authorization import Principal
from src.persistence import ACCOUNT_STATUS_ACTIVE, PLATFORM_ROLE_USER, TIER_BASIC
from src.voice.realtime import (
    FakeRealtimeProvider,
    RateLimitExceeded,
    RealtimeConfig,
    RealtimeSessionLimiter,
    RealtimeSessionRequest,
    build_realtime_provider,
    resolve_realtime_config,
)


def _principal(user_id: int = 42) -> Principal:
    return Principal(
        user_id=user_id, platform_role=PLATFORM_ROLE_USER, tier=TIER_BASIC,
        status=ACCOUNT_STATUS_ACTIVE,
    )


def _available_config() -> RealtimeConfig:
    return RealtimeConfig(
        enabled=True, provider="fake_realtime", configured=True, model="gpt-realtime",
        voice="alloy", base_url="https://example.test/v1", max_session_seconds=300,
        max_concurrent_per_user=1, idle_timeout_seconds=60, ephemeral_ttl_seconds=60,
        sessions_per_window=3, rate_window_seconds=60,
    )


def _client(*, provider, config=None, limiter=None, user_id=42) -> TestClient:
    app = create_app()
    cfg = config or _available_config()
    app.dependency_overrides[get_current_principal] = lambda: _principal(user_id)
    app.dependency_overrides[get_realtime_config] = lambda: cfg
    app.dependency_overrides[get_realtime_provider] = lambda: provider
    app.dependency_overrides[get_realtime_limiter] = lambda: (
        limiter or RealtimeSessionLimiter(sessions_per_window=3, max_concurrent_per_user=1))
    return TestClient(app)


# ---- Session route -----------------------------------------------------------------------


def test_session_mints_ephemeral_secret_and_never_leaks_server_key():
    provider = FakeRealtimeProvider(config=_available_config())
    client = _client(provider=provider)
    resp = client.post("/api/v1/voice/realtime/session", json={"locale": "de", "surface": "practice"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Ephemeral secret is present and obviously ephemeral (the fake marks it so).
    assert body["client_secret"].startswith("ephemeral-fake")
    # The long-lived key is NEVER in the response, under any field name.
    flat = " ".join(str(v).lower() for v in body.values())
    for forbidden in ("api_key", "bearer", "sk-", "secret_key"):
        assert forbidden not in flat
    # Server-authoritative model/voice; language preference honoured (primary subtag).
    assert body["model"] == "gpt-realtime" and body["voice"] == "alloy"
    assert body["locale"] == "de"


def test_session_route_is_guarded_by_authenticated_principal():
    # The route must resolve the authenticated principal (user-scoped sessions). Assert the
    # dependency is wired without needing a DB, by inspecting the endpoint signature.
    import inspect

    from src.api.routes.voice import create_realtime_session, end_realtime_session

    for fn in (create_realtime_session, end_realtime_session):
        params = inspect.signature(fn).parameters
        dep = params["principal"].default
        assert getattr(dep, "dependency", None) is get_current_principal


def test_unavailable_returns_503_for_fallback():
    client = _client(provider=None, config=RealtimeConfig(
        enabled=False, provider="openai_realtime", configured=False, model="gpt-realtime",
        voice="alloy", base_url="x", max_session_seconds=300, max_concurrent_per_user=1,
        idle_timeout_seconds=60, ephemeral_ttl_seconds=60, sessions_per_window=3,
        rate_window_seconds=60))
    resp = client.post("/api/v1/voice/realtime/session", json={})
    assert resp.status_code == 503
    # A calm, fallback-oriented message (never a dead end).
    assert "turn-based" in resp.text.lower()


def test_rate_limit_and_concurrency_bound():
    limiter = RealtimeSessionLimiter(sessions_per_window=2, max_concurrent_per_user=5)
    provider = FakeRealtimeProvider(config=_available_config())
    client = _client(provider=provider, limiter=limiter)
    assert client.post("/api/v1/voice/realtime/session", json={}).status_code == 200
    assert client.post("/api/v1/voice/realtime/session", json={}).status_code == 200
    # Third within the window → 429.
    assert client.post("/api/v1/voice/realtime/session", json={}).status_code == 429


def test_end_session_releases_reservation():
    limiter = RealtimeSessionLimiter(sessions_per_window=10, max_concurrent_per_user=1)
    provider = FakeRealtimeProvider(config=_available_config())
    client = _client(provider=provider, limiter=limiter)
    assert client.post("/api/v1/voice/realtime/session", json={}).status_code == 200
    # Concurrency now full → next is 429 …
    assert client.post("/api/v1/voice/realtime/session", json={}).status_code == 429
    # … until the session ends and releases the reservation.
    assert client.post("/api/v1/voice/realtime/session/end").status_code == 200
    assert client.post("/api/v1/voice/realtime/session", json={}).status_code == 200


def test_status_endpoint_is_booleans_only():
    client = _client(provider=FakeRealtimeProvider(config=_available_config()))
    resp = client.get("/api/v1/voice/realtime/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True and body["fallback"] == "turn_based_voice"
    assert set(body["supported_locales"]) == {"en", "de", "fr", "es", "it", "pt", "nl"}
    # No secret leaks in status.
    assert "client_secret" not in body and "api_key" not in body


# ---- Cross-user isolation ----------------------------------------------------------------


def test_limiter_is_per_user():
    limiter = RealtimeSessionLimiter(sessions_per_window=1, max_concurrent_per_user=1)
    limiter.check_and_reserve(1)
    with pytest.raises(RateLimitExceeded):
        limiter.check_and_reserve(1)
    # A different user is unaffected — sessions are user-scoped.
    limiter.check_and_reserve(2)


# ---- Model-policy boundary ---------------------------------------------------------------


def test_realtime_policy_resolves_to_no_chat_slug():
    from src.llm.policy import ModelCapability, ModelOperation, resolve_policy

    p = resolve_policy(ModelOperation.REALTIME_VOICE, None)
    assert p.capability is ModelCapability.REALTIME
    assert p.model_id is None  # never an OpenRouter chat tier
    assert p.uses_model is True
    # A client can never smuggle a raw slug: resolve_policy only accepts an operation + profile.
    with pytest.raises(ValueError):
        resolve_policy("gpt-realtime", None)


# ---- Capability flag ---------------------------------------------------------------------


def test_capability_flag_off_by_default(monkeypatch):
    for var in ("REALTIME_VOICE_ENABLED", "REALTIME_VOICE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    from src.api.routes.health import capabilities

    assert capabilities().realtime_voice_enabled is False


def test_capability_flag_requires_flag_and_key(monkeypatch):
    from src.api.routes.health import capabilities

    monkeypatch.setenv("REALTIME_VOICE_ENABLED", "true")
    monkeypatch.delenv("REALTIME_VOICE_API_KEY", raising=False)
    assert capabilities().realtime_voice_enabled is False  # flag on but no key → unavailable
    monkeypatch.setenv("REALTIME_VOICE_API_KEY", "sk-test-not-real")
    assert capabilities().realtime_voice_enabled is True


# ---- Admin metadata privacy --------------------------------------------------------------


def test_admin_realtime_metadata_is_booleans_only():
    from src.api.routes.admin import _realtime_provider_status

    meta = _realtime_provider_status()
    assert meta["audio_visible_to_admin"] is False
    assert meta["transcript_visible_to_admin"] is False
    assert meta["live_validation"] == "NOT_RUN"
    # No secret-ish keys leak.
    for k in meta:
        assert "key" not in k.lower() and "secret" not in k.lower()


# ---- Realtime module units ---------------------------------------------------------------


def test_build_provider_none_when_unconfigured(monkeypatch):
    for var in ("REALTIME_VOICE_ENABLED", "REALTIME_VOICE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert build_realtime_provider(resolve_realtime_config()) is None


def test_locale_coerced_to_supported():
    grant = FakeRealtimeProvider().mint_session(
        RealtimeSessionRequest(user_id=1, locale="zh-CN"))
    assert grant.locale == "en"  # unsupported → coerced to en (never a geography change)


def test_config_safe_dict_has_no_secret():
    d = _available_config().safe_dict()
    assert "api_key" not in d and "client_secret" not in d
    assert d["configured"] is True and d["available"] is True


# ---- Offline invariant eval as a pytest --------------------------------------------------


def test_realtime_eval_invariants_pass():
    from scripts.eval_realtime_voice import run

    results = run()
    failed = {k: v for k, v in results.items() if not v[0]}
    assert not failed, f"realtime eval invariants failed: {failed}"
