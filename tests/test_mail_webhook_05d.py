"""05D: Brevo delivery-event webhook. Authentication (forged, old, future, replayed, malformed), bounded allow-listed storage, the code gate (False) and the
truth model (provider acceptance is not delivery). Offline: synthetic secret, in-memory SQLite, no network. The live Brevo round trip is NOT RUN."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.api import dependencies as deps
from src.auth_repository import AuditRepository
from src.mail import webhook as W
from src.mail.sender import SendResult
from src.mail.service import EmailAttemptRepository
from src.persistence import AuditEvent, EmailAttempt
from tests._auth_factories import build_auth_app

SECRET, OLD_SECRET = "whsec-test-synthetic-0001", "whsec-test-synthetic-OLD"
NOW = 1_800_000_000.0
URL = "/api/v1/mail/webhooks/brevo"
REF = "<202610220001.abc123@smtp-relay.example>"


def msg(r):
    body = r.json()
    return (body.get("error") or {}).get("message") or body.get("detail")


def ev(event="delivered", ref=REF, ts=NOW - 5, **extra):
    return json.dumps({"event": event, "message-id": ref, "ts_event": int(ts), **extra}).encode()


class Env:
    def __init__(self, *, authorized=True, mode="hmac", secrets=(SECRET,), clock=lambda: NOW):
        self.app, self.repo, _ = build_auth_app()
        self.attempts = EmailAttemptRepository(self.repo.session_factory)
        self.audit = AuditRepository(self.repo.session_factory)
        self.receiver = W.DeliveryEventReceiver(self.attempts, secrets=lambda: list(secrets), auth_mode=mode, authorized=authorized, clock=clock, audit=self.audit)
        self.app.dependency_overrides[deps.get_mail_webhook_receiver] = lambda: self.receiver
        self.c = TestClient(self.app)

    def submit(self, ref=REF, status="provider_accepted"):
        self.attempts.record(message_type="email_verification", result=SendResult(status, "brevo", None, ref), locale="en", request_id="r", user_id=None)

    def row(self, ref=REF):
        with self.repo.session_factory() as s:
            r = s.scalars(select(EmailAttempt).where(EmailAttempt.provider_message_ref == ref)).first()
            s.expunge(r)
            return r

    def post(self, body, headers=None):
        return self.c.post(URL, content=body, headers={"content-type": "application/json", **(headers or {})})

    def signed(self, body, ts=NOW, secret=SECRET):
        return {W.SIGNATURE_HEADER: W.sign(secret, body, int(ts))}

    def audit_blob(self):
        with self.repo.session_factory() as s:
            return json.dumps([{"t": e.event_type, "c": e.context, "r": e.result} for e in s.scalars(select(AuditEvent)).all()], default=str)


@pytest.fixture()
def env():
    return Env()


# ---- the gate ---------------------------------------------------------------------------------------------------------------
def test_the_code_gate_is_false_in_this_release():
    assert W.DELIVERY_EVENTS_AUTHORIZED is False


def test_gate_closed_refuses_everything_even_a_perfect_signature_and_stores_nothing():
    e = Env(authorized=None)                     # None = the real module constant (False)
    e.submit()
    body = ev()
    r = e.post(body, e.signed(body))
    assert r.status_code == 503 and msg(r) == "Webhook is not available."
    assert e.row().delivery_state is None and "mail.delivery_event" not in e.audit_blob() and "mail.webhook_rejected" not in e.audit_blob()


def test_the_real_dependency_is_non_operational_by_default(monkeypatch):
    app, repo, _ = build_auth_app()
    monkeypatch.setenv("BREVO_WEBHOOK_SECRET", SECRET)
    body = ev(ts=__import__("time").time())
    r = TestClient(app).post(URL, content=body, headers={W.SIGNATURE_HEADER: W.sign(SECRET, body, int(__import__("time").time()))})
    assert r.status_code == 503


def test_no_secret_configured_is_503_not_an_unauthenticated_accept():
    e = Env(secrets=())
    body = ev()
    assert e.post(body, e.signed(body)).status_code == 503


def test_unknown_auth_mode_fails_closed():
    e = Env(mode="none")
    body = ev()
    assert e.post(body, e.signed(body)).status_code == 503


# ---- signature authentication (hmac) ----------------------------------------------------------------------------------------
def test_valid_signed_delivered_event_is_stored_as_a_separate_delivery_state(env):
    env.submit()
    body = ev("delivered")
    r = env.post(body, env.signed(body))
    assert r.status_code == 200 and r.json() == {"status": "accepted"}
    row = env.row()
    assert row.delivery_state == "delivered" and row.status == "provider_accepted"          # acceptance is not rewritten
    assert row.delivery_event_at == datetime.fromtimestamp(int(NOW - 5), tz=timezone.utc).replace(tzinfo=row.delivery_event_at.tzinfo) and row.delivery_event_digest


def test_forged_signature_is_refused_and_stores_nothing(env):
    env.submit()
    body = ev()
    for hdr in ({W.SIGNATURE_HEADER: W.sign("some-other-secret", body, int(NOW))},
                {W.SIGNATURE_HEADER: f"t={int(NOW)},v1={'0' * 64}"},
                {W.SIGNATURE_HEADER: f"t={int(NOW)},v1={'ab' * 32}"}):
        r = env.post(body, hdr)
        assert r.status_code == 401 and msg(r) == "Webhook rejected."
    assert env.row().delivery_state is None


def test_a_body_modified_after_signing_is_refused(env):
    env.submit()
    body = ev("delivered")
    sig = env.signed(body)
    assert env.post(ev("hard_bounce"), sig).status_code == 401
    assert env.row().delivery_state is None


def test_missing_signature_is_refused(env):
    env.submit()
    assert env.post(ev()).status_code == 401


@pytest.mark.parametrize("header", ["", "garbage", "t=,v1=", "t=abc,v1=00", f"t={int(NOW)}", "v1=" + "0" * 64, f"t={int(NOW)},t={int(NOW)},v1=" + "0" * 64,
                                    "t=-5,v1=" + "0" * 64, "t=" + "9" * 30 + ",v1=00", "x" * 500])
def test_malformed_signature_headers_are_refused_not_crashed(env, header):
    r = env.post(ev(), {W.SIGNATURE_HEADER: header})
    assert r.status_code in (400, 401) and msg(r) == "Webhook rejected."


def test_old_signature_timestamp_is_refused_as_a_replay(env):
    env.submit()
    body = ev()
    old = NOW - W.SIGNATURE_TOLERANCE_SECONDS - 1
    assert env.post(body, env.signed(body, ts=old)).status_code == 401
    assert env.row().delivery_state is None


def test_future_dated_signature_timestamp_is_refused(env):
    body = ev()
    assert env.post(body, env.signed(body, ts=NOW + W.SIGNATURE_TOLERANCE_SECONDS + 1)).status_code == 401


def test_signature_at_the_edge_of_the_tolerance_is_accepted(env):
    env.submit()
    body = ev()
    assert env.post(body, env.signed(body, ts=NOW - W.SIGNATURE_TOLERANCE_SECONDS)).status_code == 200


def test_rotation_accepts_the_previous_secret_and_nothing_else():
    e = Env(secrets=(SECRET, OLD_SECRET))
    e.submit()
    body = ev()
    assert e.post(body, e.signed(body, secret=OLD_SECRET)).status_code == 200
    assert e.post(body, e.signed(body, secret="third")).status_code == 401


# ---- bearer mode -------------------------------------------------------------------------------------------------------------
def test_bearer_mode_accepts_only_the_exact_secret():
    e = Env(mode="bearer")
    e.submit()
    body = ev()
    assert e.post(body, {"authorization": f"Bearer {SECRET}x"}).status_code == 401
    assert e.post(body, {"authorization": f"Basic {SECRET}"}).status_code == 400
    assert e.post(body, {}).status_code == 401
    assert e.row().delivery_state is None
    assert e.post(body, {"authorization": f"Bearer {SECRET}"}).status_code == 200
    assert e.row().delivery_state == "delivered"


def test_bearer_mode_does_not_accept_an_hmac_header():
    e = Env(mode="bearer")
    body = ev()
    assert e.post(body, e.signed(body)).status_code == 401


# ---- replay protection and ordering -----------------------------------------------------------------------------------------
def test_a_replayed_valid_request_is_a_noop_and_changes_nothing(env):
    env.submit()
    body = ev("delivered")
    hdr = env.signed(body)
    assert env.post(body, hdr).status_code == 200
    first = env.row()
    assert env.post(body, hdr).status_code == 200            # acknowledged, idempotent
    again = env.row()
    assert (again.delivery_state, again.delivery_event_digest, again.delivery_event_at) == (first.delivery_state, first.delivery_event_digest, first.delivery_event_at)
    assert '"outcome": "replay"' in env.audit_blob()


def test_event_older_than_the_freshness_window_is_refused_even_when_signed_now(env):
    body = ev(ts=NOW - W.EVENT_MAX_AGE_SECONDS - 1)
    assert env.post(body, env.signed(body)).status_code == 400


def test_event_timestamp_in_the_future_is_refused(env):
    body = ev(ts=NOW + W.SIGNATURE_TOLERANCE_SECONDS + 10)
    assert env.post(body, env.signed(body)).status_code == 400


def test_the_state_only_moves_forward_so_a_late_delivered_cannot_undo_a_bounce(env):
    env.submit()
    for event, ts, expected in (("hard_bounce", NOW - 20, "hard_bounced"), ("delivered", NOW - 10, "hard_bounced"), ("spam", NOW - 5, "complained"),
                                ("soft_bounce", NOW - 2, "complained")):
        body = ev(event, ts=ts)
        assert env.post(body, env.signed(body)).status_code == 200
        assert env.row().delivery_state == expected, event


def test_an_older_event_of_equal_rank_does_not_overwrite_a_newer_one(env):
    env.submit()
    new, old = ev("delivered", ts=NOW - 5), ev("delivered", ts=NOW - 50)
    env.post(new, env.signed(new))
    at = env.row().delivery_event_at
    env.post(old, env.signed(old))
    assert env.row().delivery_event_at == at


# ---- parsing, allow-list and bounded storage ----------------------------------------------------------------------------------
@pytest.mark.parametrize("raw", [b"", b"{not json", b"[]", b"null", b'"x"', b"{}", b'{"event":"delivered"}', b'{"event":5,"message-id":"a","ts_event":1}',
                                 json.dumps({"event": "delivered", "message-id": "", "ts_event": int(NOW)}).encode(),
                                 json.dumps({"event": "delivered", "message-id": "a" * 300, "ts_event": int(NOW)}).encode(),
                                 json.dumps({"event": "delivered", "message-id": "a\nb", "ts_event": int(NOW)}).encode(),
                                 json.dumps({"event": "delivered", "message-id": "a", "ts_event": "soon"}).encode(),
                                 json.dumps({"event": "delivered", "message-id": "a", "ts_event": True}).encode(),
                                 json.dumps({"event": "delivered", "message-id": "a", "ts_event": -1}).encode(),
                                 json.dumps({"event": "x" * 200, "message-id": "a", "ts_event": int(NOW)}).encode()])
def test_malformed_payloads_with_a_valid_signature_are_400_not_500(env, raw):
    r = env.post(raw, env.signed(raw))
    assert r.status_code == 400 and msg(r) == "Webhook rejected."


def test_oversized_body_is_413_before_anything_else(env):
    big = b"x" * (W.MAX_BODY_BYTES + 1)
    assert env.post(big, env.signed(big)).status_code == 413


def test_events_outside_the_allow_list_are_acknowledged_and_ignored(env):
    env.submit()
    for name in ("opened", "click", "request", "deferred", "unsubscribed", "proxy_open", "invalid_email", "list_addition", "anything-else"):
        body = ev(name)
        assert env.post(body, env.signed(body)).status_code == 200
    row = env.row()
    assert row.delivery_state is None and row.delivery_event_digest is None


def test_provider_event_names_map_to_the_allow_listed_states():
    assert {W.EVENT_TO_STATE[k] for k in W.EVENT_TO_STATE} == set(W.DELIVERY_STATES)
    assert W.parse_event(ev("hardBounce"), now=NOW)["state"] == "hard_bounced"
    assert W.parse_event(ev("soft-bounce"), now=NOW)["state"] == "soft_bounced"
    assert W.parse_event(ev("spam"), now=NOW)["state"] == "complained"
    assert W.parse_event(ev("blocked"), now=NOW)["state"] == "blocked"


def test_unknown_message_reference_is_a_quiet_200_that_reveals_nothing(env):
    body = ev(ref="<never-sent@example>")
    r = env.post(body, env.signed(body))
    assert r.status_code == 200 and r.json() == {"status": "accepted"}


def test_reference_matches_with_or_without_angle_brackets(env):
    env.submit(ref="plain-ref-1@relay")
    body = ev(ref="<plain-ref-1@relay>")
    env.post(body, env.signed(body))
    assert env.row("plain-ref-1@relay").delivery_state == "delivered"


def test_nothing_from_the_payload_beyond_the_allow_list_is_stored_or_audited(env):
    env.submit()
    body = ev("delivered", email="victim.person@example.com", subject="Reset your password", link="https://app.example/reset?token=SECRETTOKEN",
              tag="t1", ip="203.0.113.7", **{"user-agent": "Mozilla"})
    assert env.post(body, env.signed(body)).status_code == 200
    with env.repo.session_factory() as s:
        dump = json.dumps([[str(getattr(a, c.name)) for c in EmailAttempt.__table__.columns] for a in s.scalars(select(EmailAttempt)).all()])
    blob = dump + env.audit_blob()
    for needle in ("victim.person", "Reset your password", "SECRETTOKEN", "203.0.113.7", "Mozilla", SECRET):
        assert needle not in blob


def test_rejections_are_audited_with_a_bounded_category_only(env):
    body = ev()
    env.post(body, env.signed(body, secret="wrong"))
    blob = env.audit_blob()
    assert "mail.webhook_rejected" in blob and "signature_invalid" in blob and "wrong" not in blob and SECRET not in blob


def test_storage_failure_is_a_retryable_503_never_an_acknowledgement():
    e = Env()

    class Broken:
        def apply_delivery_event(self, event):
            raise RuntimeError("db down")
    e.receiver = W.DeliveryEventReceiver(Broken(), secrets=lambda: [SECRET], authorized=True, clock=lambda: NOW)
    e.app.dependency_overrides[deps.get_mail_webhook_receiver] = lambda: e.receiver
    body = ev()
    assert e.post(body, e.signed(body)).status_code == 503


def test_response_never_echoes_payload_signature_or_secret(env):
    env.submit()
    body = ev()
    for r in (env.post(body, env.signed(body)), env.post(body, env.signed(body, secret="x")), env.post(b"junk", env.signed(b"junk"))):
        assert SECRET not in r.text and REF not in r.text and "t=" not in r.text


def test_route_is_rate_limited_per_ip(env):
    from src.api import rate_limit as rl

    rl.reset_rate_limiter(rl.InMemoryRateLimiter())
    pol = rl.POLICIES["mail_webhook_ip"]
    statuses = {env.post(b"{}", {}).status_code for _ in range(pol.limit + 3)}
    assert 429 in statuses
    rl.reset_rate_limiter()


# ---- truth model: provider acceptance is not delivery -------------------------------------------------------------------------
def test_admin_status_reports_delivery_not_collected_while_the_gate_is_closed():
    from src.mail import operations as ops

    assert ops._events_authorized() is False


def test_admin_status_reports_webhook_verified_only_when_the_gate_is_open(monkeypatch):
    from src.mail import operations as ops

    monkeypatch.setattr(W, "DELIVERY_EVENTS_AUTHORIZED", True)
    assert ops._events_authorized() is True


def test_acceptance_alone_never_produces_a_delivery_state(env):
    env.submit()
    row = env.row()
    assert row.status == "provider_accepted" and row.delivery_state is None


def test_summary_and_diagnostics_do_not_expose_a_recipient(env):
    env.submit()
    body = ev()
    env.post(body, env.signed(body))
    blob = json.dumps(env.attempts.summary(), default=str)
    assert "@" not in blob.replace(REF, "")


def test_webhook_module_never_imports_a_network_client():
    import inspect

    src = inspect.getsource(W)
    assert "httpx" not in src and "requests" not in src and "urllib.request" not in src
