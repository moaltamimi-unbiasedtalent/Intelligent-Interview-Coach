"""Opaque, high-entropy tokens and their at-rest hashes (Capstone P1/E1).

Used for session identifiers, email-verification links and password-reset links.

Design:
* The **raw** token is generated with :func:`secrets.token_urlsafe` (URL-safe,
  cryptographically strong) and given to the client exactly once.
* Only the **SHA-256 hash** of the token is persisted. A database read therefore
  never yields a usable credential, and lookups hash the presented token and
  compare in constant time.
* Comparisons use :func:`hmac.compare_digest` to avoid timing side channels.

Nothing here logs or prints a raw token.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

__all__ = ["generate_token", "hash_token", "tokens_equal", "SESSION_TOKEN_BYTES", "LINK_TOKEN_BYTES"]

# 32 bytes → ~43 URL-safe characters, ~256 bits of entropy.
SESSION_TOKEN_BYTES = 32
LINK_TOKEN_BYTES = 32


def generate_token(n_bytes: int = SESSION_TOKEN_BYTES) -> str:
    """Return a fresh URL-safe random token (the raw secret, shown once)."""
    return secrets.token_urlsafe(n_bytes)


def hash_token(raw: str) -> str:
    """Return the hex SHA-256 of a raw token — the only form we persist."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    """Constant-time equality for two hex digests (or raw strings)."""
    return hmac.compare_digest(a, b)
