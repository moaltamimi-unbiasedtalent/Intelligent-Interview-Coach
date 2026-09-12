"""Bounded TTL cache for sanitised external research results (Phase 7F, §20/§21).

Caches ONLY sanitised, normalised ``CurrentMarketResearchResult`` JSON under ``data/cache/
external/`` (git-ignored). Never caches credentials, authenticated URLs, raw provider payloads,
candidate CV/background or free-text prompts — the cache key is built only from safe request
parameters. Current-market data is short-lived, so the TTL is bounded (default 30 minutes).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

CACHE_DIR = Path("data/cache/external")
DEFAULT_TTL_SECONDS = 1800  # 30 minutes — bounded; current-market data expires quickly (§21)


def cache_key(provider: str, intent: str, *, role: str | None, country: str | None,
              region: str | None, company: str | None, limit: int) -> str:
    """A deterministic key from SAFE request parameters only (never candidate data, §20)."""
    parts = [provider, intent, (role or "").lower().strip(), (country or "").lower(),
             (region or "").lower(), (company or "").lower(), str(limit)]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def read(key: str, *, ttl_seconds: int = DEFAULT_TTL_SECONDS,
         cache_dir: Path = CACHE_DIR) -> dict | None:
    """Return the cached payload if present and not expired, else None."""
    p = Path(cache_dir) / f"{key}.json"
    if not p.is_file():
        return None
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if time.time() - blob.get("_cached_at", 0) > ttl_seconds:
        return None  # expired
    return blob.get("payload")


def write(key: str, payload: dict, *, cache_dir: Path = CACHE_DIR) -> None:
    """Store a sanitised payload. Best-effort; a cache failure never breaks research."""
    try:
        d = Path(cache_dir)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{key}.json").write_text(
            json.dumps({"_cached_at": time.time(), "payload": payload}), encoding="utf-8")
    except OSError:
        pass
