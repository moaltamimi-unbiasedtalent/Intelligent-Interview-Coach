#!/usr/bin/env python
"""Langfuse connectivity / configuration check (Phase 7D, §44/§45).

Reports one of: DISABLED, NOT CONFIGURED, READY, PARTIAL. Never sends candidate data and never
makes an LLM/provider call. When Langfuse is enabled AND configured, it performs the smallest
safe validation: build the client and (optionally) emit ONE metadata-only connectivity trace
(operation=phase7d_connectivity_test, environment tag) then flush — no CV/JD/answers/content.

NOT CONFIGURED is NOT a failure (exit 0): the implementation is complete without the operator's
production credentials.

Usage:
    python scripts/check_langfuse.py
    python scripts/check_langfuse.py --json
    python scripts/check_langfuse.py --send-test-trace   # only if enabled+configured
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.observability.config import load_config  # noqa: E402


def check(*, send_test_trace: bool = False) -> dict:
    cfg = load_config()
    report = {
        "status": cfg.status(), "enabled": cfg.enabled,
        "credentials_present": cfg.credentials_present,
        "host": cfg.host or "(default cloud)", "environment": cfg.environment,
        "release": cfg.release, "sample_rate": cfg.sample_rate,
        "capture_content": cfg.capture_content, "test_trace_sent": False,
    }
    if cfg.status() != "READY":
        return report

    # Enabled + configured: build the client (no network yet in v2) and optionally emit one
    # sanitised connectivity trace + flush.
    try:
        from src.observability import build_observability_sink
        sink = build_observability_sink(cfg)
        report["sink"] = type(sink).__name__
        if type(sink).__name__ == "NoOpObservabilitySink":
            report["status"] = "PARTIAL"
            report["detail"] = "Enabled+configured but the Langfuse SDK is unavailable (no-op)."
            return report
        if send_test_trace:
            sink.run_started(run_id="phase7d_connectivity_test", profile=None)
            sink.run_completed(run_id="phase7d_connectivity_test",
                               projection={"status": "connectivity_test",
                                           "operation": "phase7d_connectivity_test"})
            sink.flush()
            report["test_trace_sent"] = True
    except Exception as exc:  # noqa: BLE001 - never leak details
        report["status"] = "PARTIAL"
        report["detail"] = f"client build failed: {type(exc).__name__}"
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check Langfuse observability configuration.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--send-test-trace", action="store_true",
                    help="Emit ONE metadata-only connectivity trace (only when READY).")
    args = ap.parse_args(argv)

    report = check(send_test_trace=args.send_test_trace)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"LANGFUSE:\n  {report['status']}")
        print(f"  enabled: {report['enabled']}  credentials: {report['credentials_present']}")
        print(f"  environment: {report['environment']}  release: {report['release']}")
        print(f"  sample_rate: {report['sample_rate']}  capture_content: {report['capture_content']}")
        if report.get("detail"):
            print(f"  detail: {report['detail']}")
        if report.get("test_trace_sent"):
            print("  connectivity test trace: SENT (metadata-only)")
    return 0  # NOT CONFIGURED / DISABLED / PARTIAL are never a hard failure (§44)


if __name__ == "__main__":
    sys.exit(main())
