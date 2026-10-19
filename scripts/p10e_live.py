#!/usr/bin/env python
"""P10E live capability validation: authorization status, execution plan, the persistent ledger and guarded live runs. MANUAL ONLY: never in CI, never on startup.

    python scripts/p10e_live.py status                    # authorization, execution flag, ledger totals, credential PRESENCE (never values); exit 0
    python scripts/p10e_live.py plan                      # write evaluations/p10e/execution_plan.json (offline)
    python scripts/p10e_live.py host-fingerprint          # hash of this host, to designate it in the authorization record
    P10E_LEDGER_DIR=... python scripts/p10e_live.py ledger-init       # ONCE: create the persistent ledger outside the checkout; refused if one was already designated
    python scripts/p10e_live.py provider-snapshot --label before|after   # read-only provider usage snapshot for reconciliation
    P10E_LIVE=1 P10E_LEDGER_DIR=... python scripts/p10e_live.py smoke [--profile fast|balanced|advanced ...]
    P10E_LIVE=1 P10E_LEDGER_DIR=... python scripts/p10e_live.py kb-quality [--profile balanced]
    P10E_LIVE=1 P10E_LEDGER_DIR=... python scripts/p10e_live.py agent [--profile balanced] [--limit N]

Paid commands refuse (exit 3) unless every condition in src/p10e/guard.py holds (execution flag true, owner-approved limits, designated host and ledger, exclusive lock, opt-in, not CI).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.p10e import guard as G  # noqa: E402
from src.p10e import ledger as L  # noqa: E402
from src.p10e.plan import build_plan  # noqa: E402


def _credentials_present() -> bool:
    try:
        from src.copilot.config import load_config
        return bool(load_config().is_configured)
    except Exception:  # noqa: BLE001
        return False


def status() -> dict:
    auth = G.load_authorization()
    raw = auth.limits_raw if isinstance(auth.limits_raw, dict) else {}
    unapproved = [k for k in G.REQUIRED_LIMITS if k not in auth.approves]
    unset = [k for k in G.REQUIRED_LIMITS if raw.get(k) is None]
    try:
        G.LiveLimits.parse(auth.limits_raw)
        limits_state = "VALID"
    except G.LiveRunRefused as exc:
        limits_state = exc.reason
    sa = auth.spend_authority or {}
    ee = auth.execution_environment or {}
    ledger = {"configured": bool(os.environ.get(G.LEDGER_DIR_ENV)), "designated_genesis_id_recorded": bool(ee.get("ledger_genesis_id"))}
    if ledger["configured"] and ledger["designated_genesis_id_recorded"]:
        try:
            ledger["state"] = L.read_only_status(Path(os.environ[G.LEDGER_DIR_ENV]), expected_genesis=ee.get("ledger_genesis_id"))
        except G.LiveRunRefused as exc:
            ledger["state"] = f"REFUSED ({exc.reason})"
    return {"owner_decision_date": auth.owner_decision_date, "paid_use_granted": auth.paid_use_granted, "paid_execution_enabled": auth.execution_flag,
            "execution_flag_is_boolean_true": auth.execution_enabled, "limits": limits_state, "approval_recorded": {"approved_by": auth.approved_by, "approval_date": auth.approval_date, "reference": auth.reference},
            "approved_limits": [k for k in G.REQUIRED_LIMITS if k in auth.approves], "unapproved_limits": unapproved, "unset_limits": unset,
            "approved_total_spend_usd": sa.get("approved_total_usd"), "potential_ceiling_not_approved_usd": sa.get("potential_ceiling_not_approved_usd"),
            "designated_environment": ee.get("environment_id"), "this_host_is_designated": ee.get("host_fingerprint_sha256") == L.host_fingerprint(), "ledger": ledger,
            "in_ci": G.in_ci(), "credential_present": _credentials_present(), "paid_execution_possible": bool(auth.execution_enabled and not unapproved and not unset and limits_state == "VALID"),
            "missing_owner_decision": sorted(set(unapproved) | set(unset))}


def _session(area: str, data_class: str):
    return G.live_session(area, data_class, credential_check=_credentials_present)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status"); sub.add_parser("host-fingerprint"); sub.add_parser("ledger-init")
    p = sub.add_parser("plan"); p.add_argument("--out", default=str(ROOT / "evaluations/p10e/execution_plan.json"))
    p = sub.add_parser("provider-snapshot"); p.add_argument("--label", required=True)
    p = sub.add_parser("smoke"); p.add_argument("--profile", action="append", choices=["fast", "balanced", "advanced"])
    p = sub.add_parser("kb-quality"); p.add_argument("--profile", choices=["fast", "balanced", "advanced"], default="balanced")
    sub.add_parser("auth-probe"); sub.add_parser("multilingual-offline"); sub.add_parser("multilingual-reclassify").add_argument("run_dir")
    p = sub.add_parser("interview"); p.add_argument("--profile", choices=["fast", "balanced", "advanced"], default="balanced"); p.add_argument("--cases", default=None)
    p = sub.add_parser("multilingual"); p.add_argument("--profile", choices=["fast", "balanced", "advanced"], default="balanced"); p.add_argument("--cases", default=None)
    p = sub.add_parser("rescore-kb"); p.add_argument("run_dir")
    p = sub.add_parser("agent"); p.add_argument("--profile", choices=["fast", "balanced", "advanced"], default="balanced"); p.add_argument("--limit", type=int, default=None); p.add_argument("--cases", default=None, help="comma-separated case ids")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps(status(), indent=1, default=str)); return 0
    if a.cmd == "host-fingerprint":
        print(L.host_fingerprint()); return 0
    if a.cmd == "plan":
        Path(a.out).write_text(json.dumps(build_plan(), indent=1), encoding="utf-8"); print(f"wrote {a.out} (no provider call made)"); return 0
    if a.cmd == "ledger-init":
        auth = G.load_authorization(); ee = auth.execution_environment
        try:
            if ee.get("ledger_genesis_id"):
                raise G.LiveRunRefused("ledger_already_designated", "The authorization already names a ledger genesis id: a ledger is never initialized a second time (that would create a second allowance).")
            if ee.get("host_fingerprint_sha256") != L.host_fingerprint():
                raise G.LiveRunRefused("ledger_wrong_host", "This host is not the designated execution host.")
            if not os.environ.get(G.LEDGER_DIR_ENV):
                raise G.LiveRunRefused("ledger_location_missing", f"Set {G.LEDGER_DIR_ENV} explicitly.")
            led = L.Ledger.create(Path(os.environ[G.LEDGER_DIR_ENV]), environment_id=ee["environment_id"], approved_total_usd=G.Decimal(str(auth.spend_authority["approved_total_usd"])),
                                  call_cap=int(auth.limits_raw["max_provider_calls"]))
        except G.LiveRunRefused as exc:
            print(f"REFUSED ({exc.reason}): {exc}"); return 3
        print(json.dumps({"genesis_id": led.meta["genesis_id"], "environment_id": led.meta["environment_id"], "next": "record the genesis id in authorization.json (execution_environment.ledger_genesis_id) in a reviewed commit"}, indent=1))
        led.conn.close(); return 0
    if a.cmd == "provider-snapshot":
        from src.copilot.config import load_config
        from src.p10e import reconcile as R
        cfg = load_config()
        if not cfg.is_configured or cfg.api_key is None:
            print("REFUSED (credential_missing)"); return 3
        snap = R.snapshot(cfg.api_key.get_secret_value()); path = R.save(snap, a.label)
        print(json.dumps({"saved": str(path.relative_to(ROOT)), **{k: v for k, v in snap.items() if k != "fields"}, "fields": snap.get("fields")}, indent=1)); return 0
    if a.cmd == "multilingual-reclassify":
        from src.p10e import r1_evals as E
        print(json.dumps(E.reclassify_run_post_hoc(Path(a.run_dir)), indent=1, ensure_ascii=False)); return 0
    if a.cmd == "multilingual-offline":
        from src.p10e import r1_evals as E
        print(json.dumps(E.multilingual_offline(), indent=1, ensure_ascii=False)); return 0
    if a.cmd == "rescore-kb":
        from src.p10e import live_runs as R
        print(json.dumps(R.rescore_kb_run(Path(a.run_dir)), indent=1)); return 0
    try:
        if a.cmd == "auth-probe":
            with _session("auth-failure-probe", "synthetic_fixture_corpus") as s:
                from src.p10e import live_runs as R
                out = R.run_auth_failure_probe(s)
        elif a.cmd == "interview":
            with _session("interview-quality", "synthetic_fixture_corpus") as s:
                from src.p10e import r1_evals as E
                out = E.run_interview_quality(s, a.profile, only=a.cases.split(",") if a.cases else None)
        elif a.cmd == "multilingual":
            with _session("multilingual-live", "synthetic_fixture_corpus") as s:
                from src.p10e import r1_evals as E
                out = E.run_multilingual_live(s, a.profile, only=a.cases.split(",") if a.cases else None)
        elif a.cmd == "smoke":
            with _session("smoke", "synthetic_fixture_corpus") as s:
                from src.p10e import live_runs as R
                out = R.run_smoke(s, a.profile or ["balanced"])
        elif a.cmd == "kb-quality":
            with _session("kb-quality", "synthetic_fixture_corpus") as s:
                from src.p10e import live_runs as R
                out = R.run_kb_quality(s, a.profile)
        else:
            with _session("agent-live", "synthetic_held_out_agent_cases") as s:
                from src.p10e import live_runs as R
                out = R.run_agent(s, a.profile, limit=a.limit, only=a.cases.split(",") if a.cases else None)
    except G.LiveRunRefused as exc:
        print(f"REFUSED ({exc.reason}): {exc}"); return 3
    print(json.dumps(out, indent=1, default=str)); return 0


if __name__ == "__main__":
    sys.exit(main())
