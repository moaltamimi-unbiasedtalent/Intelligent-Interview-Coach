"""P10E Safeguard B and the HTTP chokepoint: the persistent cumulative ledger outside the checkout, the exclusive lock, crash-safe reservations, cross-run and cross-checkout budget
enforcement, and enforcement of the approved limits on the REAL OpenAI SDK request path (mock transport only: no network, no credential, no paid call). Every ledger here is a
temporary, isolated one; the real P10E ledger and live evidence are never touched."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from src.p10e import guard as G
from src.p10e import httpguard as H
from src.p10e import ledger as L
from tests.test_p10e_live_guard import ENV, OWNER_LIMITS, PRICES, SLUG, approved, auth_of

ROOT = Path(__file__).resolve().parents[1]
MODEL = SLUG["balanced"]
SYNTH = "synthetic_fixture_corpus"


def make_ledger(tmp_path, name="ledger", total=10, cap=300, env_id="env-test"):
    d = tmp_path / name
    led = L.Ledger.create(d, environment_id=env_id, approved_total_usd=Decimal(total), call_cap=cap)
    genesis = led.meta["genesis_id"]
    led.conn.close()
    return d, genesis


def open_led(d, genesis, env_id="env-test", **kw):
    return L.Ledger.open(d, expected_genesis=genesis, environment_id=env_id, **kw)


def reserve(led, usd="1", units=1, cap_usd="10", cap_calls=300, run="r", area="a"):
    return led.reserve(run_id=run, area=area, model=MODEL, reserved_usd=Decimal(usd), call_units=units, max_usd=Decimal(cap_usd), max_calls=cap_calls)


def auth_for(tmp_path, genesis, env_id="env-test", **limit_over):
    body = approved(execution_environment={"environment_id": env_id, "host_fingerprint_sha256": L.host_fingerprint(), "ledger_genesis_id": genesis, "ledger_dir_env": "P10E_LEDGER_DIR"},
                    limits={**OWNER_LIMITS, **limit_over})
    return auth_of(tmp_path, body)


@contextmanager
def session(tmp_path, d, genesis, **limit_over):
    with G.live_session("test", SYNTH, env=ENV, auth=auth_for(tmp_path, genesis, **limit_over), ledger_dir=d, prices=PRICES) as s:
        yield s


# =================================================================================================================================== location and identity
def test_the_ledger_must_be_explicit_absolute_outside_the_checkout_and_private(tmp_path):
    with pytest.raises(G.LiveRunRefused) as e:
        L.check_location(Path("relative/ledger")); assert e.value.reason == "ledger_location_invalid"
    with pytest.raises(G.LiveRunRefused) as e:
        L.check_location(ROOT / "evaluations" / "ledger"); assert e.value.reason == "ledger_location_invalid"
    fake_repo = tmp_path / "repo"
    (fake_repo / ".git").mkdir(parents=True)
    with pytest.raises(G.LiveRunRefused) as e:
        L.check_location(fake_repo / "inside", repo_root=ROOT); assert e.value.reason == "ledger_location_invalid"        # any Git working tree
    open_dir = tmp_path / "open"
    open_dir.mkdir(mode=0o755)
    os.chmod(open_dir, 0o755)
    with pytest.raises(G.LiveRunRefused) as e:
        L.check_location(open_dir); assert e.value.reason == "ledger_location_insecure"                                    # open to group or others
    good = L.check_location(tmp_path / "new")
    assert good.is_absolute()


def test_there_is_no_default_location_and_a_refusal_creates_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(G.LiveRunRefused) as e:
        with G.live_session("t", SYNTH, env={"P10E_LIVE": "1"}, auth=auth_for(tmp_path, "g"), prices=PRICES):
            pass
    assert e.value.reason == "ledger_location_missing" and list(tmp_path.iterdir()) == [tmp_path / "auth.json"]            # nothing was created (only the test's own auth file exists)


def test_create_open_and_the_identity_checks(tmp_path, monkeypatch):
    d, g = make_ledger(tmp_path)
    assert oct(d.stat().st_mode & 0o777) == "0o700" and oct((d / "ledger.sqlite").stat().st_mode & 0o777) == "0o600"
    led = open_led(d, g)
    assert led.snapshot()["remaining_usd"] == "10" and led.snapshot()["remaining_calls"] == 300
    led.close(backup=False)
    with pytest.raises(G.LiveRunRefused) as e:
        L.Ledger.create(d, environment_id="env-test", approved_total_usd=Decimal(10), call_cap=300); assert e.value.reason == "ledger_exists"     # never re-initialized
    with pytest.raises(G.LiveRunRefused) as e:
        open_led(d, "0" * 32); assert e.value.reason == "ledger_identity_mismatch"
    with pytest.raises(G.LiveRunRefused) as e:
        open_led(d, g, env_id="another-environment"); assert e.value.reason == "ledger_identity_mismatch"
    with pytest.raises(G.LiveRunRefused) as e:
        L.Ledger.open(d, expected_genesis=None, environment_id="env-test"); assert e.value.reason == "ledger_not_designated"
    monkeypatch.setattr(L, "host_fingerprint", lambda: "some-other-host")
    with pytest.raises(G.LiveRunRefused) as e:
        open_led(d, g); assert e.value.reason == "ledger_wrong_host"                                                          # a copied ledger elsewhere is refused


def test_a_missing_ledger_is_a_stop_never_an_automatic_initialization(tmp_path):
    d, g = make_ledger(tmp_path)
    (d / "ledger.sqlite").unlink()
    with pytest.raises(G.LiveRunRefused) as e:
        open_led(d, g)
    assert e.value.reason == "ledger_missing" and not (d / "ledger.sqlite").exists()


def test_a_second_checkout_cannot_obtain_its_own_allowance(tmp_path):
    d1, g1 = make_ledger(tmp_path, "ledger-a")
    d2, g2 = make_ledger(tmp_path, "ledger-b")                                                                                 # a fresh, empty ledger a second checkout might create
    assert g1 != g2
    with pytest.raises(G.LiveRunRefused) as e:                                                                                 # the authorization (reviewed commit) designates genesis g1
        with G.live_session("t", SYNTH, env=ENV, auth=auth_for(tmp_path, g1), ledger_dir=d2, prices=PRICES):
            pass
    assert e.value.reason == "ledger_identity_mismatch"
    # the same ledger is reachable from another "checkout" (same designated host): it is ONE shared allowance
    led = open_led(d1, g1)
    reserve(led, "6")
    led.close(backup=False)
    led2 = open_led(d1, g1)
    with pytest.raises(G.BudgetExceeded):
        reserve(led2, "5")
    led2.close(backup=False)


def test_the_ledger_init_command_refuses_once_a_genesis_is_designated(monkeypatch, tmp_path, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("p10e_cli_init", ROOT / "scripts/p10e_live.py")
    cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)
    monkeypatch.setenv("P10E_LEDGER_DIR", str(tmp_path / "newledger"))
    designated = approved()
    designated["execution_environment"] = {**designated.get("execution_environment", {}), "ledger_genesis_id": "abc123", "host_fingerprint_sha256": L.host_fingerprint(), "environment_id": "env-x"}
    p = tmp_path / "auth.json"; p.write_text(json.dumps(designated))
    orig = G.load_authorization
    monkeypatch.setattr(cli.G, "load_authorization", lambda *a, **k: orig(p))
    assert cli.main(["ledger-init"]) == 3 and "ledger_already_designated" in capsys.readouterr().out and not (tmp_path / "newledger").exists()


# =================================================================================================================================== integrity and append-only
def test_settled_entries_cannot_be_updated_or_deleted_and_the_ledger_stays_valid(tmp_path):
    d, g = make_ledger(tmp_path)
    led = open_led(d, g)
    seq = reserve(led)
    led.settle(seq, state="settled_known", committed_usd=Decimal("0.1"), input_tokens=1, output_tokens=1)
    with pytest.raises(sqlite3.DatabaseError):
        led.conn.execute("UPDATE entries SET committed_usd='0' WHERE seq=?", (seq,))                                           # a settled entry is immutable
    with pytest.raises(sqlite3.DatabaseError):
        led.conn.execute("DELETE FROM entries WHERE seq=?", (seq,))
    with pytest.raises(sqlite3.DatabaseError):
        led.conn.execute("UPDATE meta SET value='999999' WHERE key='approved_total_usd'")                                      # the approved total cannot be edited
    with pytest.raises(sqlite3.DatabaseError):
        led.conn.execute("DELETE FROM meta WHERE key='genesis_id'")
    with pytest.raises(G.LiveRunRefused):
        led.settle(seq, state="settled_known", committed_usd=Decimal(0))                                                       # cannot settle twice
    led.close(backup=False)
    open_led(d, g).close(backup=False)


def _raw(d):
    c = sqlite3.connect(d / "ledger.sqlite", isolation_level=None)
    return c


@pytest.mark.parametrize("attack", ["garbage", "drop_trigger", "delete_row_no_triggers", "truncate_and_restore_triggers", "edit_identity_after_drop"])
def test_a_corrupted_or_tampered_ledger_refuses_additional_calls(tmp_path, attack):
    d, g = make_ledger(tmp_path)
    led = open_led(d, g)
    for i in range(3):
        led.settle(reserve(led, "1", run=f"r{i}"), state="settled_known", committed_usd=Decimal("0.5"), input_tokens=1, output_tokens=1)
    led.close(backup=False)
    if attack == "garbage":
        (d / "ledger.sqlite").write_bytes(b"this is not a database" * 100)
    else:
        c = _raw(d)
        trig = c.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger'").fetchall()
        if attack == "drop_trigger":
            c.execute("DROP TRIGGER entries_no_delete")
        elif attack == "delete_row_no_triggers":
            for n, _ in trig: c.execute(f"DROP TRIGGER {n}")
            c.execute("DELETE FROM entries WHERE seq=2")
        elif attack == "truncate_and_restore_triggers":
            for n, _ in trig: c.execute(f"DROP TRIGGER {n}")
            c.execute("DELETE FROM entries WHERE seq=3")                                                                       # drop the newest spend ...
            for _, sql in trig: c.execute(sql)                                                                                 # ... and put the protections back
        elif attack == "edit_identity_after_drop":
            for n, _ in trig: c.execute(f"DROP TRIGGER {n}")
            c.execute("UPDATE entries SET reserved_usd='0.0001' WHERE seq=1")
            for _, sql in trig: c.execute(sql)
        c.close()
    with pytest.raises(G.LiveRunRefused) as e:
        open_led(d, g)
    assert e.value.reason == "ledger_corrupted"


# =================================================================================================================================== exclusive lock
def test_a_second_session_in_the_same_process_is_refused_until_the_first_closes(tmp_path):
    d, g = make_ledger(tmp_path)
    first = open_led(d, g)
    with pytest.raises(G.LiveRunRefused) as e:
        open_led(d, g); assert e.value.reason == "ledger_locked"
    first.close(backup=False)
    open_led(d, g).close(backup=False)


def test_a_competing_runner_process_is_refused_while_the_lock_is_held(tmp_path):
    d, g = make_ledger(tmp_path)
    code = ("import sys; sys.path.insert(0, %r)\nfrom pathlib import Path\nfrom src.p10e import ledger as L\nfrom src.p10e.errors import LiveRunRefused\n"
            "try:\n    L.Ledger.open(Path(%r), expected_genesis=%r, environment_id='env-test')\n    print('OPENED')\nexcept LiveRunRefused as e:\n    print('REFUSED', e.reason)\n") % (str(ROOT), str(d), g)
    holder = open_led(d, g)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60).stdout
    assert "REFUSED ledger_locked" in out and "OPENED" not in out
    holder.close(backup=False)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60).stdout
    assert "OPENED" in out                                                                                                     # released: the OS lock is not a stale file


def test_the_lock_is_released_by_the_os_when_a_process_dies_and_open_reservations_are_kept(tmp_path):
    d, g = make_ledger(tmp_path)
    code = ("import sys, os; sys.path.insert(0, %r)\nfrom pathlib import Path\nfrom decimal import Decimal\nfrom src.p10e import ledger as L\n"
            "led = L.Ledger.open(Path(%r), expected_genesis=%r, environment_id='env-test')\n"
            "led.reserve(run_id='crash', area='a', model=%r, reserved_usd=Decimal('4'), call_units=1, max_usd=Decimal('10'), max_calls=300)\nos._exit(9)\n") % (str(ROOT), str(d), g, MODEL)
    assert subprocess.run([sys.executable, "-c", code], timeout=60).returncode == 9                                            # killed with a reservation persisted and no settlement
    led = open_led(d, g)                                                                                                       # the lock is free (OS released it); no stale lock was broken
    snap = led.snapshot()
    assert snap["committed_usd"] == "4" and snap["calls"] == 1 and snap["entries_unknown"] == 1 and snap["pending"] == 0     # kept at the FULL worst case, never refunded
    with pytest.raises(G.BudgetExceeded):
        reserve(led, "6.5")                                                                                                    # the crashed request still counts against the USD 10
    led.close(backup=False)


def test_an_unclosed_session_is_reconciled_on_the_next_open_without_resetting_anything(tmp_path):
    d, g = make_ledger(tmp_path)
    led = open_led(d, g)
    reserve(led, "2.5")
    os.close(led._lock_fd); led.conn.close()                                                                                   # simulate a hard stop without close(): lock gone, reservation pending
    led2 = open_led(d, g)
    s = led2.snapshot()
    assert s["committed_usd"] == "2.5" and s["entries_unknown"] == 1 and s["calls"] == 1
    sessions = led2.conn.execute("SELECT end_state FROM sessions ORDER BY started_at").fetchall()
    assert ("recovered_unclean",) in sessions
    led2.close(backup=False)


# =================================================================================================================================== cumulative budget and calls
def test_the_usd_ten_is_cumulative_across_sequential_sessions_and_restarts(tmp_path):
    d, g = make_ledger(tmp_path)
    s1 = open_led(d, g)
    s1.settle(reserve(s1, "6"), state="settled_known", committed_usd=Decimal("6"), input_tokens=1, output_tokens=1)
    s1.close()
    s2 = open_led(d, g)
    assert s2.snapshot()["committed_usd"] == "6" and s2.snapshot()["remaining_usd"] == "4"
    with pytest.raises(G.BudgetExceeded) as e:
        reserve(s2, "4.01"); assert e.value.reason == "spend_ceiling"
    reserve(s2, "4")                                                                                                           # exactly the remainder is allowed
    with pytest.raises(G.BudgetExceeded):
        reserve(s2, "0.0001")
    s2.close(backup=False)


def test_the_300_call_limit_is_global_and_never_per_run(tmp_path):
    d, g = make_ledger(tmp_path, cap=5)
    a = open_led(d, g)
    for i in range(3): reserve(a, "0.01", run=f"run-{i}")
    a.close(backup=False)
    b = open_led(d, g)
    reserve(b, "0.01", run="other-run"); reserve(b, "0.01", run="another-run")
    with pytest.raises(G.BudgetExceeded) as e:
        reserve(b, "0.01", run="third-run"); assert e.value.reason == "call_limit"
    b.close(backup=False)


def test_usd_fifteen_can_never_be_used_even_if_a_caller_asks(tmp_path):
    d, g = make_ledger(tmp_path)                                                                                               # the ledger's own approved total is 10
    led = open_led(d, g)
    with pytest.raises(G.BudgetExceeded):
        reserve(led, "12", cap_usd="15")                                                                                       # a caller-supplied 15 is capped by the ledger identity
    led.close(backup=False)
    with pytest.raises(G.LiveRunRefused) as e:
        G.require_live(auth_of(tmp_path, approved(limits={**OWNER_LIMITS, "max_spend_usd": 15})), env=ENV); assert e.value.reason == "spend_above_approval"
    with pytest.raises(sqlite3.DatabaseError):
        _ = open_led(d, g); c = _raw(d); c.execute("UPDATE meta SET value='15' WHERE key='approved_total_usd'")                  # and the stored total cannot be raised


def test_concurrent_admissions_never_exceed_the_call_cap(tmp_path):
    d, g = make_ledger(tmp_path, cap=9)
    led = open_led(d, g)
    ok, no = [], []
    lock = threading.Lock()

    def worker(i):
        # one connection per thread would break the single-holder model; threads share the session connection, serialized by BEGIN IMMEDIATE and the python lock
        try:
            with lock:
                reserve(led, "0.01", run=f"t{i}")
            ok.append(i)
        except G.BudgetExceeded:
            no.append(i)
    ts = [threading.Thread(target=worker, args=(i,)) for i in range(30)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(ok) == 9 and len(no) == 21 and led.snapshot()["calls"] == 9
    led.close(backup=False)


def test_settlement_rules_known_unknown_rejected_and_failed(tmp_path):
    d, g = make_ledger(tmp_path)
    led = open_led(d, g)
    a, b, c, e = (reserve(led, "1", run=f"r{i}") for i in range(4))
    led.settle(a, state="settled_known", committed_usd=Decimal("0.2"), input_tokens=10, output_tokens=5, provider_cost_usd=Decimal("0.2"))
    led.settle(b, state="settled_unknown", committed_usd=Decimal("1"), note="no usage reported")                               # unknown stays at the full worst case
    led.settle(c, state="rejected", committed_usd=Decimal("0"), status_code=429)                                                # definitive rejection: dollars released, the call still counted
    led.settle(e, state="settled_unknown", committed_usd=Decimal("1"), note="timeout")                                          # a client timeout is NOT a refund
    s = led.snapshot()
    assert Decimal(s["committed_usd"]) == Decimal("2.2") and s["calls"] == 4 and (s["entries_known"], s["entries_unknown"], s["entries_rejected"]) == (1, 2, 1)
    led.close()
    assert len(list(d.glob("ledger.backup-*.sqlite"))) == 1                                                                     # a consistent backup is written at a clean close


# =================================================================================================================================== the session preconditions
def test_live_session_applies_every_precondition(tmp_path):
    d, g = make_ledger(tmp_path)
    def open_(**kw):
        return G.live_session(kw.pop("area", "t"), kw.pop("data_class", SYNTH), env=kw.pop("env", ENV), auth=kw.pop("auth", auth_for(tmp_path, g)), ledger_dir=kw.pop("ledger_dir", d), prices=PRICES, **kw)
    for kw, reason in (({"data_class": "real_candidate_data"}, "data_class_not_allowed"), ({"env": {}}, "opt_in_missing"), ({"env": {"P10E_LIVE": "1", "CI": "true"}}, "ci_forbidden"),
                       ({"credential_check": lambda: False}, "credential_missing"), ({"auth": auth_of(tmp_path, approved(paid_execution_enabled="true"))}, "execution_flag_disabled"),
                       ({"auth": auth_of(tmp_path, approved(allowed_provider_hosts=[]))}, "provider_hosts_missing")):
        with pytest.raises(G.LiveRunRefused) as e:
            with open_(**kw): pass
        assert e.value.reason == reason, kw
    wrong_host = approved(execution_environment={"environment_id": "env-test", "host_fingerprint_sha256": "not-this-host", "ledger_genesis_id": g})
    with pytest.raises(G.LiveRunRefused) as e:
        with open_(auth=auth_of(tmp_path, wrong_host)): pass
    assert e.value.reason == "ledger_wrong_host"
    open_led(d, g).close(backup=False)                                                                                           # every refusal above released the lock
    with open_() as s:
        assert s.ledger.session_id and s.limits.max_provider_calls == 300 and s.budget.store is s.ledger
        with pytest.raises(G.LiveRunRefused) as e:                                                                                # exclusive: a second concurrent session is refused
            with open_(): pass
        assert e.value.reason == "ledger_locked"


# =================================================================================================================================== the HTTP chokepoint (real OpenAI SDK, mock transport)
def _ok_body(model=MODEL, usage=True, cost=0.00004):
    body = {"id": "x", "object": "chat.completion", "created": 1, "model": model, "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]}
    if usage:
        body["usage"] = {"prompt_tokens": 11, "completion_tokens": 2, "total_tokens": 13, **({"cost": cost} if cost is not None else {})}
    return body


class Transport:
    def __init__(self, respond=None):
        self.requests: list[httpx.Request] = []
        self.respond = respond or (lambda req, n: httpx.Response(200, json=_ok_body()))
        self._inflight = self.max_inflight = 0
        self._lock = threading.Lock()

    def __call__(self, req: httpx.Request):
        with self._lock:
            self.requests.append(req); n = len(self.requests); self._inflight += 1; self.max_inflight = max(self.max_inflight, self._inflight)
        try:
            return self.respond(req, n)
        finally:
            with self._lock:
                self._inflight -= 1


def chat(transport, *, model=MODEL, max_tokens=2000, base_url="https://openrouter.ai/api/v1", timeout=60, max_retries=0, **kw):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model, api_key="test-key", base_url=base_url, max_tokens=max_tokens, timeout=timeout, max_retries=max_retries,
                      http_client=httpx.Client(transport=httpx.MockTransport(transport)), **kw)


def test_an_admitted_request_is_reserved_before_sending_and_settled_from_the_response(tmp_path):
    d, g = make_ledger(tmp_path)
    t = Transport()
    seen = {}
    def respond(req, n):
        c = _raw_ro(d)
        seen["during"] = c.execute("SELECT state, committed_usd FROM entries").fetchall()                                      # the reservation is durable BEFORE the response exists
        c.close()
        return httpx.Response(200, json=_ok_body())
    t.respond = respond
    with session(tmp_path, d, g) as s:
        msg = chat(t).invoke([("human", "hi")])
        assert msg.content == "ok"
        snap = s.ledger.snapshot()
    assert seen["during"][0][0] == "reserved" and Decimal(seen["during"][0][1]) > 0
    assert snap["entries_known"] == 1 and snap["calls"] == 1
    assert Decimal(snap["committed_usd"]) == max(Decimal("0.000002") * 11 + Decimal("0.000012") * 2, Decimal("0.00004"))     # the larger of calculated and provider-reported cost
    body = json.loads(t.requests[0].content)
    assert body["max_completion_tokens"] == 2000 and t.requests[0].url.host == "openrouter.ai"


def _raw_ro(d):
    return sqlite3.connect(f"file:{d / 'ledger.sqlite'}?mode=ro", uri=True)


def test_requests_that_break_an_approved_limit_never_reach_the_transport(tmp_path):
    d, g = make_ledger(tmp_path)
    t = Transport()
    with session(tmp_path, d, g) as s:
        guard = s.http_guard
        for label, kwargs, reason in (
            ("no output cap", {"max_tokens": None}, "output_cap_missing"),
            ("cap above the limit", {"max_tokens": 3000}, "output_cap_exceeds_limit"),
            ("unpriced model", {"model": "openai/gpt-4o"}, "model_not_recognized"),
            ("another provider host", {"base_url": "https://api.openai.com/v1"}, "host_not_allowed"),
            ("streaming", {"streaming": True}, "streaming_not_supported"),
        ):
            with pytest.raises(Exception):
                chat(t, **kwargs).invoke([("human", "hi")])
            assert guard.refused[-1] == reason, label
        with pytest.raises(Exception):
            chat(t).invoke([("human", "word " * 30000)])                                                                       # about 38,000 estimated tokens > 20,000
        assert guard.refused[-1] == "request_too_large"
        assert s.ledger.snapshot()["calls"] == 0
    assert t.requests == []                                                                                                    # NOTHING was sent for any of them


def test_other_endpoints_and_other_httpx_users_are_blocked_during_a_session(tmp_path):
    d, g = make_ledger(tmp_path)
    with session(tmp_path, d, g) as s:
        with pytest.raises(G.LiveRunRefused) as e:
            httpx.Client().get("https://example.com/")                                                                         # any httpx user, not only the model client
        assert e.value.reason == "host_not_allowed"
        with pytest.raises(G.LiveRunRefused) as e:
            httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))).post("https://openrouter.ai/api/v1/embeddings", json={"model": MODEL, "input": "x"})
        assert e.value.reason == "endpoint_not_allowed"                                                                        # embeddings are unpriced: refused, not guessed
        ok = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": {}}))).get("https://openrouter.ai/api/v1/key")
        assert ok.status_code == 200 and s.http_guard.metadata_requests == 1 and s.ledger.snapshot()["calls"] == 0            # read-only metadata is allowed and never billed


def test_the_guard_is_removed_when_the_session_ends_and_can_be_installed_again(tmp_path):
    d, g = make_ledger(tmp_path)
    original = httpx.Client.send
    with session(tmp_path, d, g):
        assert httpx.Client.send is not original and H.HttpGuard._active is not None
    assert httpx.Client.send is original and H.HttpGuard._active is None
    with session(tmp_path, d, g):
        assert H.HttpGuard._active is not None


def test_each_retry_is_a_separate_counted_request_and_the_retry_limit_is_enforced(tmp_path):
    d, g = make_ledger(tmp_path)
    t = Transport(lambda req, n: httpx.Response(500, json={"error": "boom"}))
    with session(tmp_path, d, g) as s:                                                                                         # approved max_retries = 1: two attempts, never three
        with pytest.raises(Exception):
            chat(t, max_retries=2).invoke([("human", "hi")])
        snap = s.ledger.snapshot()
    assert len(t.requests) == 2 and [r.headers.get("x-stainless-retry-count") for r in t.requests] == ["0", "1"]
    assert snap["calls"] == 2 and snap["entries_unknown"] == 2 and "retry_limit" in s.http_guard.refused                       # both billed conservatively; the third was refused


def test_a_retry_after_a_server_error_counts_both_requests_and_keeps_the_failed_one_at_worst_case(tmp_path):
    d, g = make_ledger(tmp_path)
    t = Transport(lambda req, n: httpx.Response(500, json={"e": 1}) if n == 1 else httpx.Response(200, json=_ok_body()))
    with session(tmp_path, d, g) as s:
        chat(t, max_retries=1).invoke([("human", "hi")])
        snap = s.ledger.snapshot()
        rows = s.ledger.conn.execute("SELECT state FROM entries ORDER BY seq").fetchall()
    assert rows == [("settled_unknown",), ("settled_known",)] and snap["calls"] == 2


def test_the_timeout_is_clamped_to_the_approved_value(tmp_path):
    d, g = make_ledger(tmp_path)
    t = Transport()
    with session(tmp_path, d, g):
        chat(t, timeout=600).invoke([("human", "hi")])                                                                         # the client asks for 600 s
    assert all(v <= 60 for v in t.requests[0].extensions["timeout"].values())


def test_concurrency_never_exceeds_the_approved_two(tmp_path):
    d, g = make_ledger(tmp_path)
    def slow(req, n):
        time.sleep(0.15)
        return httpx.Response(200, json=_ok_body())
    t = Transport(slow)
    with session(tmp_path, d, g) as s:
        m = chat(t)
        ts = [threading.Thread(target=lambda: m.invoke([("human", "hi")])) for _ in range(6)]
        [x.start() for x in ts]; [x.join() for x in ts]
        assert s.ledger.snapshot()["calls"] == 6
    assert t.max_inflight <= 2


def test_provider_rejection_timeout_and_missing_usage_are_settled_conservatively(tmp_path):
    d, g = make_ledger(tmp_path)
    def respond(req, n):
        if n == 1: return httpx.Response(401, json={"error": "bad key"})
        if n == 2: raise httpx.ReadTimeout("slow", request=req)
        return httpx.Response(200, json=_ok_body(usage=False))
    t = Transport(respond)
    with session(tmp_path, d, g) as s:
        m = chat(t)
        for _ in range(3):
            try:
                m.invoke([("human", "hi")])
            except Exception:
                pass
        rows = s.ledger.conn.execute("SELECT state, committed_usd, status_code FROM entries ORDER BY seq").fetchall()
        snap = s.ledger.snapshot()
    assert rows[0][0] == "rejected" and Decimal(rows[0][1]) == 0 and rows[0][2] == 401                                          # rejected: dollars released, call counted
    assert rows[1][0] == "settled_unknown" and Decimal(rows[1][1]) > 0                                                           # timeout: potentially billable, kept
    assert rows[2][0] == "settled_unknown" and Decimal(rows[2][1]) > 0                                                           # response without usage: unknown is not zero
    assert snap["calls"] == 3 and len(t.requests) == 3


def test_nested_model_calls_inside_one_tool_all_count(tmp_path):
    from langchain_core.runnables import RunnableLambda
    d, g = make_ledger(tmp_path)
    t = Transport()
    with session(tmp_path, d, g) as s:
        m = chat(t)
        RunnableLambda(lambda x: [m.invoke([("human", "a")]), m.invoke([("human", "b")]), m.invoke([("human", "c")])]).invoke("go")     # a "tool" calling the model three times
        assert s.ledger.snapshot()["calls"] == 3 and len(t.requests) == 3


def test_the_budget_stops_the_http_path_before_the_network_when_the_ceiling_or_calls_are_reached(tmp_path):
    d, g = make_ledger(tmp_path, cap=2)
    t = Transport()
    with session(tmp_path, d, g, max_provider_calls=2) as s:
        m = chat(t)
        m.invoke([("human", "a")]); m.invoke([("human", "b")])
        with pytest.raises(Exception):
            m.invoke([("human", "c")])
        assert s.http_guard.refused[-1] == "call_limit"
    assert len(t.requests) == 2
    d2, g2 = make_ledger(tmp_path, "l2", total=10)
    c = open_led(d2, g2); reserve(c, "9.99"); c.close(backup=False)                                                            # earlier sessions already committed 9.99 of the USD 10
    t2 = Transport()
    with session(tmp_path, d2, g2) as s:
        with pytest.raises(Exception):
            chat(t2).invoke([("human", "hi")])                                                                                 # worst case (2000 output tokens) cannot fit in the remaining 0.01
        assert s.http_guard.refused[-1] == "spend_ceiling"
    assert t2.requests == []


def test_a_model_fallback_is_flagged(tmp_path):
    d, g = make_ledger(tmp_path)
    t = Transport(lambda req, n: httpx.Response(200, json=_ok_body(model="someone/else-model")))
    with session(tmp_path, d, g) as s:
        chat(t).invoke([("human", "hi")])
        assert s.http_guard.anomalies and "someone/else-model" in s.http_guard.anomalies[0]


# =================================================================================================================================== runners
def test_the_smoke_runner_runs_through_the_session_and_is_not_a_quality_claim(tmp_path):
    from src.p10e import live_runs as R
    d, g = make_ledger(tmp_path)
    ev = tmp_path / "evidence"; ev.mkdir()
    t = Transport()
    with session(tmp_path, d, g) as s:
        out = R.run_smoke(s, ["balanced"], build=lambda slug: chat(t, model=slug), base=ev)
    r = out["results"]["balanced"]
    assert r["status"] == "OK" and r["usage_reported"] and r["unexpected_fallback"] is False and r["answered_by"] == MODEL
    summary = json.loads(next(ev.iterdir()).joinpath("summary.json").read_text())
    assert summary["ledger_genesis_id"] == g and summary["environment_id"] == "env-test" and summary["execution_flag"] is True and "not quality qualification" in json.dumps(summary["results"])


def test_the_smoke_runner_reports_a_guard_refusal_as_refused_and_never_echoes_provider_text(tmp_path):
    from src.p10e import live_runs as R
    d, g = make_ledger(tmp_path, cap=300)
    ev = tmp_path / "evidence"; ev.mkdir()
    t = Transport()
    with session(tmp_path, d, g, max_output_tokens_per_request=100) as s:                                                         # the model asks for 100? it asks for the approved 100 via the builder
        out = R.run_smoke(s, ["fast"], build=lambda slug: chat(t, model=slug, max_tokens=500), base=ev)                          # a cap above the limit
    assert out["results"]["fast"] == {"status": "REFUSED", "reason": "output_cap_exceeds_limit"} and t.requests == []
    t2 = Transport(lambda req, n: httpx.Response(200, text="Authorization: Bearer sk-or-SECRETSECRETSECRET not json"))
    with session(tmp_path, d, g) as s:
        out = R.run_smoke(s, ["fast"], build=lambda slug: chat(t2, model=slug), base=ev)
    assert "sk-or" not in json.dumps(out)


def test_the_kb_quality_runner_answers_only_the_answer_cases_and_never_declares_a_pass(tmp_path):
    from src.p10e import live_runs as R
    d, g = make_ledger(tmp_path)
    ev = tmp_path / "evidence"; ev.mkdir()
    t = Transport(lambda req, n: httpx.Response(200, json={**_ok_body(), "choices": [{"index": 0, "message": {"role": "assistant", "content": "According to the evidence [1]."}, "finish_reason": "stop"}]}))
    with session(tmp_path, d, g) as s:
        out = R.run_kb_quality(s, "balanced", build=lambda slug: chat(t, model=slug), base=ev)
        snap = s.ledger.snapshot()
    res = out["results"]
    assert len([c for c in res["cases"] if c["status"] == "COMPLETE"]) == 9 and len(res["evidence_cases_not_run"]) == 11 and snap["calls"] == 9
    assert res["metrics"]["thresholds"].startswith("none") and "citation_supports_claim" in res["metrics"]["pending_human_review"]
    packet = json.loads((Path(out["run_dir"]) / "review_packet.json").read_text())
    assert packet["reviewer"] is None and all(v == "PENDING_HUMAN_REVIEW" for c in packet["cases"] for v in c["human_ratings"].values())


def test_the_kb_quality_runner_stops_at_the_global_call_limit_and_says_so(tmp_path):
    from src.p10e import live_runs as R
    d, g = make_ledger(tmp_path, cap=3)
    ev = tmp_path / "evidence"; ev.mkdir()
    t = Transport()
    with session(tmp_path, d, g, max_provider_calls=3) as s:
        out = R.run_kb_quality(s, "fast", build=lambda slug: chat(t, model=slug), base=ev)
    done = [c for c in out["results"]["cases"] if c["status"] == "COMPLETE"]
    assert len(done) == 3 and out["results"]["stopped_by_guard"] == "call_limit" and len(t.requests) == 3
    assert any(c["status"].startswith("NOT RUN") for c in out["results"]["cases"])


def test_no_test_touches_the_real_ledger_or_live_evidence(tmp_path):
    live = ROOT / "evaluations" / "p10e" / "live"
    before = sorted(p.name for p in live.iterdir()) if live.exists() else []
    d, g = make_ledger(tmp_path)
    open_led(d, g).close(backup=False)
    assert (sorted(p.name for p in live.iterdir()) if live.exists() else []) == before
    assert not str(d).startswith(str(ROOT))


# =================================================================================================================================== classification, offline re-scoring, the auth probe
def test_kb_cases_are_classified_from_their_own_pinned_design_never_from_model_output():
    from src.p10e import live_runs as R
    assert R.classify_kb_case({"tags": ["grounding:unsupported_occupation"], "expect": {}}) == "designed_unsupported"
    assert R.classify_kb_case({"tags": ["citation:unavailable_evidence"], "expect": {}}) == "designed_unsupported"
    assert R.classify_kb_case({"tags": [], "expect": {"citations_max": 0}}) == "designed_unsupported"
    assert R.classify_kb_case({"tags": ["citation:correct_source"], "expect": {"citations_min": 1}}) == "designed_supported"
    assert R.classify_kb_case({"tags": [], "expect": {"citation_sources": ["fx_roles"]}}) == "designed_supported"
    assert R.classify_kb_case({"tags": ["x"], "expect": {}}) == "unclassified"


def test_an_abstention_on_a_designed_unsupported_case_is_not_scored_as_ungrounded_and_rescoring_is_offline_and_append_only(tmp_path):
    from src.p10e import live_runs as R
    d, g = make_ledger(tmp_path)
    ev = tmp_path / "evidence"; ev.mkdir()
    t = Transport(lambda req, n: httpx.Response(200, json={**_ok_body(), "choices": [{"index": 0, "message": {"role": "assistant", "content": "No evidence was retrieved, so I cannot say."}, "finish_reason": "stop"}]}))
    with session(tmp_path, d, g) as s:
        out = R.run_kb_quality(s, "balanced", build=lambda slug: chat(t, model=slug), base=ev)
    calls_before = len(t.requests)
    r = R.rescore_kb_run(Path(out["run_dir"]))
    assert len(t.requests) == calls_before and r["rescored_offline"] is True                              # re-scoring made no provider call
    unsupported = [x for x in r["per_case"] if x.get("design") == "designed_unsupported"]
    assert unsupported and all(x["observation"] == {"no_citation_invented": True} for x in unsupported)       # a correct abstention, not a failure
    assert r["tally"]["designed_unsupported"]["no_citation_invented"] == len(unsupported) and r["thresholds"].startswith("none")
    with pytest.raises(FileExistsError):
        R.rescore_kb_run(Path(out["run_dir"]))                                                              # an earlier result is never overwritten


def test_the_auth_failure_probe_releases_the_dollars_but_counts_the_call(tmp_path):
    from src.p10e import live_runs as R
    d, g = make_ledger(tmp_path)
    ev = tmp_path / "evidence"; ev.mkdir()
    t = Transport(lambda req, n: httpx.Response(401, json={"error": {"message": "invalid key", "code": 401}}))
    with session(tmp_path, d, g) as s:
        res = R.run_auth_failure_probe(s, base=ev, build=lambda slug: chat(t, model=slug, max_tokens=50))
    assert res["outcome"] == "REJECTED_OR_FAILED" and res["ledger_state"] == "rejected" and res["http_status"] == 401
    assert Decimal(res["committed_usd_for_the_call"]) == 0 and res["calls_counted"] == 1 and Decimal(res["usd_added"]) == 0
    assert "invalid-p10e-probe-key" not in json.dumps(res)
