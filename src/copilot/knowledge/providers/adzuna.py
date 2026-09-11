"""Adzuna current-market data provider (Phase 7A.1 — acquisition infrastructure ONLY).

Bounded, read-only client for the documented Adzuna jobs API
(https://api.adzuna.com/v1/api). Adzuna is classified as an ``authorized_market_api`` —
its role is CURRENT ADVERTISED-market evidence (advertised salary ranges, vacancy counts,
regional demand), never official observed earnings.

This is data-acquisition infrastructure: it is NOT an Agent tool, does not touch LangGraph
or retrieval, and never enters the candidate runtime.

Security (§29): credentials are read ONLY from the ADZUNA_APP_ID / ADZUNA_APP_KEY
environment variables. They are never logged, printed, embedded in provenance, or included
in error messages or authenticated URLs. ``_redact`` scrubs the credentials from any string
that could surface.

Endpoint rule (§32): ``/jobs/<country>/version`` is NOT used for connectivity — it returned
404 during manual validation, which is endpoint-specific and must not be read as an auth or
country failure. Germany connectivity is validated with ``/jobs/de/search/1`` (and optionally
``/jobs/de/categories``).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

API_BASE = "https://api.adzuna.com/v1/api"
DEFAULT_TIMEOUT = 15
_USER_AGENT = "Ask4Mo-KnowledgeAcquisition/7A.1 (+contact: repository owner)"


class AdzunaConfigError(RuntimeError):
    """Raised when Adzuna credentials are not configured in the environment."""


class AdzunaError(RuntimeError):
    """A bounded, credential-safe Adzuna API error (status carried when known)."""

    def __init__(self, message: str, *, status: int | None = None, category: str = "error"):
        super().__init__(message)
        self.status = status
        self.category = category


@dataclass
class AdzunaResult:
    ok: bool
    status: int | None
    count: int | None = None
    data: dict | None = None
    category: str = "ok"


def credentials_configured() -> bool:
    return bool(os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_APP_KEY"))


def _creds() -> tuple[str, str]:
    aid = os.environ.get("ADZUNA_APP_ID")
    akey = os.environ.get("ADZUNA_APP_KEY")
    if not aid or not akey:
        raise AdzunaConfigError("ADZUNA_APP_ID / ADZUNA_APP_KEY are not configured.")
    return aid, akey


def _redact(text: str) -> str:
    """Remove any credential material from a string before it is surfaced/logged."""
    out = text
    for val in (os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")):
        if val:
            out = out.replace(val, "***")
    # Also scrub app_id/app_key query params generically.
    import re
    out = re.sub(r"(app_id|app_key)=[^&\s]+", r"\1=***", out)
    return out


@dataclass
class AdzunaProvider:
    """Bounded Adzuna client. One request per call; small results; conservative retries."""

    timeout: int = DEFAULT_TIMEOUT
    max_retries: int = 2
    # Injectable transport for tests: (url, headers) -> (status, body_bytes). Default None
    # uses urllib. Tests pass a fake so no live call is made.
    transport: object = field(default=None, repr=False)

    def _request(self, path: str, params: dict) -> AdzunaResult:
        aid, akey = _creds()
        query = dict(params)
        query.update({"app_id": aid, "app_key": akey})
        url = f"{API_BASE}{path}?{urllib.parse.urlencode(query)}"
        headers = {"Accept": "application/json", "User-Agent": _USER_AGENT}

        attempt = 0
        while True:
            attempt += 1
            try:
                status, body = self._send(url, headers)
            except AdzunaError:
                raise
            except Exception as exc:  # noqa: BLE001 - network/other → safe, redacted
                raise AdzunaError(
                    f"request failed: {type(exc).__name__}", category="network"
                ) from None

            if status == 429 and attempt <= self.max_retries:
                continue  # bounded retry on rate limit
            if status in (401, 403):
                raise AdzunaError("authentication failed", status=status, category="auth")
            if status == 404:
                raise AdzunaError("endpoint not found", status=status, category="not_found")
            if status == 429:
                raise AdzunaError("rate limited", status=status, category="rate_limit")
            if status >= 400:
                raise AdzunaError(f"HTTP {status}", status=status, category="http_error")
            try:
                data = json.loads(body)
            except (ValueError, TypeError):
                raise AdzunaError("malformed JSON response", status=status,
                                  category="malformed") from None
            return AdzunaResult(ok=True, status=status, data=data,
                                count=data.get("count") if isinstance(data, dict) else None)

    def _send(self, url: str, headers: dict) -> tuple[int, str]:
        if self.transport is not None:
            return self.transport(url, headers)  # test hook
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                pass
            return exc.code, body
        except urllib.error.URLError as exc:
            raise AdzunaError(f"connection error: {type(exc).__name__}",
                              category="network") from None

    # -- documented operations (implemented against verified endpoints) ---------

    def search_jobs(self, *, country: str = "de", what: str = "", where: str = "",
                    results_per_page: int = 1, page: int = 1) -> AdzunaResult:
        """`/jobs/<country>/search/<page>` — small current-market query."""
        params = {"results_per_page": max(1, min(results_per_page, 10))}
        if what:
            params["what"] = what
        if where:
            params["where"] = where
        return self._request(f"/jobs/{country}/search/{page}", params)

    def categories(self, *, country: str = "de") -> AdzunaResult:
        """`/jobs/<country>/categories` — supported job categories for the country."""
        return self._request(f"/jobs/{country}/categories", {})


def sanitized_provenance(*, endpoint: str, country: str, query: str, count: int | None) -> dict:
    """Credential-free provenance for a snapshot (§38/§47). Never includes app_id/app_key."""
    return {
        "source": "adzuna",
        "source_quality": "authorized_market_api",
        "endpoint_type": _redact(endpoint),
        "country": country,
        "query": _redact(query),
        "record_count": count,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def parse_salary(job: dict) -> dict:
    """Extract advertised-salary semantics from one Adzuna job (never invents a median)."""
    return {
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "salary_is_predicted": str(job.get("salary_is_predicted", "")) in ("1", "true", "True"),
    }
