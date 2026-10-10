"""The public 'Available today' pricing table must mirror the AUTHORITATIVE backend plan definitions (v4).

`frontend/lib/pricing.ts` AVAILABLE_TODAY is hand-maintained presentation; this test parses it and compares it key for key with
`src/entitlements.py` (REGISTRY + DEFAULT_PLANS), so a feature difference the server does not enforce can never be advertised as
'available today', and a server change cannot silently diverge from the public table.
"""

from __future__ import annotations

import re
from pathlib import Path

from src import entitlements as ent

PRICING_TS = (Path(__file__).resolve().parent.parent / "frontend" / "lib" / "pricing.ts").read_text(encoding="utf-8")


def _rows() -> dict[str, tuple[bool, bool, bool]]:
    block = PRICING_TS[PRICING_TS.index("export const AVAILABLE_TODAY"):PRICING_TS.index("/** Proposed package ideas")]
    out: dict[str, tuple[bool, bool, bool]] = {}
    for m in re.finditer(r'\{ key: "(\w+)", labelKey: "[\w.]+", basic: (true|false), premium: (true|false)(, preview: true)? \}', block):
        out[m.group(1)] = (m.group(2) == "true", m.group(3) == "true", bool(m.group(4)))
    return out


def test_available_today_keys_are_exactly_the_backend_registry() -> None:
    assert set(_rows()) == set(ent.REGISTRY)


def test_available_today_values_match_the_default_plans() -> None:
    rows = _rows()
    for key, (basic, premium, _preview) in rows.items():
        assert basic == (key in ent.DEFAULT_PLANS["basic"]["enabled"]), key
        assert premium == (key in ent.DEFAULT_PLANS["premium"]["enabled"]), key


def test_premium_only_difference_is_the_non_purchasable_preview() -> None:
    diff = ent.DEFAULT_PLANS["premium"]["enabled"] - ent.DEFAULT_PLANS["basic"]["enabled"]
    assert diff == {"premium_preview"}
    assert _rows()["premium_preview"][2] is True            # rendered as 'preview only', never 'included'


def test_backend_has_no_limit_entitlements_so_no_limit_may_be_advertised_as_available() -> None:
    from src.entitlements import EntitlementType
    assert all(d.type == EntitlementType.BOOLEAN for d in ent.REGISTRY.values())
    assert 'BILLING_ENABLED = false' in PRICING_TS
