#!/usr/bin/env python3
"""Free OpenRouter availability probe (package 05C). Run by the OWNER or an operator; NEVER by tests or CI.

    python scripts/openrouter_models_probe.py key-status          # prints only "present" or "absent"
    python scripts/openrouter_models_probe.py models              # model ids the key can see; embeddings-capable ones are flagged where the API says so
    python scripts/openrouter_models_probe.py models --embeddings-only
    python scripts/openrouter_models_probe.py models --compare-pricing   # also: which models of the AI budget price table are / are not listed

It calls OpenRouter's models listing only (``GET /api/v1/models`` and ``GET /api/v1/embeddings/models``): no completion is requested, no token is consumed and nothing is charged,
so it does not need the AI budget approval marker. The API key is used as a Bearer header and is NEVER printed, logged or included in any message. Exit 0 = listing obtained,
2 = key absent or rejected, 1 = listing failed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm.budget.models_probe import compare_with_pricing, key_status, probe_models  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("key-status", help="report whether a key is configured (never its value)")
    m = sub.add_parser("models", help="list model ids available to the key")
    m.add_argument("--embeddings-only", action="store_true")
    m.add_argument("--compare-pricing", action="store_true", help="compare with the model price table of the AI budget configuration")
    a = ap.parse_args(argv)

    if a.cmd == "key-status":
        print(json.dumps({"openrouter_key": key_status()}))
        return 0
    result = probe_models()
    if result["error"] in ("key_absent", "key_rejected"):
        print(json.dumps({"ok": False, "key": result["key"], "error": result["error"]}))
        return 2
    if not result["ok"]:
        print(json.dumps({"ok": False, "key": result["key"], "error": result["error"]}))
        return 1
    models = [x for x in result["models"] if x["embeddings_capable"]] if a.embeddings_only else result["models"]
    out = {"ok": True, "key": result["key"], "tokens_consumed": 0, "counts": result["counts"], "embeddings_listing": result["embeddings_listing"], "models": models}
    if a.compare_pricing:
        from src.llm.budget.config import BudgetConfig, load_config
        from src.llm.budget.errors import BudgetError

        try:
            cfg: BudgetConfig = load_config()
            out["pricing_comparison"] = compare_with_pricing(result, sorted(cfg.pricing))
        except BudgetError as exc:
            out["pricing_comparison"] = {"unavailable": exc.reason}
    print(json.dumps(out, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
