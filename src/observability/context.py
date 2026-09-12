"""Safe correlation identity for telemetry (Phase 7D, §6).

Raw user identity (email / name / external subject) must NEVER be sent to telemetry. When a
run/session must be correlated to a user, use a DETERMINISTIC, NON-REVERSIBLE pseudonym: an
HMAC-SHA256 of the subject under a server-side salt, truncated. Without a configured salt this
returns ``None`` (correlate by opaque run_id / session_id only) — we never emit a plain hash
that could be dictionary-attacked, and never a reversible encoding.

Opaque server ids (agent ``run_id``, interview ``session_id``) are random and carry no user
data, so they are safe correlation keys on their own and need no hashing.
"""

from __future__ import annotations

import hashlib
import hmac
import os

__all__ = ["pseudonymous_id", "salt_configured"]

_SALT_ENV = "OBSERVABILITY_ID_SALT"


def salt_configured() -> bool:
    return bool(os.environ.get(_SALT_ENV, "").strip())


def pseudonymous_id(subject: str | int | None) -> str | None:
    """Return ``ask4mo_u_<16 hex>`` — a stable, non-reversible pseudonym for a user subject.

    Returns ``None`` when there is no subject or no configured salt (the default), so telemetry
    falls back to opaque run/session ids and never carries even a plain hash of identity.
    """
    if subject is None or str(subject).strip() == "":
        return None
    salt = os.environ.get(_SALT_ENV, "").strip()
    if not salt:
        return None
    digest = hmac.new(salt.encode("utf-8"), str(subject).encode("utf-8"),
                      hashlib.sha256).hexdigest()[:16]
    return f"ask4mo_u_{digest}"
