"""Task 05: synthetic approvals and mocked HTTP only; no owner approval is supplied."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import multiprocessing
import os
import uuid

import httpx
import pytest
from sqlalchemy import select, text

from src.llm.budget import config as C, governor as G
from src.llm.budget.errors import BudgetError
from src.llm.budget.ledger import DbBudgetLedger
from src.llm.budget.status import budget_status
from src.persistence import AiBudgetEntry, Base, make_engine, make_session_factory
from tests.test_ai_budget_governor_05c import MODEL, MARKER, Provider, chat, raw_config


def synthetic_config():
    """TEST FIXTURE ONLY. Values are NOT a proposed or approved real budget."""
    raw = raw_config()
    raw["allowed_provider_hosts"] = ["openrouter.ai"]
    now = datetime.now(timezone.utc)
    raw["approval"] = dict(
        owner="synthetic-owner",
        approver="synthetic-approver",
        environment="staging",
        currency="USD",
        period_start=(now - timedelta(hours=1)).isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        pricing_effective_at=(now - timedelta(minutes=30)).isoformat(),
        pricing_expires_at=(now + timedelta(minutes=30)).isoformat(),
        pricing_source="https://pricing.invalid/synthetic",
        reconciliation_owner="synthetic-reviewer",
        incident_owner="synthetic-operator",
    )
    raw["total"] = {"hard_cap_usd": "5", "stop_usd": "4", "max_requests": 1000}
    raw["classes"]["production"]["categories"]["embedding"] = {
        "hard_cap_usd": ".2",
        "stop_usd": ".1",
    }
    return raw


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    G.uninstall()
    for name in ("CI", "GITHUB_ACTIONS", "AI_BUDGET_MODE", "API_ENV"):
        monkeypatch.delenv(name, raising=False)
    yield
    G.uninstall()


@pytest.fixture
def ledger(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/synthetic.db")
    Base.metadata.create_all(engine)
    yield DbBudgetLedger(make_session_factory(engine))
    engine.dispose()


def reserve(
    ledger, cfg, fingerprint=None, category="agent", klass="production", worst=100
):
    return ledger.reserve(
        cfg,
        budget_class=klass,
        category=category,
        operation=category,
        model=MODEL,
        endpoint="chat",
        fingerprint=fingerprint or uuid.uuid4().hex,
        worst_case=worst,
    )


@pytest.mark.parametrize("mode", [None, "", "off", "observe", "development"])
def test_hosted_mode_cannot_skip_enforcement(mode):
    env = {"API_ENV": "staging", **({C.MODE_ENV: mode} if mode is not None else {})}
    gov = G.install_from_env(environ=env)
    with Provider().client() as client, pytest.raises(BudgetError, match="closed"):
        chat(client)
    assert gov.closed_reason == "enforcement_required"


@pytest.mark.parametrize(
    "host", ["api.openai.com", "alternate.invalid", "openrouter.ai.evil.invalid"]
)
def test_alternate_sdk_endpoint_is_refused_before_transport(host):
    gov = G.install(
        G.BudgetGovernor.closed("config_unavailable", environ={"API_ENV": "staging"})
    )
    p = Provider()
    with p.client() as client, pytest.raises(BudgetError) as err:
        client.post(f"https://{host}/v1/chat/completions", json={})
    assert err.value.reason == "provider_host_not_allowed" and not p.requests
    assert gov is G.active_governor()


@pytest.mark.parametrize(
    "field",
    [
        "owner",
        "approver",
        "expires_at",
        "pricing_effective_at",
        "pricing_source",
        "environment",
        "currency",
        "reconciliation_owner",
        "incident_owner",
    ],
)
def test_hosted_approval_requires_each_owner_field(field):
    raw = synthetic_config()
    del raw["approval"][field]
    with pytest.raises(BudgetError, match="approval"):
        C.validate_hosted_approval(C.parse_config(raw), {"API_ENV": "staging"})


@pytest.mark.parametrize(
    "change", ["expired", "future-price", "wrong-env", "development", "no-total"]
)
def test_hosted_approval_cannot_use_expired_pricing_or_dev_class(change):
    raw = synthetic_config()
    env = {"API_ENV": "staging"}
    if change == "expired":
        raw["approval"]["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
    elif change == "future-price":
        raw["approval"]["pricing_effective_at"] = (
            datetime.now(timezone.utc) + timedelta(minutes=1)
        ).isoformat()
    elif change == "wrong-env":
        raw["approval"]["environment"] = "production"
    elif change == "development":
        env[C.CLASS_ENV] = "development"
    else:
        del raw["total"]
    with pytest.raises(BudgetError):
        C.validate_hosted_approval(C.parse_config(raw), env)


@pytest.mark.parametrize("price", ["NaN", "Infinity", "-1"])
def test_invalid_prices_refuse(price):
    raw = raw_config()
    raw["pricing"]["models"][MODEL]["prompt"] = price
    with pytest.raises(BudgetError):
        C.parse_config(raw)


@pytest.mark.parametrize("scope", ["class:production", "cat:production:agent"])
def test_corrupted_counter_blocks_new_spending(ledger, scope):
    cfg = C.parse_config(synthetic_config())
    reserve(ledger, cfg)
    with ledger._sf() as s:
        s.execute(
            text("UPDATE ai_budget_controls SET held_micro_usd=0 WHERE scope_key=:key"),
            {"key": scope},
        )
        s.commit()
    with pytest.raises(BudgetError) as err:
        reserve(ledger, cfg)
    assert err.value.reason == "ledger_inconsistent"


def test_global_concurrency_is_durable_and_restart_does_not_clear_it(ledger):
    cfg = C.parse_config(synthetic_config())
    cfg = replace(cfg, limits=replace(cfg.limits, max_concurrency=1))
    first = reserve(ledger, cfg)
    restarted = DbBudgetLedger(ledger._sf)
    with pytest.raises(BudgetError) as err:
        reserve(restarted, cfg)
    assert err.value.reason == "concurrency_limit"
    restarted.settle(first, outcome="unknown")
    assert restarted.snapshot(cfg, "production")["unknown_held_usd"] == "0.000100"
    reserve(restarted, cfg)


def test_total_across_classes_and_policy_change_cannot_reset_counters(ledger):
    raw = synthetic_config()
    raw["total"] = {"hard_cap_usd": ".00015", "stop_usd": ".00015"}
    cfg = C.parse_config(raw)
    reserve(ledger, cfg)
    with pytest.raises(BudgetError) as err:
        reserve(ledger, cfg, category="evaluation", klass="evaluation")
    assert err.value.reason == "total_stop"
    changed = C.parse_config({**raw, "total": {"hard_cap_usd": "8", "stop_usd": "7"}})
    with pytest.raises(BudgetError) as err:
        reserve(ledger, changed)
    assert err.value.reason == "policy_mismatch"


def test_unknown_is_never_automatically_retried_after_window(ledger):
    cfg = C.parse_config(raw_config())
    r = reserve(ledger, cfg, fingerprint="a" * 64)
    ledger.settle(r, outcome="unknown")
    ledger._clock = lambda: 999999999999
    with pytest.raises(BudgetError) as err:
        reserve(ledger, cfg, fingerprint="a" * 64)
    assert err.value.reason == "unknown_outcome_no_retry"


def test_reported_overrun_without_tokens_is_held_and_kills(ledger):
    cfg = C.parse_config(raw_config())
    gov = G.BudgetGovernor(cfg, ledger, "production", environ={C.MARKER_ENV: MARKER})
    G.install(gov)
    p = Provider(
        lambda request, n: httpx.Response(200, json={"usage": {"cost": "0.5"}})
    )
    chat(p.client())
    snap = gov.status()
    assert snap["state"] == "killed" and snap["unknown_held_usd"] == "0.500000"
    assert snap["integrity"]["consistent"]


def test_admin_does_not_treat_marker_presence_as_matching_approval(ledger, tmp_path):
    f = tmp_path / "synthetic.json"
    f.write_text(json.dumps(raw_config()))
    result = budget_status(
        ledger._sf, {C.CONFIG_PATH_ENV: str(f), C.MARKER_ENV: "OD-BUDGET:wrong-test"}
    )
    assert result["state"] == "not_approved" and result["reason"] == "marker_mismatch"
    assert "wrong-test" not in json.dumps(result)


def _compete(url, raw, event, queue, role, ready=None):
    """Independent API/worker-shaped processes share ONLY PostgreSQL state."""
    engine = make_engine(url)
    ledger = DbBudgetLedger(make_session_factory(engine))
    if ready is not None:
        ready.put("ready")
    event.wait(30)
    if ready is not None:
        ready.put("attempt")
    try:
        reserve(ledger, C.parse_config(raw), fingerprint=role + uuid.uuid4().hex)
        queue.put("admitted")
    except BudgetError as err:
        queue.put(err.reason)
    finally:
        engine.dispose()


@pytest.fixture
def postgres():
    if not os.environ.get("P5B_PG_ADMIN_URL"):
        pytest.skip("explicit disposable PostgreSQL 16 not configured")
    from tests.test_pg_05b import _alembic, _create_db, _drop_db, _skip_reason

    assert _skip_reason() is None
    name, url = _create_db("p5b_budget_task05")
    try:
        migrated = _alembic(url, "upgrade", "head")
        assert migrated.returncode == 0, "isolated migration failed"
        engine = make_engine(url)
        with engine.connect() as conn:
            assert conn.execute(text("SHOW server_version")).scalar().startswith("16.")
        yield url, DbBudgetLedger(make_session_factory(engine))
        engine.dispose()
    finally:
        _drop_db(name)


@pytest.mark.parametrize(
    "limit", ["class", "category", "total", "concurrency", "requests"]
)
def test_postgresql_independent_api_worker_admission(postgres, limit):
    url, ledger = postgres
    raw = synthetic_config()
    raw["limits"]["max_concurrency"] = 20
    if limit == "class":
        raw["classes"]["production"]["stop_usd"] = ".0005"
    if limit == "category":
        raw["classes"]["production"]["categories"]["agent"]["stop_usd"] = ".0005"
    if limit == "total":
        raw["total"]["stop_usd"] = ".0005"
    if limit == "concurrency":
        raw["limits"]["max_concurrency"] = 5
    if limit == "requests":
        raw["classes"]["production"]["max_requests"] = 5
    # Class/category configuration must remain internally valid.
    if limit == "class":
        raw["classes"]["production"]["categories"] = {
            k: {"hard_cap_usd": ".0005", "stop_usd": ".0005"}
            for k in raw["classes"]["production"]["categories"]
        }
    cfg = C.parse_config(raw)
    ctx = multiprocessing.get_context("spawn")
    event = ctx.Event()
    queue = ctx.Queue()
    processes = [
        ctx.Process(
            target=_compete,
            args=(url, raw, event, queue, "api" if i % 2 == 0 else "worker"),
        )
        for i in range(12)
    ]
    try:
        for p in processes:
            p.start()
        event.set()
        results = [queue.get(timeout=90) for p in processes]
        for p in processes:
            p.join(30)
            assert p.exitcode == 0
        assert results.count("admitted") == 5, results
        snap = ledger.snapshot(cfg, "production")
        assert snap["requests"] == 5 and snap["held_usd"] == "0.000500"
        assert ledger.integrity("production")["consistent"]
        ledger.kill()
        restarted = DbBudgetLedger(ledger._sf)
        with pytest.raises(BudgetError) as err:
            reserve(restarted, cfg)
        assert err.value.reason == "kill_switch"
        with ledger._sf() as s:
            assert len(list(s.execute(select(AiBudgetEntry)).scalars())) == 5
    finally:
        for p in processes:
            if p.is_alive():
                p.terminate()
                p.join(10)


@pytest.mark.parametrize(
    "scenario",
    [
        "success",
        "timeout",
        "no-usage",
        "malformed",
        "429",
        "503",
        "overrun",
        "bad-tokens",
    ],
)
def test_postgresql_mocked_settlement_and_refusal(postgres, scenario):
    url, ledger = postgres
    raw = synthetic_config()
    cfg = C.parse_config(raw)
    env = {"API_ENV": "staging", C.MODE_ENV: "enforce", C.MARKER_ENV: MARKER}
    gov = G.install(G.BudgetGovernor.build(ledger._sf, config=cfg, environ=env))

    def response(req, n):
        if scenario == "timeout":
            raise httpx.ReadTimeout("synthetic timeout")
        if scenario == "no-usage":
            return httpx.Response(200, json={})
        if scenario == "malformed":
            return httpx.Response(200, content=b"{")
        if scenario in ("429", "503"):
            return httpx.Response(int(scenario))
        return httpx.Response(
            200,
            json={
                "usage": {
                    "prompt_tokens": -2 if scenario == "bad-tokens" else 10,
                    "completion_tokens": 3,
                    **({"cost": ".5"} if scenario == "overrun" else {}),
                }
            },
        )

    p = Provider(response)
    if scenario == "timeout":
        with pytest.raises(httpx.ReadTimeout):
            chat(p.client())
    else:
        chat(p.client())
    snap = gov.status()
    assert (
        snap["integrity"]["consistent"]
        and snap["requests"] == 1
        and len(p.requests) == 1
    )
    if scenario in ("timeout", "no-usage", "malformed", "503", "bad-tokens"):
        assert (
            snap["calls_by_state"] == {"unknown": 1}
            and float(snap["unknown_held_usd"]) > 0
        )
        with pytest.raises(BudgetError):
            chat(p.client())
        assert len(p.requests) == 1
    elif scenario == "429":
        assert snap["held_usd"] == "0.000000" and snap["calls_by_state"] == {
            "rejected": 1
        }
        chat(p.client())
        with pytest.raises(BudgetError):
            chat(p.client())
        assert len(p.requests) == 2
    elif scenario == "overrun":
        assert snap["state"] == "killed" and snap["settled_usd"] == "0.500000"
        with pytest.raises(BudgetError):
            chat(p.client())
    else:
        assert (
            snap["calls_by_state"] == {"settled": 1}
            and snap["settled_usd"] == "0.000016"
        )
    assert DbBudgetLedger(ledger._sf).snapshot(cfg, "production")["requests"] == len(
        p.requests
    )


def test_hosted_safe_non_ai_http_survives_closed_budget():
    gov = G.install_from_env(environ={"API_ENV": "staging"})
    p = Provider()
    assert p.client().get("https://accounts.example.invalid/health").status_code == 200
    assert not gov.is_open


def test_hosted_demo_configuration_cannot_install_demonstration_budget():
    from src.demo_live.guard import install_from_env

    assert (
        install_from_env({"API_ENV": "staging", "ASK4MO_PROVIDER_MODE": "live"}) is None
    )


def test_ledger_outage_refuses_before_provider(ledger, monkeypatch):
    from sqlalchemy.exc import OperationalError

    def broken():
        raise OperationalError("synthetic", {}, Exception())

    cfg = C.parse_config(raw_config())
    G.install(
        G.BudgetGovernor(cfg, ledger, "production", environ={C.MARKER_ENV: MARKER})
    )
    monkeypatch.setattr(ledger, "_sf", broken)
    p = Provider()
    with pytest.raises(BudgetError):
        chat(p.client())
    assert not p.requests
    assert budget_status(broken, {})["state"] == "unavailable"


@pytest.mark.parametrize("transport", ["google-speech", "gemini-live"])
def test_legacy_non_httpx_sdk_boundary_refuses_hosted(transport, monkeypatch):
    monkeypatch.setenv("API_ENV", "staging")
    if transport == "google-speech":
        from src.speech_service import GoogleSpeechTranscriptionService

        # Call the real boundary without constructing credentials or a real SDK.
        from types import SimpleNamespace

        with pytest.raises(BudgetError) as err:
            GoogleSpeechTranscriptionService._get_client(
                SimpleNamespace(_client=object())
            )
    else:
        from src.live_interview import GeminiLiveTokenService

        with pytest.raises(BudgetError) as err:
            GeminiLiveTokenService._default_minter(
                None,
                api_key="synthetic-not-a-key",
                model="synthetic",
                ttl_seconds=1,
                now=0,
            )
    assert err.value.reason == "transport_not_qualified"


@pytest.mark.parametrize(
    "extra",
    [
        {"n": 2},
        {"best_of": 2},
        {"modalities": ["audio"]},
        {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": "https://synthetic.invalid/a"},
                        }
                    ],
                }
            ]
        },
    ],
)
def test_unqualified_request_shapes_never_send_or_underreserve(ledger, extra):
    cfg = C.parse_config(raw_config())
    G.install(
        G.BudgetGovernor(cfg, ledger, "production", environ={C.MARKER_ENV: MARKER})
    )
    p = Provider()
    with pytest.raises(BudgetError) as err:
        chat(p.client(), **extra)
    assert err.value.reason == "request_shape_not_supported" and not p.requests


def test_environment_emergency_stop_is_latched_in_durable_ledger(ledger):
    cfg = C.parse_config(raw_config())
    G.BudgetGovernor.build(
        ledger._sf,
        config=cfg,
        budget_class="production",
        environ={C.MARKER_ENV: MARKER, C.KILL_ENV: "true"},
    )
    restarted = G.BudgetGovernor.build(
        ledger._sf,
        config=cfg,
        budget_class="production",
        environ={C.MARKER_ENV: MARKER},
    )
    assert restarted.killed() and DbBudgetLedger(ledger._sf).killed()


def test_partial_chat_usage_does_not_invent_zero_output_tokens(ledger):
    cfg = C.parse_config(raw_config())
    gov = G.install(
        G.BudgetGovernor(cfg, ledger, "production", environ={C.MARKER_ENV: MARKER})
    )
    p = Provider(
        lambda r, n: httpx.Response(200, json={"usage": {"prompt_tokens": 10}})
    )
    chat(p.client())
    snap = gov.status()
    assert (
        snap["calls_by_state"] == {"unknown": 1} and float(snap["unknown_held_usd"]) > 0
    )
    with ledger._sf() as s:
        entry = s.execute(select(AiBudgetEntry)).scalar_one()
        assert entry.input_tokens == 10 and entry.output_tokens is None
    assert (
        snap["input_tokens_known"] == 10
        and snap["output_tokens_known"] is None
        and snap["calls_with_known_usage"] == 0
    )


@pytest.mark.parametrize("mode", ["enforce", "off"])
def test_local_guard_cannot_be_reused_as_a_hosted_development_bypass(ledger, mode):
    cfg = C.parse_config(raw_config())
    G.install(
        G.BudgetGovernor(cfg, ledger, "development", environ={C.MARKER_ENV: MARKER})
    )
    reused = G.install_from_env(
        ledger._sf,
        environ={"API_ENV": "staging", C.MODE_ENV: mode, C.MARKER_ENV: MARKER},
    )
    p = Provider()
    with pytest.raises(BudgetError):
        chat(p.client())
    assert reused.closed_reason == "enforcement_required" and not p.requests


@pytest.mark.parametrize("legacy", ["demo", "p10e"])
def test_legacy_file_ledger_cannot_authorize_hosted_spending(legacy, monkeypatch):
    monkeypatch.setenv("API_ENV", "staging")
    if legacy == "demo":
        from src.demo_live.guard import ProviderControl

        guard = object.__new__(ProviderControl)
        guard.mode = "live"
    else:
        from src.p10e.httpguard import HttpGuard

        guard = object.__new__(HttpGuard)
    with pytest.raises(BudgetError) as err:
        guard.install()
    assert err.value.reason == "transport_not_qualified"


def test_postgresql_kill_commit_refuses_waiting_independent_processes(postgres):
    from sqlalchemy import update
    from src.persistence import AiBudgetControl

    url, ledger = postgres
    raw = synthetic_config()
    cfg = C.parse_config(raw)
    initial = reserve(ledger, cfg)
    ledger.settle(initial, outcome="rejected")
    ctx = multiprocessing.get_context("spawn")
    event = ctx.Event()
    queue = ctx.Queue()
    ready = ctx.Queue()
    processes = [
        ctx.Process(target=_compete, args=(url, raw, event, queue, str(i), ready))
        for i in range(5)
    ]
    try:
        with ledger._sf() as s:
            # Hold the same global lock as admission while competing requests start.
            s.execute(
                update(AiBudgetControl)
                .where(AiBudgetControl.scope_key == "global")
                .values(killed=True, kill_reason="synthetic-concurrent-stop")
            )
            for p in processes:
                p.start()
            assert [ready.get(timeout=60) for p in processes] == ["ready"] * 5
            event.set()
            assert [ready.get(timeout=60) for p in processes] == ["attempt"] * 5
            s.commit()
        assert [queue.get(timeout=60) for p in processes] == ["kill_switch"] * 5
        for p in processes:
            p.join(20)
            assert p.exitcode == 0
        snap = ledger.snapshot(cfg, "production")
        assert (
            snap["requests"] == 1 and snap["held_usd"] == "0.000000" and snap["killed"]
        )
    finally:
        for p in processes:
            if p.is_alive():
                p.terminate()
                p.join(10)


def test_postgresql_disconnected_ledger_refuses_and_recovery_preserves_held_usage(
    postgres,
):
    url, ledger = postgres
    cfg = C.parse_config(synthetic_config())
    held = reserve(ledger, cfg)
    ledger.settle(held, outcome="unknown")
    engine = ledger._sf.kw["bind"]
    with ledger._sf() as s:
        own_pid = s.execute(text("SELECT pg_backend_pid()")).scalar()
    # A separate connection terminates ONLY this fixture's pooled ledger connection.
    # Keep the exact disposable URL; never relax the test database isolation guard.
    admin = make_engine(url)
    try:
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            assert conn.execute(
                text("SELECT pg_terminate_backend(:pid)"), {"pid": own_pid}
            ).scalar()
        gov = G.install(
            G.BudgetGovernor(cfg, ledger, "production", environ={C.MARKER_ENV: MARKER})
        )
        p = Provider()
        with pytest.raises(BudgetError):
            chat(p.client())
        assert not p.requests
    finally:
        admin.dispose()
        engine.dispose()
    snap = gov.status()
    assert (
        snap["integrity"]["consistent"]
        and snap["unknown_held_usd"] == "0.000100"
        and snap["requests"] == 1
    )


@pytest.mark.parametrize("restart", [False, True])
def test_missing_global_control_is_never_recreated_over_existing_spend(ledger, restart):
    cfg = C.parse_config(raw_config())
    reserve(ledger, cfg)
    with ledger._sf() as s:
        s.execute(text("DELETE FROM ai_budget_controls WHERE scope_key='global'"))
        s.commit()
    candidate = DbBudgetLedger(ledger._sf) if restart else ledger
    with pytest.raises(BudgetError) as err:
        reserve(candidate, cfg)
    assert err.value.reason == "ledger_inconsistent"
    with ledger._sf() as s:
        assert (
            s.execute(
                text("SELECT COUNT(*) FROM ai_budget_controls WHERE scope_key='global'")
            ).scalar()
            == 0
        )
        assert s.execute(text("SELECT COUNT(*) FROM ai_budget_entries")).scalar() == 1


def test_hosted_runtime_file_change_refuses_before_provider_and_admin_reports_mismatch(
    postgres, tmp_path
):
    _, ledger = postgres
    raw = synthetic_config()
    path = tmp_path / "synthetic-unapproved-test-only.json"
    path.write_text(json.dumps(raw))
    env = {
        "API_ENV": "staging",
        C.MODE_ENV: "enforce",
        C.MARKER_ENV: MARKER,
        C.CONFIG_PATH_ENV: str(path),
    }
    gov = G.install(G.BudgetGovernor.build(ledger._sf, environ=env))
    raw["classes"]["production"]["max_requests"] -= 1
    path.write_text(json.dumps(raw))
    p = Provider()
    with pytest.raises(BudgetError) as err:
        chat(p.client())
    assert err.value.reason == "policy_mismatch" and not p.requests
    status = budget_status(ledger._sf, env)
    assert status["state"] == "unavailable" and status["reason"] == "policy_mismatch"
    assert gov.config.raw_hash != C.load_config(environ=env).raw_hash


def test_hosted_approval_cannot_inherit_an_implicit_provider_host():
    raw = synthetic_config()
    del raw["allowed_provider_hosts"]
    with pytest.raises(BudgetError) as err:
        C.validate_hosted_approval(C.parse_config(raw), {"API_ENV": "staging"})
    assert err.value.reason == "approval_invalid"
