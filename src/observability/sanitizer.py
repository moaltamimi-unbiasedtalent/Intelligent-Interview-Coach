"""Central telemetry sanitizer (Phase 7D, §11–§14).

The single choke point that scrubs anything before it can leave the process as telemetry.
Even though the observability layer is allow-listed by construction (only explicit safe
projections are emitted), this is a defence-in-depth backstop: every metadata dict handed to a
sink passes through :func:`safe_metadata`, so a future field or a careless caller can never leak
a secret, a candidate PII value, an authenticated URL or a raw exception string.

Design rules:
* Redact by KEY for known secret-bearing names, using precise matching so legitimate telemetry
  like ``token_count`` / ``total_tokens`` / ``input_tokens`` is NEVER stripped (§11).
* Redact by VALUE for obvious PII (emails, phone numbers) and credential-shaped strings (§12).
* URLs keep only scheme/host/path — query strings (which may carry app_id/app_key/signatures)
  are dropped (§13).
* Exceptions become a small set of sanitized category codes — never ``str(exc)`` (§14).

Nothing here promises perfect PII detection; the primary control remains NOT sending raw
candidate content at all (the safe projections in :mod:`base`).
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "REDACTED", "safe_metadata", "sanitize_value", "sanitize_url", "sanitize_text",
    "error_category", "is_secret_key",
]

REDACTED = "[redacted]"
_MAX_DEPTH = 6
_MAX_STR = 500
_MAX_ITEMS = 50

# Substrings that mark a KEY as secret-bearing. Matched against the lower-cased key.
_SECRET_SUBSTRINGS = (
    "authorization", "cookie", "password", "passwd", "secret", "credential",
    "private_key", "app_key", "app_id", "api_key", "apikey", "access_key",
    "bearer", "session_id_raw", "set-cookie",
)
# Exact key names that are secret (would otherwise be too broad as substrings).
_SECRET_EXACT = {"token", "auth", "key", "sig", "signature", "pwd"}
# Key suffixes that indicate a secret (e.g. "adzuna_token", "x_api_token").
_SECRET_SUFFIXES = ("_token", "_secret", "_password", "_key", "_credential", "_apikey")
# Telemetry keys that CONTAIN a secret-ish word but are legitimate metrics — never redact.
_SAFE_KEYS = {
    "token_count", "total_tokens", "input_tokens", "output_tokens", "reasoning_tokens",
    "prompt_tokens", "completion_tokens", "tokens", "tokens_per_second",
    "public_key_present", "secret_key_present",  # booleans (presence flags only)
}

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().\-]{7,}\d)(?!\w)")
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+")
# A long, high-entropy-ish token/credential blob (>=24 chars of key alphabet).
_KEYBLOB_RE = re.compile(r"(?<![\w])[A-Za-z0-9_\-]{24,}(?![\w])")


def is_secret_key(key: str) -> bool:
    """True if a metadata KEY should have its value redacted (§11 exact/safe matching)."""
    k = str(key).strip().lower()
    if k in _SAFE_KEYS:
        return False
    if k in _SECRET_EXACT:
        return True
    if any(s in k for s in _SECRET_SUBSTRINGS):
        return True
    return any(k.endswith(s) for s in _SECRET_SUFFIXES)


def sanitize_url(url: str) -> str:
    """Return scheme://host/path only — query string (possible secrets) dropped (§13)."""
    try:
        from urllib.parse import urlsplit
        parts = urlsplit(url)
        if not parts.scheme and not parts.netloc:
            # Not a real URL; still strip any ?query and credential-ish tail.
            return url.split("?", 1)[0]
        path = parts.path or ""
        return f"{parts.scheme}://{parts.netloc}{path}".rstrip("/") or f"{parts.scheme}://{parts.netloc}"
    except Exception:  # noqa: BLE001
        return REDACTED


def sanitize_text(text: str) -> str:
    """Redact emails / phone numbers / bearer tokens / credential blobs from a string (§12).

    Also bounds length. This runs on STRING VALUES that are allowed through — it does not make
    it safe to send candidate prose (that is blocked upstream), it just backstops accidents.
    """
    s = str(text)
    if len(s) > _MAX_STR:
        s = s[:_MAX_STR] + "…"
    if "http://" in s or "https://" in s:
        s = re.sub(r"https?://[^\s]+", lambda m: sanitize_url(m.group(0)), s)
    s = _BEARER_RE.sub(REDACTED, s)
    s = _EMAIL_RE.sub(REDACTED, s)
    s = _PHONE_RE.sub(REDACTED, s)
    s = _KEYBLOB_RE.sub(REDACTED, s)
    return s


def sanitize_value(value: Any, *, depth: int = 0) -> Any:
    """Recursively sanitize a telemetry value (dicts/lists/scalars)."""
    if depth > _MAX_DEPTH:
        return REDACTED
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in list(value.items())[:_MAX_ITEMS]:
            if is_secret_key(k):
                out[str(k)] = REDACTED
            else:
                out[str(k)] = sanitize_value(v, depth=depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [sanitize_value(v, depth=depth + 1) for v in list(value)[:_MAX_ITEMS]]
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    # Unknown/opaque object → its type name only, never its repr (could carry content).
    return f"<{type(value).__name__}>"


def safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """The public entry point: sanitize a metadata dict and drop ``None`` values.

    Redacts secret-keyed values, scrubs PII/URLs from string values, bounds depth/size, and
    removes ``None`` so only present, safe fields are emitted.
    """
    if not metadata:
        return {}
    cleaned = sanitize_value(dict(metadata))
    return {k: v for k, v in cleaned.items() if v is not None}


# --- Error taxonomy (§14) --------------------------------------------------------------

_ERROR_RULES = (
    ("provider_timeout", ("timeout", "timed out", "readtimeout", "connecttimeout")),
    ("provider_rate_limit", ("rate limit", "ratelimit", "429", "too many requests", "quota")),
    ("provider_auth", ("401", "403", "unauthorized", "forbidden", "invalid api key",
                       "authenticationerror", "permissionerror")),
    ("provider_truncation", ("max tokens", "length", "truncat", "context length")),
    ("provider_schema_error", ("schema", "validationerror for", "json", "parse", "pydantic")),
    ("retrieval_error", ("retriev", "chroma", "vector", "embedding")),
    ("database_error", ("database", "sqlite", "operationalerror", "integrityerror", "sqlalchemy")),
    ("validation_error", ("validation", "invalid input", "valueerror")),
    ("network_error", ("connection", "dns", "urlerror", "network", "ssl")),
    ("telemetry_error", ("langfuse", "telemetry", "observability")),
)


def error_category(exc: BaseException | str | None) -> str:
    """Map an exception (or message) to a sanitized diagnostic category — never the raw text.

    Uses the exception TYPE name and a lower-cased scan of the message against known markers.
    Returns a stable code from the §14 taxonomy (default ``unknown_error``).
    """
    if exc is None:
        return "unknown_error"
    type_name = type(exc).__name__.lower() if isinstance(exc, BaseException) else ""
    text = (type_name + " " + str(exc)).lower()
    for category, markers in _ERROR_RULES:
        if any(m in text for m in markers):
            return category
    # Fall back on well-known builtin exception types.
    if "timeout" in type_name:
        return "provider_timeout"
    if type_name in ("keyerror", "typeerror", "attributeerror", "indexerror"):
        return "application_error"
    return "unknown_error"
