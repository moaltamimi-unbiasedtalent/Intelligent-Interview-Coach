"""05E (W9.8-D9, W10.10-AUDIT-CTX): audit and incident context is allow-list enforced at the one choke point every write path shares.

Offline. Covers: the listener on both models (strict raises with KEY PATHS only; non-strict drops and records a count, never the value), every real write path
(``AuditRepository.record``, the atomic ``_stage_audit`` helper, ``build_audit``, the invitation writer, incident history), value restrictions for keys that could
carry free text, bounded shapes, the static scan of every key the source can emit, and the free-text-key guard that fails when a new suspicious key is allow-listed
without a written justification."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import create_engine, text

import tests.conftest  # noqa: F401  (isolation first)
from src import audit_allowlist as AL
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.auth_repository import AccountRepository, AuditRepository
from src.persistence import AdminIncidentEvent, AuditEvent, Base, make_session_factory
from tests._audit_scan_05e import ROOT, emitted_key_sources


@pytest.fixture()
def sf():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def _sentinel() -> str:
    return "SENTINEL-" + uuid.uuid4().hex


def _all_text(sf) -> str:
    with sf() as s:
        return " ".join(str(r[0]) for r in s.execute(text("select context from audit_events")).all())


# ---------------------------------------------------------------------------------------------------------------- the listener
def test_strict_mode_is_on_in_tests_and_rejects_an_unlisted_key_naming_the_path_not_the_value(sf):
    assert AL.strict_mode()
    secret = _sentinel()
    with pytest.raises(AL.AuditContextRejected) as exc:
        AuditRepository(sf).record(event_type="account.login", context={"free_text_note": secret})
    assert "free_text_note" in str(exc.value) and secret not in str(exc.value)
    assert "free_text_note" not in _all_text(sf) and secret not in _all_text(sf)


@pytest.mark.parametrize("context", [
    {"note": "x"}, {"email": "a@b.c"}, {"text": "hello"}, {"comment": "hello"}, {"prompt": "x"}, {"answer": "x"}, {"cv": "x"},
    {"before": {"note": "x"}}, {"scope": {"deep": {"query": "x"}}}, {"Free text key with spaces": 1}, {"UPPER": 1}, {"": 1}, {"1abc": 1},
])
def test_any_unlisted_or_non_identifier_key_is_rejected_at_any_depth(sf, context):
    with pytest.raises(AL.AuditContextRejected):
        AuditRepository(sf).record(event_type="account.login", context=context)


def test_listed_metadata_passes_unchanged_including_nested_summaries(sf):
    ctx = {"changed": {"interface_locale": "de", "target_role": "set", "display_name": "set"}, "request_type": "deletion", "count": 3, "complete": True,
           "scope": {"source_ref": "x", "period": "2024", "measure": "median"}, "reasons": ["a", "b"], "reason": "operator reason, bounded"}
    AuditRepository(sf).record(event_type="account.preferences_change", context=ctx)
    with sf() as s:
        stored = s.query(AuditEvent).one().context
    assert stored == ctx


@pytest.mark.parametrize("key, value", [("display_name", "Ada Lovelace"), ("target_role", "senior data scientist"), ("document", "my_cv.pdf")])
def test_keys_that_could_carry_free_text_accept_only_their_closed_values(sf, key, value):
    with pytest.raises(AL.AuditContextRejected):
        AuditRepository(sf).record(event_type="account.preferences_change", context={key: value})
    AuditRepository(sf).record(event_type="account.preferences_change", context={key: "set" if key != "document" else "terms"})


def test_value_shapes_are_bounded(sf):
    for bad in ({"reason": "x" * (AL.MAX_STRING + 1)}, {"reasons": ["a"] * (AL.MAX_ITEMS + 1)}, {"before": {"before": {"before": {"before": {"before": {"state": "x"}}}}}},
                {"records": {"a": object()}}):
        with pytest.raises(AL.AuditContextRejected):
            AuditRepository(sf).record(event_type="account.login", context=bad)
    big = {"reasons": ["y" * 150] * 40}                               # 40 x 150 chars is within every per-item bound but over the total
    with pytest.raises(AL.AuditContextRejected):
        AuditRepository(sf).record(event_type="account.login", context=big)


def test_a_non_object_context_is_rejected(sf):
    with pytest.raises(AL.AuditContextRejected):
        AuditRepository(sf).record(event_type="account.login", context=["not", "an", "object"])  # type: ignore[arg-type]


def test_none_and_empty_context_are_fine(sf):
    AuditRepository(sf).record(event_type="account.login", context=None)
    AuditRepository(sf).record(event_type="account.login", context={})
    with sf() as s:
        assert [r.context for r in s.query(AuditEvent).order_by(AuditEvent.id)] == [None, None]


# ---------------------------------------------------------------------------------------------------------------- non-strict: drop, never store
def test_outside_strict_mode_unlisted_entries_are_dropped_counted_and_never_stored(sf, monkeypatch):
    monkeypatch.setenv("AUDIT_CONTEXT_STRICT", "0")
    assert not AL.strict_mode()
    secret = _sentinel()
    AuditRepository(sf).record(event_type="account.login", context={"count": 2, "note": secret, "before": {"state": "a", "text": secret}, "display_name": secret})
    with sf() as s:
        row = s.query(AuditEvent).one()
    assert row.context["count"] == 2 and row.context["before"] == {"state": "a"} and "note" not in row.context and "display_name" not in row.context
    assert row.context["dropped_keys"] == 3
    assert secret not in _all_text(sf)                                    # no value of a dropped entry reaches the database in any form


def test_non_strict_logs_key_paths_only(sf, monkeypatch, caplog):
    monkeypatch.setenv("AUDIT_CONTEXT_STRICT", "0")
    secret = _sentinel()
    with caplog.at_level("WARNING", logger="ask4mo.audit.allowlist"):
        AuditRepository(sf).record(event_type="account.login", context={"note": secret})
    assert "note" in caplog.text and secret not in caplog.text


# ---------------------------------------------------------------------------------------------------------------- every write path goes through it
def test_the_atomic_stage_helper_is_covered_and_the_mutation_rolls_back_in_strict_mode(sf):
    from src.persistence import User

    with sf() as s:
        u = User(subject="a", provider="password", email="a@example.com")
        s.add(u)
        s.commit()
        uid = u.id
    repo = AccountRepository(sf)
    with pytest.raises(AL.AuditContextRejected):
        repo.set_platform_role(uid, "platform_admin", audit={"event_type": "admin.platform_role_change", "actor_user_id": None, "context": {"email": "a@example.com"}})
    with sf() as s:
        assert s.get(User, uid).platform_role == "user"                  # the audited mutation did not survive a rejected audit row
        assert s.query(AuditEvent).count() == 0


def test_build_audit_output_for_a_real_admin_event_passes(sf):
    spec = A.build_audit(event_type=A.ADMIN_PRIVACY_REQUEST_STATUS_CHANGED, actor_user_id=None, request_id="r1", target_type="privacy_request", target_id="x",
                         request_public_id="abc", old_state="submitted", new_state="acknowledged", result_category=None)
    AuditRepository(sf).record(**spec)


def test_the_invitation_writer_and_direct_orm_inserts_are_covered(sf):
    with sf() as s:
        s.add(AuditEvent(event_type="x", context={"note": "x"}))
        with pytest.raises(AL.AuditContextRejected):
            s.flush()
        s.rollback()
    with sf() as s:
        s.add(AuditEvent(event_type="x", context={"invitation_id": 1, "ttl_days": 14, "email_bound": False}))
        s.commit()


def test_incident_history_meta_is_allow_listed_separately(sf):
    from src.persistence import AdminIncident

    with sf() as s:
        inc = AdminIncident(public_id=uuid.uuid4().hex, title="t", severity="low", affected_service="agent")
        s.add(inc)
        s.flush()
        s.add(AdminIncidentEvent(incident_id=inc.id, action="updated", meta={"fields_changed": ["title"]}))
        s.commit()
        s.add(AdminIncidentEvent(incident_id=inc.id, action="updated", meta={"title": "free text about the incident"}))
        with pytest.raises(AL.AuditContextRejected):
            s.flush()
        s.rollback()
        s.add(AdminIncidentEvent(incident_id=inc.id, action="updated", meta={"fields_changed": ["root_cause"], "root_cause": "free text"}))
        with pytest.raises(AL.AuditContextRejected):
            s.flush()
        s.rollback()


def test_incident_non_strict_drops_free_text(sf, monkeypatch):
    from src.persistence import AdminIncident

    monkeypatch.setenv("AUDIT_CONTEXT_STRICT", "0")
    secret = _sentinel()
    with sf() as s:
        inc = AdminIncident(public_id=uuid.uuid4().hex, title="t", severity="low", affected_service="agent")
        s.add(inc)
        s.flush()
        s.add(AdminIncidentEvent(incident_id=inc.id, action="updated", meta={"fields_changed": ["title"], "root_cause": secret}))
        s.commit()
        meta = s.query(AdminIncidentEvent).one().meta
    assert meta == {"fields_changed": ["title"], "dropped_keys": 1} and secret not in json.dumps(meta)


# ---------------------------------------------------------------------------------------------------------------- the allow-list itself
def test_every_allowed_key_is_a_code_identifier_and_the_sets_are_consistent():
    for key in AL.ALLOWED_CONTEXT_KEYS | AL.ALLOWED_INCIDENT_META_KEYS:
        assert AL._KEY.match(key), key
    assert AL.ALLOWED_INCIDENT_META_KEYS <= AL.ALLOWED_CONTEXT_KEYS | {"dropped_keys"}


def test_the_role_value_spec_matches_the_real_role_presets_and_workspace_roles():
    from src.persistence import WORKSPACE_ROLES

    assert AL.VALUE_SPECS["target_role"] == frozenset({"set"}) | set(perm.ROLE_PRESETS) | {perm.ROLE_CANDIDATE} | set(WORKSPACE_ROLES)


# Keys whose NAME suggests free text or personal data. Each is allow-listed only with a written reason why its value cannot be free text. A NEW allow-listed key with a
# suspicious name fails this test until it is justified here; a key that is not on the allow-list cannot be stored at all.
_SUSPICIOUS = ("note", "text", "body", "comment", "content", "message", "email", "name", "phone", "address", "query", "prompt", "answer", "transcript",
               "description", "title", "summary", "detail", "reason", "path", "document", "cv", "memory", "free", "label", "subject", "input", "output", "response")
_JUSTIFIED = {
    "display_name": "value restricted to the literal 'set' (VALUE_SPECS)",
    "note_id": "an integer identifier",
    "message_id": "an integer identifier",
    "message_type": "a code-defined enum (the mail template kind)",
    "email_bound": "a boolean",
    "email_submitted": "a boolean",
    "reason": "an operator-entered reason, bounded at 200 characters, internal admin metadata (never candidate text)",
    "reason_category": "a code-defined category",
    "reason_code": "a code-defined code",
    "reasons": "a list of code-defined reason codes, bounded",
    "path": "the request URL PATH only (query string never recorded), at most 200 characters",
    "document": "value restricted to the three legal document codes (VALUE_SPECS)",
    "response_detail": "a code-defined enum (brief or detailed)",
    "subject_type": "a code-defined enum",
    "subject_user_id": "an integer identifier",
    "request_type": "a code-defined enum",
    "request_public_id": "an opaque public id",
}


def test_a_new_allow_listed_key_with_a_free_text_looking_name_needs_a_written_justification():
    unjustified = sorted(k for k in AL.ALLOWED_CONTEXT_KEYS | AL.ALLOWED_INCIDENT_META_KEYS
                         if any(w in k for w in _SUSPICIOUS) and k not in _JUSTIFIED)
    assert unjustified == [], f"allow-listed keys that look like free text without a justification: {unjustified}"
    stale = sorted(k for k in _JUSTIFIED if k not in AL.ALLOWED_CONTEXT_KEYS)
    assert stale == [], stale


def test_no_forbidden_fragment_key_slipped_onto_the_list_except_the_two_documented_code_valued_keys():
    leaked = sorted(k for k in AL.ALLOWED_CONTEXT_KEYS if any(f in k for f in A._FORBIDDEN_CONTEXT_FRAGMENTS))
    # "document": the legal document CODE (terms/privacy/ai_transparency), value-restricted. "conversation_language": the language CODE chosen in Preferences (a closed enum
    # validated before it is audited), not conversation content.
    assert leaked == ["conversation_language", "document"]


# ---------------------------------------------------------------------------------------------------------------- the static scan
def test_every_context_key_the_source_can_emit_is_allow_listed():
    offenders = sorted({(k, kind, rel) for k, (kind, rel) in emitted_key_sources()
                        if k not in (AL.ALLOWED_CONTEXT_KEYS if kind == "audit" else AL.ALLOWED_INCIDENT_META_KEYS)})
    assert offenders == [], f"audit/incident context keys emitted by the source but not allow-listed: {offenders}"


def test_the_scan_finds_a_new_free_text_key_in_a_synthetic_module(tmp_path):
    (tmp_path / "bad.py").write_text(
        "from src.application import admin_audit as A\n"
        "def f(repo):\n"
        "    A.build_audit(event_type='admin.access.denied', actor_user_id=1, request_id=None, free_text_note='x')\n"
        "    repo.record(event_type='x', context={'candidate_answer': 'y', 'scope': {'nested_comment': 'z'}})\n"
        "def g(s, inc):\n"
        "    _event(s, inc, action='x', meta={'root_cause_text': 'q'})\n", encoding="utf-8")
    import tests._audit_scan_05e as scan

    found = {(k, kind) for k, (kind, _rel) in _scan_in(scan, tmp_path)}
    assert {("free_text_note", "audit"), ("candidate_answer", "audit"), ("nested_comment", "audit"), ("root_cause_text", "incident")} <= found
    assert not ({"free_text_note", "candidate_answer", "nested_comment", "root_cause_text"} & AL.ALLOWED_CONTEXT_KEYS)


def _scan_in(scan, directory):
    """Run the scanner over a disposable directory (its relative_to(ROOT) is bypassed by monkeypatching ROOT to the directory)."""
    original = scan.ROOT
    scan.ROOT = directory
    try:
        return scan.emitted_key_sources([directory])
    finally:
        scan.ROOT = original


def test_the_repository_root_is_the_real_project_root():
    assert (ROOT / "src" / "audit_allowlist.py").is_file()
