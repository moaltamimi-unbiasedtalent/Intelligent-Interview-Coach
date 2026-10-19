#!/usr/bin/env python
"""P10E live capability validation: authorization status, execution plan and guarded live runs. MANUAL ONLY: never in CI, never on startup.

    python scripts/p10e_live.py status          # authorization, limits, credentials PRESENCE (never values); exit 0
    python scripts/p10e_live.py plan            # write evaluations/p10e/execution_plan.json (offline)
    P10E_LIVE=1 python scripts/p10e_live.py smoke [--profile fast|balanced|advanced]
    P10E_LIVE=1 python scripts/p10e_live.py kb-quality [--profile balanced]

Paid commands refuse (exit 3) unless the owner-approved, finite limits are recorded in evaluations/p10e/authorization.json (see src/p10e/guard.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.p10e import guard as G  # noqa: E402
from src.p10e.plan import build_plan  # noqa: E402


def _credentials_present() -> dict:
    try:
        from src.copilot.config import load_config
        return {"OPENROUTER_API_KEY": bool(load_config().is_configured)}
    except Exception:  # noqa: BLE001
        return {"OPENROUTER_API_KEY": False}


def status() -> dict:
    auth = G.load_authorization()
    try:
        G.LiveLimits.parse(auth.limits_raw)
        limits_state = "VALID"
    except G.LiveRunRefused as exc:
        limits_state = f"{exc.reason}"
    return {"owner_decision_date": auth.owner_decision_date, "paid_use_granted": auth.paid_use_granted, "limits": limits_state, "limits_approved": bool(auth.approved_by and auth.approval_date and auth.reference),
            "in_ci": G.in_ci(), "credentials_present": _credentials_present(), "paid_execution_possible": False if limits_state != "VALID" else "see require_live",
            "missing_owner_decision": [] if limits_state == "VALID" else ["max_spend_usd", "max_provider_calls", "per-request token limits, timeout, retries, concurrency", "approved_by / approval_date / reference"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("plan"); p.add_argument("--out", default=str(ROOT / "evaluations/p10e/execution_plan.json"))
    for name in ("smoke", "kb-quality"):
        q = sub.add_parser(name); q.add_argument("--profile", choices=["fast", "balanced", "advanced"], default="balanced")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps(status(), indent=1)); return 0
    if a.cmd == "plan":
        Path(a.out).write_text(json.dumps(build_plan(), indent=1), encoding="utf-8"); print(f"wrote {a.out} (no provider call made)"); return 0
    try:
        limits = G.require_live(credential_names=())
        if not _credentials_present()["OPENROUTER_API_KEY"]:
            raise G.LiveRunRefused("credential_missing", "Required credential not configured: OPENROUTER_API_KEY.")
    except G.LiveRunRefused as exc:
        print(f"REFUSED ({exc.reason}): {exc}"); return 3
    from src.p10e import live_runs as L
    if a.cmd == "smoke":
        out = L.run_smoke([a.profile], limits)
    else:
        out = L.run_kb_quality(a.profile, limits)
    print(json.dumps(out, indent=1, default=str)); return 0


if __name__ == "__main__":
    sys.exit(main())
