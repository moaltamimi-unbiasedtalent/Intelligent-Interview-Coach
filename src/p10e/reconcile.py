"""Provider-side usage snapshots for reconciling the local ledger with what the provider reports (OpenRouter read-only key endpoint: no inference, no cost).

The credential is read only inside ``snapshot`` and never returned or written. The provider's account figures include EVERYTHING the key has ever done, possibly for other applications:
the difference between two snapshots is only an upper bound on what P10E consumed if nothing else used the key in between, and the local ledger can never be a proof of the provider's bill.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from src.p10e.guard import LIVE_DIR

SNAP_DIR = LIVE_DIR / "provider_snapshots"
KEY_URL = "https://openrouter.ai/api/v1/key"


def snapshot(api_key: str, *, client: httpx.Client | None = None) -> dict:
    c = client or httpx.Client(timeout=30)
    try:
        r = c.get(KEY_URL, headers={"Authorization": f"Bearer {api_key}"})
    finally:
        if client is None:
            c.close()
    taken = datetime.now(timezone.utc).isoformat()
    if r.status_code != 200:
        return {"taken_at": taken, "status": "UNAVAILABLE", "http_status": r.status_code}
    d = (r.json() or {}).get("data") or {}
    keep = {k: d.get(k) for k in ("usage", "usage_daily", "usage_weekly", "usage_monthly", "limit", "limit_remaining", "is_free_tier", "limit_reset") if k in d}
    return {"taken_at": taken, "status": "OK", "provider": "OpenRouter", "fields": keep,
            "key_has_provider_side_spending_limit": d.get("limit") is not None, "note": "account-level figures for the credential; may include usage by other applications"}


def save(snap: dict, label: str, base: Path = SNAP_DIR) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    p = base / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{label}.json"
    with open(p, "x", encoding="utf-8") as f:
        json.dump(snap, f, indent=1, sort_keys=True)
    return p


def compare(before: dict, after: dict, ledger_committed_usd: str, ledger_known_usd: str | None = None) -> dict[str, Any]:
    """Provider-reported consumption between two snapshots versus the local ledger. Estimated figures are never labelled as a verified bill."""
    if before.get("status") != "OK" or after.get("status") != "OK":
        return {"provider_reported_consumption_usd": "UNKNOWN", "reason": "a snapshot was unavailable", "ledger_committed_usd_upper_bound": ledger_committed_usd}
    b, a = before["fields"].get("usage"), after["fields"].get("usage")
    if b is None or a is None:
        return {"provider_reported_consumption_usd": "UNKNOWN", "reason": "the provider did not report a usage figure", "ledger_committed_usd_upper_bound": ledger_committed_usd}
    prov = Decimal(str(a)) - Decimal(str(b))
    out = {"provider_reported_consumption_usd": str(prov), "ledger_committed_usd_upper_bound": ledger_committed_usd, "ledger_known_estimate_usd": ledger_known_usd,
           "difference_provider_minus_ledger_committed_usd": str(prov - Decimal(ledger_committed_usd)),
           "interpretation": "provider figure is account-level (other applications may share the key); the ledger committed figure is a worst-case upper bound, not a bill"}
    if prov > Decimal(ledger_committed_usd):
        out["alert"] = "PROVIDER-REPORTED CONSUMPTION EXCEEDS THE LEDGER'S COMMITTED UPPER BOUND: stop further provider calls and investigate (another user of the key, or a missed request)."
    return out
