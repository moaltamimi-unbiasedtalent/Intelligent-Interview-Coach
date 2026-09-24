"""Unit tests for the auth security primitives (Capstone P1/E1).

Covers password hashing (bcrypt) and opaque-token helpers — no DB, no network.
"""

from __future__ import annotations

from src.authsec import passwords, tokens


def test_password_hash_is_not_plaintext_and_verifies():
    h = passwords.hash_password("correcthorsebattery")
    assert h != "correcthorsebattery"
    assert "correcthorsebattery" not in h
    assert h.startswith("$2")  # bcrypt
    assert passwords.verify_password("correcthorsebattery", h) is True
    assert passwords.verify_password("wrong-password-value", h) is False


def test_password_hashes_are_salted_unique():
    a = passwords.hash_password("same-password-123")
    b = passwords.hash_password("same-password-123")
    assert a != b  # random per-password salt
    assert passwords.verify_password("same-password-123", a)
    assert passwords.verify_password("same-password-123", b)


def test_password_verify_is_safe_on_bad_input():
    assert passwords.verify_password("x", None) is False
    assert passwords.verify_password("", "whatever") is False
    assert passwords.verify_password("x", "not-a-bcrypt-hash") is False


def test_password_supports_long_inputs_beyond_bcrypt_72_bytes():
    long_pw = "a" * 100 + "🔒unicode-tail"
    h = passwords.hash_password(long_pw)
    assert passwords.verify_password(long_pw, h)
    # A different long password that shares the first 72 bytes must NOT verify
    # (the SHA-256 pre-hash removes bcrypt's truncation weakness).
    other = "a" * 100 + "different-tail"
    assert passwords.verify_password(other, h) is False


def test_needs_rehash_detects_low_cost():
    weak = passwords.hash_password("pw-to-rehash-123", rounds=10)
    assert passwords.needs_rehash(weak, rounds=14) is True
    strong = passwords.hash_password("pw-to-rehash-123", rounds=14)
    assert passwords.needs_rehash(strong, rounds=14) is False


def test_token_generation_and_hash():
    raw = tokens.generate_token()
    assert len(raw) > 30
    h = tokens.hash_token(raw)
    assert h != raw and len(h) == 64  # sha256 hex
    assert tokens.hash_token(raw) == h  # deterministic
    assert tokens.tokens_equal(h, tokens.hash_token(raw)) is True
    assert tokens.tokens_equal(h, tokens.hash_token(tokens.generate_token())) is False


def test_tokens_are_unique():
    seen = {tokens.generate_token() for _ in range(200)}
    assert len(seen) == 200
