"""Modern password hashing (bcrypt) for account authentication (Capstone P1/E1).

Passwords are **never** stored in plaintext and **never** logged. We hash with
bcrypt (a deliberately slow, salted, adaptive KDF). Because bcrypt silently
truncates inputs at 72 bytes, we first fold the password through SHA-256 and
base64 — a well-known construction that removes the length limit and any embedded
NUL-byte issues without weakening the hash. The bcrypt work factor is tunable via
``BCRYPT_ROUNDS`` (default 12) so it can be raised as hardware improves.

The stored value is bcrypt's self-describing string (algorithm, cost and salt are
embedded), so :func:`verify_password` needs no separate parameters and
:func:`needs_rehash` can detect an out-of-date cost.
"""

from __future__ import annotations

import base64
import hashlib
import os

import bcrypt

__all__ = ["hash_password", "verify_password", "needs_rehash", "MIN_PASSWORD_LENGTH", "MAX_PASSWORD_LENGTH"]

# Product policy bounds (enforced by the auth service before hashing). The maximum
# guards against denial-of-service via very large inputs; the SHA-256 pre-hash
# already removes bcrypt's own 72-byte limit for legitimate passwords.
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 200


def _default_rounds() -> int:
    raw = os.environ.get("BCRYPT_ROUNDS", "").strip()
    if raw.isdigit():
        rounds = int(raw)
        # bcrypt accepts 4..31; keep a sane floor so a misconfiguration cannot
        # produce a trivially weak hash.
        return max(10, min(rounds, 16))
    return 12


def _prepare(plain: str) -> bytes:
    """Fold an arbitrary-length password into a fixed 44-byte bcrypt input."""
    digest = hashlib.sha256(plain.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(plain: str, *, rounds: int | None = None) -> str:
    """Return a bcrypt hash string for ``plain`` (never the password itself)."""
    if not isinstance(plain, str) or not plain:
        raise ValueError("password must be a non-empty string")
    work = rounds if rounds is not None else _default_rounds()
    salt = bcrypt.gensalt(rounds=work)
    return bcrypt.hashpw(_prepare(plain), salt).decode("ascii")


def verify_password(plain: str, hashed: str | None) -> bool:
    """Constant-time verification of ``plain`` against a stored bcrypt hash.

    Returns ``False`` (never raises) for any malformed/None hash so a missing
    credential is indistinguishable from a wrong password to the caller.
    """
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def needs_rehash(hashed: str | None, *, rounds: int | None = None) -> bool:
    """True when a stored hash uses fewer rounds than currently configured."""
    if not hashed:
        return True
    target = rounds if rounds is not None else _default_rounds()
    try:
        # bcrypt format: $2b$<cost>$<salt+hash>
        parts = hashed.split("$")
        current = int(parts[2])
    except (IndexError, ValueError):
        return True
    return current < target
