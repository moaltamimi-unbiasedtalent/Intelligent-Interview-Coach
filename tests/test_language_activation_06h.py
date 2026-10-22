"""06H (REQ-LANG-11/13/14, LG-01..LG-14, OD-LANG-03/04): fail-closed language activation control.

Deterministic, 0 paid/live calls, no network. The mechanism is proven ONLY with synthetic fixtures (``tests/fixtures/language_qualification``)
injected through the test-only seam; the committed readiness record keeps zero qualified languages and a test asserts it.
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src import language_activation as la
from src.api import dependencies as deps
from src.api.main import create_app
from src.locales import ACTIVE_CANDIDATE_LOCALES
from tests._auth_factories import build_auth_app, cookies_for, login_token, register

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "language_qualification"
COMMITTED = ROOT / "docs" / "production" / "execution" / "language_readiness.json"
PW = "correcthorsebattery"
TODAY = date(2026, 10, 22)
SEVEN = ("en", "de", "fr", "es", "it", "pt", "nl")


def fixture(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _clean_seam():
    la.reset_for_tests()
    yield
    la.reset_for_tests()


@pytest.fixture
def hosted(monkeypatch):
    """Returns a switch: call it AFTER the app has started (hosted startup validation needs a full hosted configuration, which tests do not have)."""
    def go(env: str = "production") -> None:
        monkeypatch.setenv("API_ENV", env)
    return go


def _gate(rec: dict, g: str = "LG-05") -> dict:
    return rec["languages"]["de"]["gates"][g]


# ---- the committed record: zero qualified languages (06A truth) ----------------------------------------------------------------------------------------
def test_committed_record_has_zero_qualified_languages_and_enforced_mode_offers_nothing():
    data, err = la.load_committed()
    assert err is None and data is not None
    act = la.resolve(data, la.MODE_ENFORCED, today=TODAY)
    assert act.qualified == () and act.offered == () and act.none_available
    for code in SEVEN:
        assert act.locales[code].state != "QUALIFIED", code
        assert data["languages"][code]["production_qualified"] is False
        assert data["languages"][code]["offered_to_real_users"] is False
    assert not any(act.accepts(c) for c in (*SEVEN, "ru", None, ""))  # English is NOT an implicit exception


def test_committed_record_gates_are_not_all_pass_with_the_new_approval_fields():
    data, _ = la.load_committed()
    for code, rec in data["languages"].items():
        assert "release_sha" not in rec, f"{code}: a locale release SHA needs a real approval, not an engineering edit"
        for g, e in rec["gates"].items():
            if e["state"] == "PASS":  # 06A engineering PASS (LG-01, LG-14): never an approval
                assert "approver" not in e and "approved_on" not in e, (code, g)


def test_labelled_mode_keeps_the_seven_selectable_but_all_unqualified():
    data, _ = la.load_committed()
    act = la.resolve(data, la.MODE_LABELLED, today=TODAY)
    assert act.offered == SEVEN and act.qualified == ()
    assert act.unqualified_offered == SEVEN and not act.none_available
    assert not act.accepts("ru")


# ---- mode: server-decided from API_ENV; unknown fails closed ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("env,mode", [("development", "labelled"), ("dev", "labelled"), ("local", "labelled"), ("test", "labelled"), ("testing", "labelled"),
                                      ("staging", "enforced"), ("production", "enforced"), ("prod", "enforced"), ("preview", "enforced"), ("", "labelled"), ("PRODUCTION", "enforced")])
def test_activation_mode_from_environment(env, mode):
    assert la.activation_mode({"API_ENV": env}) == mode


def test_missing_api_env_is_development():
    assert la.activation_mode({}) == la.MODE_LABELLED


# ---- the mechanism, proven with a synthetic fully approved record -------------------------------------------------------------------------------------
def test_a_fully_approved_synthetic_locale_enables_exactly_that_locale():
    data = fixture("approved_synthetic")
    enforced = la.resolve(data, la.MODE_ENFORCED, today=TODAY)
    assert enforced.qualified == ("de",) and enforced.offered == ("de",)
    assert enforced.accepts("de") and not enforced.accepts("en") and not enforced.accepts("fr") and not enforced.accepts("ru")
    assert enforced.locales["de"].state == "QUALIFIED" and enforced.locales["de"].gates_pass == 14
    labelled = la.resolve(data, la.MODE_LABELLED, today=TODAY)
    assert labelled.offered == SEVEN and labelled.qualified == ("de",)
    assert labelled.unqualified_offered == tuple(c for c in SEVEN if c != "de")


@pytest.mark.parametrize("name", ["forged_status_only", "stale_evidence", "partial_approval"])
def test_each_committed_defective_fixture_qualifies_nothing(name):
    act = la.resolve(fixture(name), la.MODE_ENFORCED, today=TODAY)
    assert act.qualified == () and act.offered == () and act.none_available


def _mut(fn):
    def apply(d):
        fn(d)
        return d
    return apply


DEFECTS = {
    "remove approver": lambda d: _gate(d).pop("approver"),
    "empty approver": lambda d: _gate(d).update(approver=""),
    "placeholder approver": lambda d: _gate(d).update(approver="TBD"),
    "unnamed approver": lambda d: _gate(d).update(approver="approver"),
    "automation approver": lambda d: _gate(d).update(approver="Claude"),
    "engineering approver": lambda d: _gate(d).update(approver="Engineering team"),
    "non-string approver": lambda d: _gate(d).update(approver=42),
    "remove evidence": lambda d: _gate(d).pop("evidence"),
    "blank evidence": lambda d: _gate(d).update(evidence="   "),
    "placeholder evidence": lambda d: _gate(d).update(evidence="TBD"),
    "remove date": lambda d: _gate(d).pop("approved_on"),
    "malformed date": lambda d: _gate(d).update(approved_on="22/10/2026"),
    "impossible date": lambda d: _gate(d).update(approved_on="2026-13-45"),
    "future date": lambda d: _gate(d).update(approved_on="2026-10-23"),
    "remove gate sha": lambda d: _gate(d).pop("release_sha"),
    "malformed gate sha": lambda d: _gate(d).update(release_sha="not-a-sha"),
    "stale gate sha": lambda d: _gate(d).update(release_sha="fedcba9876543210fedcba9876543210fedcba98"),
    "expired approval": lambda d: _gate(d).update(approved_until="2026-10-21"),
    "malformed approved_until": lambda d: _gate(d).update(approved_until="soon"),
    "gate not run": lambda d: _gate(d).update(state="NOT RUN"),
    "gate engineering draft": lambda d: _gate(d).update(state="ENGINEERING DRAFT"),
    "gate not started": lambda d: _gate(d).update(state="NOT STARTED"),
    "invalid state": lambda d: _gate(d).update(state="PASSED"),
    "lowercase state": lambda d: _gate(d).update(state="pass"),
    "missing gate": lambda d: d["languages"]["de"]["gates"].pop("LG-14"),
    "unknown gate": lambda d: d["languages"]["de"]["gates"].update({"LG-15": copy.deepcopy(_gate(d))}),
    "unknown extra gate": lambda d: d["languages"]["de"]["gates"].update({"LG-00": copy.deepcopy(_gate(d))}),
    "thirteen gates": lambda d: d["languages"]["de"]["gates"].pop("LG-01"),
    "fifteen gates": lambda d: d["languages"]["de"]["gates"].update({"X": {}}),
    "gates not an object": lambda d: d["languages"]["de"].update(gates=[]),
    "locale record not an object": lambda d: d["languages"].update(de="PASS"),
    "no locale sha": lambda d: d["languages"]["de"].pop("release_sha"),
    "malformed locale sha": lambda d: d["languages"]["de"].update(release_sha="zzz"),
    "locale sha differs from every gate": lambda d: d["languages"]["de"].update(release_sha="abcdef1234567"),
    "claim production_qualified false": lambda d: d["languages"]["de"].update(production_qualified=False),
    "claim offered false": lambda d: d["languages"]["de"].update(offered_to_real_users=False),
    "claim as string": lambda d: d["languages"]["de"].update(production_qualified="true"),
}


@pytest.mark.parametrize("defect", sorted(DEFECTS))
def test_each_single_defect_disables_the_locale(defect):
    data = fixture("approved_synthetic")
    assert la.resolve(data, la.MODE_ENFORCED, today=TODAY).qualified == ("de",)  # baseline is genuinely qualified
    DEFECTS[defect](data)
    act = la.resolve(data, la.MODE_ENFORCED, today=TODAY)
    assert act.qualified == () and not act.accepts("de"), defect
    assert la.validate_locale_record("de", data["languages"]["de"], today=TODAY).problems


def test_only_the_defective_gate_in_one_locale_disables_that_locale_not_another():
    data = fixture("approved_synthetic")
    data["languages"]["fr"] = copy.deepcopy(data["languages"]["de"])
    assert la.resolve(data, la.MODE_ENFORCED, today=TODAY).qualified == ("de", "fr")
    _gate(data).update(approver="")
    assert la.resolve(data, la.MODE_ENFORCED, today=TODAY).qualified == ("fr",)


def test_flipping_status_strings_and_flags_alone_cannot_enable_a_language():
    data, _ = la.load_committed()
    forged = copy.deepcopy(data)
    for e in forged["languages"]["de"]["gates"].values():
        e["state"] = "PASS"
        e["evidence"] = "docs/production/execution/evidence/06A_EVIDENCE.md"
    forged["languages"]["de"]["production_qualified"] = True
    forged["languages"]["de"]["offered_to_real_users"] = True
    st = la.validate_locale_record("de", forged["languages"]["de"], today=TODAY)
    assert not st.qualified and st.gates_pass == 14
    assert any("approver" in p for p in st.problems) and any("date" in p for p in st.problems) and any("SHA" in p for p in st.problems)
    assert la.resolve(forged, la.MODE_ENFORCED, today=TODAY).offered == ()


def test_the_clock_makes_a_dated_approval_stale_and_the_gate_sha_binding_is_exact():
    data = fixture("approved_synthetic")
    _gate(data).update(approved_until="2026-12-31")
    assert la.resolve(data, la.MODE_ENFORCED, today=date(2026, 12, 31)).qualified == ("de",)
    assert la.resolve(data, la.MODE_ENFORCED, today=date(2027, 1, 1)).qualified == ()
    # approval dated today is allowed; tomorrow is a future date
    d2 = fixture("approved_synthetic")
    _gate(d2).update(approved_on="2026-10-22")
    assert la.resolve(d2, la.MODE_ENFORCED, today=TODAY).qualified == ("de",)
    assert la.resolve(d2, la.MODE_ENFORCED, today=date(2026, 10, 21)).qualified == ()


# ---- unreadable, malformed, duplicated and missing records fail closed --------------------------------------------------------------------------------
def test_duplicate_gate_and_locale_keys_are_rejected():
    text = (FIX / "approved_synthetic.json").read_text(encoding="utf-8")
    dup_gate = text.replace('"LG-02": {', '"LG-01": {', 1)  # a second "LG-01" key
    with pytest.raises(la.ReadinessFormatError):
        la.parse_readiness_text(dup_gate)
    dup_locale = text.replace('"languages": {', '"languages": {"de": {}, ', 1)
    with pytest.raises(la.ReadinessFormatError):
        la.parse_readiness_text(dup_locale)


@pytest.mark.parametrize("content", ["", "{", "not json", "[]", "null", '"x"', '{"languages": 5}', '{"languages": []}'])
def test_unusable_record_text_fails_closed_for_every_locale(tmp_path, content):
    p = tmp_path / "r.json"
    p.write_text(content, encoding="utf-8")
    data, err = la.load_committed(p)
    act = la.resolve(data, la.MODE_ENFORCED, today=TODAY, file_error=err)
    assert act.offered == () and act.qualified == () and act.none_available
    assert la.resolve(data, la.MODE_LABELLED, today=TODAY, file_error=err).qualified == ()  # labelled mode never turns a bad record into a qualification


def test_missing_record_fails_closed(tmp_path):
    data, err = la.load_committed(tmp_path / "absent.json")
    assert data is None and err
    assert la.resolve(data, la.MODE_ENFORCED, file_error=err).offered == ()


def test_error_text_never_echoes_record_content(tmp_path):
    p = tmp_path / "r.json"
    p.write_text('{"secret": "TOP-SECRET-VALUE", ', encoding="utf-8")
    _, err = la.load_committed(p)
    assert err and "TOP-SECRET-VALUE" not in err


# ---- Russian (LG-14) and unknown locales are never activatable ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("stray", ["ru", "zh", "hi", "ar", "xx"])
def test_a_record_for_a_non_active_locale_makes_the_file_untrustworthy(stray):
    data = fixture("approved_synthetic")
    data["languages"][stray] = copy.deepcopy(data["languages"]["de"])
    act = la.resolve(data, la.MODE_ENFORCED, today=TODAY)
    assert act.offered == () and act.qualified == () and act.file_error


def test_russian_is_not_accepted_in_any_mode_even_with_a_complete_record():
    data = fixture("approved_synthetic")
    for mode in (la.MODE_ENFORCED, la.MODE_LABELLED):
        assert not la.resolve(data, mode, today=TODAY).accepts("ru")
    assert "ru" not in la.GATES and "ru" not in ACTIVE_CANDIDATE_LOCALES


# ---- the test-only seam is unreachable outside the test harness --------------------------------------------------------------------------------------
def test_seam_refuses_without_the_pytest_harness_in_a_clean_process():
    code = ("import sys; sys.path.insert(0, %r)\n"
            "from src import language_activation as la\n"
            "try:\n    la.install_test_records({'languages': {}})\nexcept RuntimeError:\n    print('refused')\n"
            "else:\n    print('ACCEPTED')\n") % str(ROOT)
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, cwd=str(ROOT), timeout=60)
    assert out.stdout.strip() == "refused", out.stderr


def test_seam_refuses_when_the_test_marker_is_absent(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(RuntimeError):
        la.install_test_records(fixture("approved_synthetic"))


def test_no_production_module_reaches_the_seam():
    offenders = []
    for p in (ROOT / "src").rglob("*.py"):
        if p.name == "language_activation.py":
            continue
        text = p.read_text(encoding="utf-8")
        if "install_test_records" in text or "reset_for_tests" in text or "_test_records" in text:
            offenders.append(str(p.relative_to(ROOT)))
    assert offenders == []


def test_the_record_is_code_and_file_defined_not_environment_or_database_configurable():
    src = (ROOT / "src" / "language_activation.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import) (sqlalchemy|src\.repository|src\.persistence)", src, re.M)
    environ_reads = re.findall(r"environ(?:\.get)?\(?[\[\"']([A-Z_]+)", src)
    assert set(environ_reads) <= {"API_ENV", "PYTEST_CURRENT_TEST"}, environ_reads  # the mode and the harness marker only; never the record
    assert "READINESS_PATH" in src


def test_image_ships_the_record():
    docker = (ROOT / "deploy" / "Dockerfile.api").read_text(encoding="utf-8")
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "COPY docs/production/execution/language_readiness.json" in docker
    assert "!docs/production/execution/language_readiness.json" in ignore
    assert la.READINESS_PATH == COMMITTED


# ---- HTTP: capabilities ----------------------------------------------------------------------------------------------------------------------------------
def _caps(client):
    return client.get("/api/v1/capabilities").json()


def test_capabilities_in_development_offer_seven_labelled_unqualified():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        body = _caps(c)
    assert body["active_candidate_locales"] == list(SEVEN) and body["unqualified_locales"] == list(SEVEN)
    assert body["qualified_locales"] == [] and body["language_activation_mode"] == "labelled" and body["no_language_available"] is False


def test_capabilities_in_a_hosted_environment_offer_nothing_when_no_locale_qualifies(hosted):
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        hosted()
        body = _caps(c)
    assert body["active_candidate_locales"] == [] and body["qualified_locales"] == [] and body["unqualified_locales"] == []
    assert body["no_language_available"] is True and body["language_activation_mode"] == "enforced"


def test_capabilities_in_a_hosted_environment_offer_only_the_synthetic_qualified_locale(hosted):
    la.install_test_records(fixture("approved_synthetic"))
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        hosted()
        body = _caps(c)
    assert body["active_candidate_locales"] == ["de"] and body["qualified_locales"] == ["de"] and body["no_language_available"] is False
    assert "approver" not in json.dumps(body).lower() and "release_sha" not in json.dumps(body)


# ---- HTTP: every entry point 06A guards ------------------------------------------------------------------------------------------------------------
def _signed_in(client, email="a@example.com"):
    register(client, email, PW)
    return cookies_for(login_token(client, email, PW))


def _code(resp) -> str | None:
    try:
        return resp.json().get("error", {}).get("code")
    except ValueError:
        return None


def test_preferences_refuse_an_unactivated_locale_and_accept_the_activated_one(monkeypatch):
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        ck = _signed_in(c)
        monkeypatch.setenv("API_ENV", "production")
        la.install_test_records(fixture("approved_synthetic"))
        r = c.patch("/api/v1/auth/preferences", json={"interface_locale": "fr"}, cookies=ck)
        assert r.status_code == 422 and _code(r) == "language_not_activated"
        r = c.patch("/api/v1/auth/preferences", json={"conversation_language": "en"}, cookies=ck)
        assert r.status_code == 422 and _code(r) == "language_not_activated"
        r = c.patch("/api/v1/auth/preferences", json={"interface_locale": "de", "conversation_language": "fr"}, cookies=ck)
        assert r.status_code == 422 and _code(r) == "language_not_activated"  # one bad field refuses the request before any write
        r = c.patch("/api/v1/auth/preferences", json={"interface_locale": "de", "conversation_language": "de"}, cookies=ck)
        assert r.status_code == 200, r.text
        r = c.patch("/api/v1/auth/preferences", json={"response_detail": "detailed"}, cookies=ck)  # not a language change: unaffected
        assert r.status_code == 200, r.text
        # 06A rejection path is unchanged: an excluded locale is still the standard validation error
        r = c.patch("/api/v1/auth/preferences", json={"interface_locale": "ru"}, cookies=ck)
        assert r.status_code == 422 and _code(r) == "invalid_request"


def test_a_refused_preference_does_not_change_the_stored_value(monkeypatch):
    from src.persistence import UserPreference

    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        ck = _signed_in(c)
        c.patch("/api/v1/auth/preferences", json={"interface_locale": "fr"}, cookies=ck)  # development: accepted
        monkeypatch.setenv("API_ENV", "production")
        r = c.patch("/api/v1/auth/preferences", json={"interface_locale": "es"}, cookies=ck)
        assert _code(r) == "language_not_activated"
    with repo.session_factory() as s:
        assert s.scalars(select(UserPreference.interface_locale)).all() == ["fr"]


def test_registration_refuses_an_unactivated_or_default_locale_in_a_hosted_environment(monkeypatch):
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        monkeypatch.setenv("API_ENV", "production")
        la.install_test_records(fixture("approved_synthetic"))
        r = c.post("/api/v1/auth/register", json={"email": "x@example.com", "password": PW, "locale": "fr"})
        assert r.status_code == 422 and _code(r) == "language_not_activated"
        r = c.post("/api/v1/auth/register", json={"email": "x@example.com", "password": PW})  # omitted = default English: not exempt
        assert r.status_code == 422 and _code(r) == "language_not_activated"
        r = c.post("/api/v1/auth/register", json={"email": "y@example.com", "password": PW, "locale": "de"})
        assert r.status_code == 201, r.text


def test_when_no_locale_qualifies_every_new_activity_is_refused_visibly_and_safely(monkeypatch):
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        ck = _signed_in(c)
        monkeypatch.setenv("API_ENV", "staging")
        for lang in SEVEN:
            r = c.patch("/api/v1/auth/preferences", json={"conversation_language": lang}, cookies=ck)
            assert r.status_code == 422 and _code(r) == "language_not_activated", lang
            r = c.post("/api/v1/auth/register", json={"email": f"{lang}@example.com", "password": PW, "locale": lang})
            assert r.status_code == 422 and _code(r) == "language_not_activated", lang
        body = r.json()["error"]
        assert body["message"] == la.ERROR_MESSAGE and "locale" not in body["message"].lower()
        # not a language change: account controls keep working (privacy, deletion and sign-out are never language-gated)
        assert c.get("/api/v1/auth/me", cookies=ck).status_code == 200


def _stub_app():
    app = create_app()
    app.dependency_overrides[deps.get_current_user_id] = lambda: 1
    app.dependency_overrides[deps.get_agent_service] = lambda: object()
    app.dependency_overrides[deps.get_career_service] = lambda: object()
    return app


def test_agent_run_and_career_chat_refuse_unactivated_languages(hosted):
    la.install_test_records(fixture("approved_synthetic"))
    with TestClient(_stub_app(), raise_server_exceptions=False) as c:
        hosted()
        for path, base in (("/api/v1/agent/run", {"goal": "Prepare me"}), ("/api/v1/career/chat", {"question": "How do I prepare?"})):
            for lang in ("fr", "en", None):
                body = dict(base) if lang is None else {**base, "conversation_language": lang}
                r = c.post(path, json=body)
                assert r.status_code == 422 and _code(r) == "language_not_activated", (path, lang, r.text)
            r = c.post(path, json={**base, "conversation_language": "ru"})
            assert r.status_code == 422 and _code(r) == "invalid_request", path  # 06A path unchanged
            r = c.post(path, json={**base, "conversation_language": "de"})
            assert _code(r) != "language_not_activated", path  # reaches the (stubbed) service


def test_agent_run_and_career_chat_refuse_everything_when_none_qualify(hosted):
    with TestClient(_stub_app(), raise_server_exceptions=False) as c:
        hosted()
        for path, base in (("/api/v1/agent/run", {"goal": "Prepare me"}), ("/api/v1/career/chat", {"question": "How do I prepare?"})):
            for lang in (None, *SEVEN):
                body = dict(base) if lang is None else {**base, "conversation_language": lang}
                r = c.post(path, json=body)
                assert r.status_code == 422 and _code(r) == "language_not_activated", (path, lang)


def _interview_client(tmp_path):
    from tests.test_api import _FakeRepo
    from tests.test_wave4_language_api import _svc
    from src.interview.session_repository import DurableInterviewSessionStore
    from src.persistence import init_db, make_engine, make_session_factory

    engine = make_engine(f"sqlite:///{tmp_path / 'iv.db'}")
    init_db(engine, force=True)
    store = DurableInterviewSessionStore(make_session_factory(engine))
    app = create_app()
    app.dependency_overrides[deps.get_interview_service] = _svc
    app.dependency_overrides[deps.get_repository] = lambda: _FakeRepo()
    app.dependency_overrides[deps.get_app_config] = lambda: None
    app.dependency_overrides[deps.get_session_store] = lambda: store
    app.dependency_overrides[deps.get_current_user_id] = lambda: 1
    return TestClient(app, raise_server_exceptions=False)


def _cfg(lang=None):
    cfg = {"target_role": "Registered Nurse", "industry_or_sector": "healthcare", "career_level": "senior", "number_of_questions": 2}
    if lang is not None:
        cfg["conversation_language"] = lang
    return {"configuration": cfg}


def test_interview_create_accepts_only_activated_languages(tmp_path, hosted):
    la.install_test_records(fixture("approved_synthetic"))
    with _interview_client(tmp_path) as c:
        hosted()
        for lang in ("fr", "en", None):
            r = c.post("/api/v1/interviews", json=_cfg(lang))
            assert r.status_code == 422 and _code(r) == "language_not_activated", (lang, r.text)
        ctx = {"preparation_context": {"target_role": "PM"}, "industry_or_sector": "tech", "career_level": "senior"}
        r = c.post("/api/v1/interviews", json=ctx)
        assert r.status_code == 422 and _code(r) == "language_not_activated"
        r = c.post("/api/v1/interviews", json={**ctx, "conversation_language": "fr"})
        assert r.status_code == 422 and _code(r) == "language_not_activated"
        r = c.post("/api/v1/interviews", json=_cfg("de"))
        assert r.status_code == 200, r.text


def test_interview_create_refuses_everything_when_none_qualify(tmp_path, hosted):
    with _interview_client(tmp_path) as c:
        hosted()
        for lang in (None, *SEVEN):
            r = c.post("/api/v1/interviews", json=_cfg(lang))
            assert r.status_code == 422 and _code(r) == "language_not_activated", lang


def test_development_keeps_every_entry_point_open(tmp_path):
    with _interview_client(tmp_path) as c:
        for lang in (None, *SEVEN):
            assert c.post("/api/v1/interviews", json=_cfg(lang)).status_code == 200, lang
    with TestClient(_stub_app(), raise_server_exceptions=False) as c:
        r = c.post("/api/v1/agent/run", json={"goal": "Prepare me", "conversation_language": "fr"})
        assert _code(r) != "language_not_activated"


def test_existing_sessions_in_an_unactivated_language_are_not_deleted_or_reread_through_the_guard(tmp_path, monkeypatch):
    with _interview_client(tmp_path) as c:
        sid = c.post("/api/v1/interviews", json=_cfg("fr")).json()["session_id"]
        monkeypatch.setenv("API_ENV", "production")
        assert c.get(f"/api/v1/interviews/{sid}").status_code == 200  # reading an existing session is not new activity


# ---- Admin read: counts and states only, no new permission -------------------------------------------------------------------------------------------
def test_admin_readiness_row_carries_counts_and_states_only(hosted):
    hosted()
    from src.application import admin_readiness as ar
    from src.application.admin_permissions import OVERVIEW_READ

    la.install_test_records(fixture("approved_synthetic"))
    out = ar.capability_readiness(allowed=frozenset({OVERVIEW_READ}))
    row = next(r for r in out["capabilities"] if r["id"] == "language_activation")
    assert row["status"] == "READ_ONLY" and "1 of 7 locales qualified" in row["evidence"]
    text = json.dumps(row)
    assert "Synthetic Fixture Reviewer" not in text and "synthetic://" not in text and "0123456789abcdef" not in text
    assert "language_activation" not in {r["id"] for r in ar.capability_readiness(allowed=frozenset())["capabilities"]}  # follows the caller's read permission


def test_admin_summary_has_counts_not_evidence():
    s = la.admin_summary(la.resolve(fixture("partial_approval"), la.MODE_ENFORCED, today=TODAY))
    assert s["locales"]["de"] == {"gates_passed": 13, "gates_total": 14, "state": "INCOMPLETE", "open_problems": 1}
    assert s["locales"]["fr"]["state"] == "UNQUALIFIED" and s["none_available"] is True


# ---- the 06A inventory freshness check is not loosened, and Admin stays English-only --------------------------------------------------------------
def test_eval_locale_inventory_still_compares_the_committed_audit_exactly():
    text = (ROOT / "scripts" / "eval_locale_inventory.py").read_text(encoding="utf-8")
    assert "stale" in text and "build_markdown()" in text  # the freshness comparison is untouched by 06H
