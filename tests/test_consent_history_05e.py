"""05E (W9.8-D2): legal-acceptance VERSION history. It records which document version a user acknowledged and when, is never back-filled, and is never read as consent
to anything beyond the acknowledgement. Offline; no migration (the existing acceptance rows already carry the version, which is what this exposes)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text

import tests.conftest  # noqa: F401  (isolation first)
from src import persistence as P
from src.application.account_deletion_service import AccountDeletionService
from src.persistence import Base, LegalAcceptance, make_session_factory
from src.privacy import policy as PP
from src.privacy.legal import CONSENT_HISTORY_SCOPE, LegalConflict, LegalNotFound, LegalService, LegalValidationError
from tests._auth_factories import build_auth_app, cookies_for, login_token, register, verification_token

HASH_2 = "b" * 64
HASH_3 = "c" * 64


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def tick(self, **kw) -> datetime:
        self.now += timedelta(**kw)
        return self.now


@pytest.fixture()
def world():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sf = make_session_factory(engine)
    clock = Clock()
    return sf, clock, LegalService(sf, clock)


def _user(sf) -> int:
    tag = uuid.uuid4().hex[:10]
    with sf() as s:
        u = P.User(subject=f"s-{tag}", provider="password", email=f"{tag}@example.com")
        s.add(u)
        s.commit()
        return u.id


def _publish(legal: LegalService, clock: Clock, code: str, version: str, hash_: str, actor: int) -> dict:
    d = legal.create_draft(code, version=version, content_ref=f"/{code}", content_hash=hash_, effective_at=clock(), actor_user_id=actor)
    return legal.publish(d["id"], actor_user_id=actor)


def _count(sf) -> int:
    with sf() as s:
        return s.scalar(select(func.count()).select_from(LegalAcceptance)) or 0


# ------------------------------------------------------------------------------------------------------------- never back-filled
def test_a_user_who_never_accepted_has_an_empty_truthful_history_and_nothing_creates_rows(world):
    sf, clock, legal = world
    uid, admin = _user(sf), _user(sf)
    assert legal.acceptance_history(uid)["history"] == []
    legal.ensure_baseline()
    legal.admin_overview()
    legal.for_user(uid)
    _publish(legal, clock, "terms", "2.0", HASH_2, admin)                      # publishing a new version creates no acceptance for anybody
    _publish(legal, clock, "privacy", "2.0", HASH_2, admin)
    assert _count(sf) == 0 and legal.acceptance_history(uid)["history"] == []
    status = legal.for_user(uid)
    assert all(d["accepted_current"] is False and d["last_acceptance"] is None for d in status["documents"])


def test_registration_and_sign_in_record_no_acceptance(tmp_path):
    app, repo, mail = build_auth_app()
    with TestClient(app) as client:
        assert register(client, "fresh@example.com", "password123").status_code in (200, 201)
        client.post("/api/v1/auth/verify-email", json={"token": verification_token(mail)})
        token = login_token(client, "fresh@example.com", "password123")
        with repo.session_factory() as s:
            assert s.scalar(select(func.count()).select_from(LegalAcceptance)) == 0                  # the signup source exists in the vocabulary but is not wired
        h = client.get("/api/v1/privacy/legal/history", cookies=cookies_for(token)).json()
        assert h["history"] == [] and h["scope"]["back_filled"] is False


# ------------------------------------------------------------------------------------------------------------- which version, when, how
def test_history_records_the_version_accepted_in_order_and_keeps_old_versions_after_a_new_one_is_published(world):
    sf, clock, legal = world
    uid, admin = _user(sf), _user(sf)
    legal.accept(uid, "terms")                                                  # baseline-1 at 09:00
    clock.tick(hours=2)
    v2 = _publish(legal, clock, "terms", "2.0", HASH_2, admin)
    clock.tick(hours=1)
    legal.accept(uid, "terms")                                                  # 2.0 at 12:00
    clock.tick(days=3)
    _publish(legal, clock, "terms", "3.0", HASH_3, admin)                       # published, NOT accepted
    legal.accept(uid, "privacy")                                                # privacy baseline, later
    h = legal.acceptance_history(uid)["history"]
    assert [(r["document"], r["version"]) for r in h] == [("terms", PP.BASELINE_VERSION), ("terms", "2.0"), ("privacy", PP.BASELINE_VERSION)]
    base, two, priv = h
    assert base["is_baseline"] is True and base["content_hash"] is None and base["version_effective_at"] is None and base["version_state"] == "retired"
    assert two["is_baseline"] is False and two["content_hash"] == HASH_2 and two["version_effective_at"] is not None and two["version_state"] == "retired"
    assert two["is_current"] is False and two["current_version"] == "3.0"                              # superseded by 3.0, which the user has NOT accepted
    assert priv["is_current"] is True and priv["current_version"] == PP.BASELINE_VERSION
    assert [r["accepted_at"] for r in h] == sorted(r["accepted_at"] for r in h)
    assert all(r["source"] == "settings" for r in h)
    assert v2["state"] == "published"
    assert next(d for d in legal.for_user(uid)["documents"] if d["code"] == "terms")["accepted_current"] is False


def test_accepting_twice_is_idempotent_and_never_duplicates_history(world):
    sf, clock, legal = world
    uid = _user(sf)
    legal.accept(uid, "ai_transparency")
    clock.tick(minutes=5)
    legal.accept(uid, "ai_transparency")
    assert _count(sf) == 1 and len(legal.acceptance_history(uid)["history"]) == 1


def test_only_the_current_published_version_can_be_accepted_and_the_source_is_code_defined(world):
    sf, clock, legal = world
    uid, admin = _user(sf), _user(sf)
    draft = legal.create_draft("terms", version="9.0", content_ref="/terms", content_hash=HASH_2, effective_at=clock(), actor_user_id=admin)
    legal.accept(uid, "terms")
    h = legal.acceptance_history(uid)["history"]
    assert [r["version"] for r in h] == [PP.BASELINE_VERSION]                                           # a draft is never what gets accepted
    with pytest.raises(LegalNotFound):
        legal.accept(uid, "cookies")
    with pytest.raises(LegalValidationError):
        legal.accept(uid, "terms", source="admin_recorded")                                              # an operator cannot record acceptance for somebody
    with pytest.raises(LegalValidationError):
        legal.accept(uid, "terms", source="signup-guess")
    assert _count(sf) == 1 and draft["state"] == "draft"


def test_a_published_version_is_immutable_so_the_recorded_version_keeps_meaning_one_text(world):
    sf, clock, legal = world
    uid, admin = _user(sf), _user(sf)
    pub = _publish(legal, clock, "privacy", "2.0", HASH_2, admin)
    legal.accept(uid, "privacy")
    with pytest.raises(LegalConflict):
        legal.update_draft(pub["id"], content_ref="/privacy", content_hash=HASH_3, effective_at=None)
    assert legal.acceptance_history(uid)["history"][0]["content_hash"] == HASH_2


# ------------------------------------------------------------------------------------------------------------- not consent beyond what exists
def test_the_history_states_its_scope_and_makes_no_consent_or_compliance_claim(world):
    sf, clock, legal = world
    uid = _user(sf)
    legal.accept(uid, "terms")
    out = legal.acceptance_history(uid)
    assert out["scope"] == CONSENT_HISTORY_SCOPE
    assert out["scope"]["optional_processing_consent_recorded"] is False and out["scope"]["back_filled"] is False
    note = out["scope"]["note"].lower()
    assert "not a statement of legal compliance" in note and "no record of consent to optional processing" in note
    for banned in ("gdpr", "compliant", "certified"):
        assert banned not in note


def test_the_export_carries_the_version_identity(world):
    sf, clock, legal = world
    uid, admin = _user(sf), _user(sf)
    _publish(legal, clock, "terms", "2.0", HASH_2, admin)
    legal.accept(uid, "terms")
    rows = legal.export_for_user(uid)
    assert rows == [{"document": "terms", "version": "2.0", "accepted_at": rows[0]["accepted_at"], "source": "settings", "version_is_baseline": False,
                     "version_content_hash": HASH_2}]


# ------------------------------------------------------------------------------------------------------------- isolation and deletion
def test_a_users_history_never_contains_another_users_rows(world):
    sf, clock, legal = world
    a, b = _user(sf), _user(sf)
    legal.accept(a, "terms")
    clock.tick(minutes=1)
    legal.accept(b, "terms")
    legal.accept(b, "privacy")
    assert [(r["document"]) for r in legal.acceptance_history(a)["history"]] == ["terms"]
    assert [(r["document"]) for r in legal.acceptance_history(b)["history"]] == ["terms", "privacy"]
    assert legal.acceptance_history(999999)["history"] == []


def test_account_deletion_removes_the_history_and_only_that_users(world):
    sf, clock, legal = world
    a, b = _user(sf), _user(sf)
    legal.accept(a, "terms")
    legal.accept(b, "terms")
    summary = AccountDeletionService(sf).delete_account(a)
    assert summary.legal_acceptances_deleted == 1
    assert legal.acceptance_history(a)["history"] == [] and len(legal.acceptance_history(b)["history"]) == 1
    with sf() as s:
        assert s.scalar(text("select count(*) from legal_acceptances where user_id = :u"), {"u": a}) == 0


# ------------------------------------------------------------------------------------------------------------- the route
def test_the_history_route_is_owner_scoped_authenticated_and_strict():
    hosted, _repo, _mail = build_auth_app("production")
    with TestClient(hosted) as anonymous:
        assert anonymous.get("/api/v1/privacy/legal/history").status_code == 401                       # hosted: no session, no history
    app, repo, mail = build_auth_app()
    with TestClient(app) as client:
        tokens = []
        for email in ("one@example.com", "two@example.com"):
            register(client, email, "password123")
            client.post("/api/v1/auth/verify-email", json={"token": verification_token(mail)})
            tokens.append(login_token(client, email, "password123"))
        assert client.post("/api/v1/privacy/legal/terms/accept", cookies=cookies_for(tokens[0])).status_code == 200
        mine = client.get("/api/v1/privacy/legal/history", cookies=cookies_for(tokens[0])).json()
        theirs = client.get("/api/v1/privacy/legal/history", cookies=cookies_for(tokens[1])).json()
        assert [r["document"] for r in mine["history"]] == ["terms"] and theirs["history"] == []
        assert set(mine["history"][0]) == {"document", "title", "version", "version_state", "is_baseline", "content_hash", "version_effective_at", "accepted_at", "source",
                                           "is_current", "current_version"}
        assert set(mine) == {"history", "scope"}
        assert "user_id" not in str(mine) and "ip" not in {k.lower() for k in mine["history"][0]}      # no identifier, no IP or device field exists
        assert client.get("/api/v1/privacy/legal/history?user_id=2", cookies=cookies_for(tokens[0])).json() == mine        # a client-supplied id is ignored
