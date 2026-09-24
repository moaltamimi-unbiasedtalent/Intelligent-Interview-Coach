"""Unit tests for the authorization foundation (Capstone P1/E1)."""

from __future__ import annotations

from src.application.authorization import (
    BASIC_CAPABILITIES,
    PREMIUM_CAPABILITIES,
    Capability,
    Principal,
    capabilities_for,
    flag_enabled,
    has_capability,
    is_platform_admin,
)


def _p(role="user", tier="basic"):
    return Principal(user_id=1, platform_role=role, tier=tier, status="active")


def test_basic_keeps_all_currently_free_capabilities():
    # P1 must NOT remove any capability current users have.
    assert Capability.CURRENT_MARKET_RESEARCH in BASIC_CAPABILITIES
    assert Capability.STANDARD_HISTORY in BASIC_CAPABILITIES
    assert Capability.STANDARD_PROGRESS in BASIC_CAPABILITIES


def test_premium_is_strict_superset_of_basic():
    assert BASIC_CAPABILITIES <= PREMIUM_CAPABILITIES
    assert Capability.PREMIUM_PREVIEW in PREMIUM_CAPABILITIES
    assert Capability.PREMIUM_PREVIEW not in BASIC_CAPABILITIES


def test_has_capability_by_tier():
    assert has_capability(_p(tier="basic"), Capability.CURRENT_MARKET_RESEARCH) is True
    assert has_capability(_p(tier="basic"), Capability.PREMIUM_PREVIEW) is False
    assert has_capability(_p(tier="premium"), Capability.PREMIUM_PREVIEW) is True


def test_unknown_tier_defaults_to_basic():
    assert capabilities_for("enterprise-does-not-exist") == BASIC_CAPABILITIES


def test_is_platform_admin():
    assert is_platform_admin(_p(role="platform_admin")) is True
    assert is_platform_admin(_p(role="user")) is False


def test_feature_flag(monkeypatch):
    assert flag_enabled("google_login") is False
    monkeypatch.setenv("FEATURE_GOOGLE_LOGIN", "true")
    assert flag_enabled("google_login") is True
    monkeypatch.setenv("FEATURE_GOOGLE_LOGIN", "off")
    assert flag_enabled("google_login") is False
