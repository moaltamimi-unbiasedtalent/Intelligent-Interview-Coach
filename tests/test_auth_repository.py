"""Unit tests for the identity repositories (Capstone P1/E1).

Real SQLite (in-memory), no network. Covers session expiry/revocation, single-use &
expiring tokens (replay protection), and OIDC account linking / duplicate-email rules.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from src.auth_repository import (
    AccountRepository,
    AuditRepository,
    SessionRepository,
    TokenRepository,
)
from src.persistence import (
    TOKEN_PURPOSE_EMAIL_VERIFICATION,
    TOKEN_PURPOSE_PASSWORD_RESET,
    Base,
    make_session_factory,
)


@pytest.fixture()
def sf():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def _user(sf, email="u@example.com"):
    return AccountRepository(sf).create_password_account(
        email=email, password_hash="x", display_name=None
    )


# --- sessions ----------------------------------------------------------------


def test_session_resolve_and_revoke(sf):
    uid = _user(sf)
    sessions = SessionRepository(sf)
    sessions.create(token_hash="h1", user_id=uid, ttl_seconds=3600)
    assert sessions.resolve("h1") == uid
    assert sessions.revoke("h1") is True
    assert sessions.resolve("h1") is None  # revoked → no grant
    assert sessions.revoke("h1") is False  # idempotent


def test_expired_session_rejected(sf):
    uid = _user(sf)
    sessions = SessionRepository(sf)
    sessions.create(token_hash="h2", user_id=uid, ttl_seconds=-1)  # already expired
    assert sessions.resolve("h2") is None


def test_revoke_all_for_user(sf):
    uid = _user(sf)
    sessions = SessionRepository(sf)
    sessions.create(token_hash="a", user_id=uid, ttl_seconds=3600)
    sessions.create(token_hash="b", user_id=uid, ttl_seconds=3600)
    assert sessions.revoke_all_for_user(uid) == 2
    assert sessions.resolve("a") is None and sessions.resolve("b") is None


def test_unknown_session_returns_none(sf):
    assert SessionRepository(sf).resolve("does-not-exist") is None


# --- tokens (single-use, expiring) -------------------------------------------


def test_token_single_use(sf):
    uid = _user(sf)
    toks = TokenRepository(sf)
    toks.issue(token_hash="t1", user_id=uid, purpose=TOKEN_PURPOSE_EMAIL_VERIFICATION, ttl_seconds=3600)
    assert toks.consume(token_hash="t1", purpose=TOKEN_PURPOSE_EMAIL_VERIFICATION) == uid
    # Replay → None (already consumed).
    assert toks.consume(token_hash="t1", purpose=TOKEN_PURPOSE_EMAIL_VERIFICATION) is None


def test_token_wrong_purpose_rejected(sf):
    uid = _user(sf)
    toks = TokenRepository(sf)
    toks.issue(token_hash="t2", user_id=uid, purpose=TOKEN_PURPOSE_PASSWORD_RESET, ttl_seconds=3600)
    # Consuming with the wrong purpose must not succeed.
    assert toks.consume(token_hash="t2", purpose=TOKEN_PURPOSE_EMAIL_VERIFICATION) is None
    # Correct purpose still works afterwards.
    assert toks.consume(token_hash="t2", purpose=TOKEN_PURPOSE_PASSWORD_RESET) == uid


def test_expired_token_rejected(sf):
    uid = _user(sf)
    toks = TokenRepository(sf)
    toks.issue(token_hash="t3", user_id=uid, purpose=TOKEN_PURPOSE_PASSWORD_RESET, ttl_seconds=-1)
    assert toks.consume(token_hash="t3", purpose=TOKEN_PURPOSE_PASSWORD_RESET) is None


# --- OIDC account linking / duplicate email ----------------------------------


def test_oidc_creates_then_reuses_identity(sf):
    accounts = AccountRepository(sf)
    uid1 = accounts.link_or_create_oidc(
        provider="google", provider_subject="sub-1", email="g@example.com",
        email_verified=True, display_name="G",
    )
    uid2 = accounts.link_or_create_oidc(
        provider="google", provider_subject="sub-1", email="g@example.com",
        email_verified=True, display_name="G",
    )
    assert uid1 == uid2  # same (provider, subject) → same principal


def test_oidc_links_to_existing_account_on_verified_email(sf):
    accounts = AccountRepository(sf)
    pw_uid = accounts.create_password_account(email="dual@example.com", password_hash="x", display_name=None)
    linked = accounts.link_or_create_oidc(
        provider="google", provider_subject="sub-2", email="dual@example.com",
        email_verified=True, display_name=None,
    )
    assert linked == pw_uid  # linked to the existing password account (same email)
    acct = accounts.get_account(pw_uid)
    assert "google" in acct.providers and "password" in acct.providers


def test_oidc_does_not_link_on_unverified_email(sf):
    accounts = AccountRepository(sf)
    pw_uid = accounts.create_password_account(email="safe@example.com", password_hash="x", display_name=None)
    other = accounts.link_or_create_oidc(
        provider="google", provider_subject="sub-3", email="safe@example.com",
        email_verified=False, display_name=None,  # provider did NOT verify
    )
    assert other != pw_uid  # must NOT hijack an account on an unverified email


# --- entitlement / role setters ----------------------------------------------


def test_tier_and_role_setters(sf):
    accounts = AccountRepository(sf)
    uid = accounts.create_password_account(email="e@example.com", password_hash="x", display_name=None)
    assert accounts.get_account(uid).tier == "basic"
    accounts.set_tier(uid, "premium", source="test")
    assert accounts.get_account(uid).tier == "premium"
    accounts.set_platform_role(uid, "platform_admin")
    assert accounts.get_account(uid).platform_role == "platform_admin"


# --- audit -------------------------------------------------------------------


def test_audit_record_and_read(sf):
    uid = _user(sf)
    audit = AuditRepository(sf)
    audit.record(event_type="account.login", result="success", actor_user_id=uid)
    rows = audit.recent_for_actor(uid)
    assert rows and rows[0]["event_type"] == "account.login"
