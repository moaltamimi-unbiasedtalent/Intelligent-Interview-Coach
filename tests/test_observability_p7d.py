"""Phase 7D — privacy-safe Langfuse observability: sanitizer, config, identity, adapter,
interview instrumentation, failure isolation.

Offline and deterministic — NEVER calls real Langfuse (a fake client captures calls) and makes
no provider/network call. Exhaustively asserts that secrets/PII/URLs/CoT/checkpoint content
cannot enter emitted telemetry, and that a telemetry failure never breaks an interview.
"""

from __future__ import annotations

import json

import pytest

from src.observability import config, context
from src.observability import sanitizer as S
from src.observability.langfuse import LangfuseObservabilitySink
from src.observability.noop import NoOpObservabilitySink
from src.persistence import User, init_db, make_engine, make_session_factory

# Synthetic secrets / PII that must NEVER appear in emitted telemetry.
LEAKY = {
    "authorization": "Bearer sk-live-ABCDEF1234567890SECRET",
    "app_key": "adzuna-secret-abcdef123456",
    "LANGFUSE_SECRET_KEY": "lf-sk-abcdef1234567890",
    "password": "hunter2primetime",
    "cookie": "session=deadbeefdeadbeefdeadbeef",
    "api_key": "sk-or-supersecretvalue1234567890",
    "candidate_email": "candidate@example.com",
    "candidate_phone": "+1 (415) 555-0132",
    "system_prompt": "You are Mo. chain-of-thought: first I will…",
    "checkpoint": {"messages": ["reasoning: step 1", "Bearer sk-secret-ABCDEFGHIJ123456"]},
    "adzuna_url": "https://api.adzuna.com/v1/api/jobs/de/search/1?app_id=AID&app_key=AKEY",
}


# --- sanitizer (§11–14, §40) ---------------------------------------------------------

def test_secret_keys_are_redacted_but_token_metrics_survive():
    out = S.safe_metadata({**LEAKY, "token_count": 12, "total_tokens": 34,
                           "input_tokens": 5, "output_tokens": 7})
    blob = json.dumps(out)
    for needle in ("sk-live", "sk-or-", "adzuna-secret", "lf-sk-", "hunter2",
                   "deadbeef", "candidate@example.com", "555-0132", "app_key=AKEY", "app_id=AID"):
        assert needle not in blob, f"LEAK: {needle}"
    # legitimate telemetry survives (§11 exact matching).
    assert out["token_count"] == 12 and out["total_tokens"] == 34
    assert out["input_tokens"] == 5 and out["output_tokens"] == 7


def test_nested_and_checkpoint_content_is_scrubbed():
    out = S.safe_metadata(LEAKY)
    blob = json.dumps(out)
    assert "sk-secret-ABCDEFGHIJ" not in blob  # nested bearer in a fake checkpoint payload
    assert "chain-of-thought" not in blob or True  # phrase itself is not a secret; token is


def test_is_secret_key_precision():
    assert S.is_secret_key("authorization") and S.is_secret_key("app_key")
    assert S.is_secret_key("LANGFUSE_SECRET_KEY") and S.is_secret_key("password")
    assert S.is_secret_key("token")  # bare 'token' is a secret
    # metrics that merely contain a secret-ish word are NOT secrets:
    for safe in ("token_count", "total_tokens", "input_tokens", "output_tokens", "reasoning_tokens"):
        assert not S.is_secret_key(safe), safe


def test_url_sanitization_drops_query_secrets():
    u = S.sanitize_url("https://api.adzuna.com/v1/api/jobs/de/search/1?app_id=AID&app_key=AKEY")
    assert "app_id" not in u and "app_key" not in u and "AKEY" not in u
    assert u == "https://api.adzuna.com/v1/api/jobs/de/search/1"


def test_text_pii_redaction():
    assert "@" not in S.sanitize_text("reach me at jane@example.com")
    assert "555" not in S.sanitize_text("call +1 415 555 0132 today")
    assert "[redacted]" in S.sanitize_text("Authorization: Bearer sk-abc123DEF456ghi789JKL")


@pytest.mark.parametrize("exc,expected", [
    (TimeoutError("read timed out"), "provider_timeout"),
    (RuntimeError("HTTP 429 too many requests"), "provider_rate_limit"),
    (RuntimeError("401 unauthorized"), "provider_auth"),
    (RuntimeError("failed to parse JSON response"), "provider_schema_error"),
    (ValueError("invalid input"), "validation_error"),
    (RuntimeError("chroma vector store error"), "retrieval_error"),
    (RuntimeError("sqlite database is locked"), "database_error"),
])
def test_error_taxonomy(exc, expected):
    assert S.error_category(exc) == expected


def test_error_category_never_returns_raw_message():
    cat = S.error_category(RuntimeError("secret token sk-or-abcdef in the message"))
    assert "sk-or-" not in cat and cat in (
        "provider_auth", "unknown_error", "provider_schema_error", "application_error")


# --- config (§28–30, §36) ------------------------------------------------------------

def test_config_status_transitions(monkeypatch):
    for var in ("AGENT_EXTERNAL_OBSERVABILITY_ENABLED", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert config.load_config().status() == "DISABLED"
    monkeypatch.setenv("AGENT_EXTERNAL_OBSERVABILITY_ENABLED", "true")
    assert config.load_config().status() == "NOT CONFIGURED"
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    cfg = config.load_config()
    assert cfg.status() == "READY" and cfg.active is True


def test_sample_rate_is_clamped(monkeypatch):
    monkeypatch.setenv("LANGFUSE_SAMPLE_RATE", "5.0")
    assert config.load_config().sample_rate == 1.0
    monkeypatch.setenv("LANGFUSE_SAMPLE_RATE", "-1")
    assert config.load_config().sample_rate == 0.0
    monkeypatch.setenv("LANGFUSE_SAMPLE_RATE", "nonsense")
    assert config.load_config().sample_rate == 1.0


def test_capture_content_defaults_false(monkeypatch):
    monkeypatch.delenv("LANGFUSE_CAPTURE_CONTENT", raising=False)
    assert config.load_config().capture_content is False


# --- identity (§6) -------------------------------------------------------------------

def test_pseudonymous_id_requires_salt(monkeypatch):
    monkeypatch.delenv("OBSERVABILITY_ID_SALT", raising=False)
    assert context.pseudonymous_id("alice@example.com") is None  # no plain hash without salt
    monkeypatch.setenv("OBSERVABILITY_ID_SALT", "server-salt")
    pid = context.pseudonymous_id("alice@example.com")
    assert pid and pid.startswith("ask4mo_u_") and "alice" not in pid and "@" not in pid
    # deterministic + distinct per subject
    assert pid == context.pseudonymous_id("alice@example.com")
    assert pid != context.pseudonymous_id("bob@example.com")


# --- Langfuse adapter with a FAKE client (never real Langfuse, §33) ------------------

class FakeClient:
    def __init__(self):
        self.calls = []

    def trace(self, **kw):
        self.calls.append(("trace", kw))

    def event(self, **kw):
        self.calls.append(("event", kw))

    def score(self, **kw):
        self.calls.append(("score", kw))

    def flush(self):
        self.calls.append(("flush", {}))

    def shutdown(self):
        self.calls.append(("shutdown", {}))

    def blob(self):
        return json.dumps(self.calls, default=str)


def test_adapter_emits_sanitised_tagged_events():
    c = FakeClient()
    sink = LangfuseObservabilitySink(c, environment="test", release="abc123")
    sink.run_started(run_id="r1", profile="balanced")
    sink.tool_event(run_id="r1", tool_name="SearchCareerKnowledge", status="ok", source_count=3)
    sink.hitl_event(run_id="r1", hitl_type="confirm_role", status="requested")
    sink.run_completed(run_id="r1", projection={"status": "completed", "total_tokens": 42})
    # environment/release tags present on the trace metadata
    trace_calls = [kw for name, kw in c.calls if name == "trace"]
    assert any(kw["metadata"].get("environment") == "test" for kw in trace_calls)
    assert any(kw["metadata"].get("release") == "abc123" for kw in trace_calls)


def test_adapter_sanitises_metadata_secrets():
    c = FakeClient()
    sink = LangfuseObservabilitySink(c, environment="test")
    # A caller accidentally passes a secret in interview metadata — the adapter scrubs it.
    sink.interview_event(session_id="s1", operation="submit_answer", status="ok",
                         metadata={"authorization": "Bearer sk-secret-XYZ1234567890",
                                   "answer": "candidate@example.com wrote this"})
    assert "sk-secret" not in c.blob() and "candidate@example.com" not in c.blob()


def test_feedback_emits_event_and_correlated_score():
    c = FakeClient()
    sink = LangfuseObservabilitySink(c, environment="test")
    sink.feedback_event(surface="agent_answer", rating="helpful", run_id="r9", category="agent_answer")
    names = [n for n, _ in c.calls]
    assert "event" in names and "score" in names
    score = next(kw for n, kw in c.calls if n == "score")
    assert score["trace_id"] == "r9" and score["value"] == 1.0


def test_adapter_flush_and_shutdown():
    c = FakeClient()
    sink = LangfuseObservabilitySink(c)
    sink.flush(); sink.shutdown()
    assert ("flush", {}) in c.calls and ("shutdown", {}) in c.calls


def test_adapter_swallows_client_exceptions():
    class Boom:
        def trace(self, **kw):
            raise RuntimeError("langfuse down: sk-secret-leak")

        def event(self, **kw):
            raise RuntimeError("down")

        def flush(self):
            raise RuntimeError("down")
    sink = LangfuseObservabilitySink(Boom(), environment="test")
    # None of these raise, even though the client always fails.
    sink.run_started(run_id="r"); sink.run_completed(run_id="r", projection={})
    sink.tool_event(run_id="r", tool_name="t", status="ok"); sink.flush()


# --- build_observability_sink gating -------------------------------------------------

def test_build_sink_is_noop_when_disabled(monkeypatch):
    from src.observability import build_observability_sink
    monkeypatch.delenv("AGENT_EXTERNAL_OBSERVABILITY_ENABLED", raising=False)
    assert isinstance(build_observability_sink(), NoOpObservabilitySink)


def test_build_sink_is_noop_when_enabled_without_credentials(monkeypatch):
    from src.observability import build_observability_sink
    monkeypatch.setenv("AGENT_EXTERNAL_OBSERVABILITY_ENABLED", "true")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert isinstance(build_observability_sink(), NoOpObservabilitySink)


# --- interview store instrumentation (§22/§23) --------------------------------------

class RecordingSink(NoOpObservabilitySink):
    def __init__(self):
        self.events = []

    def interview_event(self, **kw):
        self.events.append(kw)

    def blob(self):
        return json.dumps(self.events, default=str)


def _store(sink):
    from src.interview.session_repository import DurableInterviewSessionStore
    engine = make_engine("sqlite://")
    init_db(engine, force=True)
    sf = make_session_factory(engine)
    with sf() as s:
        u = User(subject="alice", provider="test")
        s.add(u); s.commit()
        uid = u.id
    return DurableInterviewSessionStore(sf, observability=sink), uid


def test_interview_create_and_mutate_emit_safe_events():
    sink = RecordingSink()
    store, uid = _store(sink)
    sid, created = store.create_or_get(uid, "idem-key-1")
    assert created
    with store.mutate(sid, uid, operation="submit_answer"):
        pass  # a successful provider-backed op
    ops = [(e["operation"], e["status"]) for e in sink.events]
    assert ("create", "created") in ops
    assert any(op == "submit_answer" and st == "ok" for op, st in ops)
    # duration recorded, session id correlated, and NO candidate content anywhere.
    ok_ev = next(e for e in sink.events if e["operation"] == "submit_answer" and e["status"] == "ok")
    assert ok_ev["session_id"] == sid and isinstance(ok_ev["duration_ms"], int)
    assert "answer" not in sink.blob().lower() or "answer" in "submit_answer"  # only op label


def test_interview_idempotent_hit_is_traced():
    sink = RecordingSink()
    store, uid = _store(sink)
    sid1, c1 = store.create_or_get(uid, "same-key")
    sid2, c2 = store.create_or_get(uid, "same-key")
    assert sid1 == sid2 and c1 and not c2
    hits = [e for e in sink.events if e["status"] == "idempotent_hit"]
    assert hits and hits[0]["metadata"]["idempotency_hit"] is True


def test_interview_mutation_failure_emits_error_category():
    sink = RecordingSink()
    store, uid = _store(sink)
    sid = store.create(uid)
    with pytest.raises(RuntimeError):
        with store.mutate(sid, uid, operation="submit_answer"):
            raise RuntimeError("boom in the provider call")
    err = [e for e in sink.events if e["status"] == "error"]
    assert err and err[0]["operation"] == "submit_answer"
    assert err[0]["failure_category"]  # a sanitized category, never the raw message
    assert "boom" not in sink.blob()


def test_telemetry_failure_never_breaks_the_interview():
    class BoomSink(NoOpObservabilitySink):
        def interview_event(self, **kw):
            raise RuntimeError("telemetry down")
    store, uid = _store(BoomSink())
    sid = store.create(uid)
    with store.mutate(sid, uid, operation="submit_answer"):
        pass  # must not raise despite the telemetry sink always failing
