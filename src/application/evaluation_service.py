"""Evaluation application boundary (Streamlit-free, read-only).

Exposes safe, read-only evaluation status: the latest usable RAGAS run, the list
of stored runs, one run's results, and a safe RAGAS configuration snapshot.

**No provider call happens here** — nothing runs RAGAS on import or on read. The
user-triggered, cost-gated RAGAS runner stays explicit in the UI
(``ragas_panel``) / a future API endpoint. RAGAS scoring semantics are unchanged.
This module owns the pure run-reading logic; ``ragas_panel`` delegates to it.
"""

from __future__ import annotations

import json
import os

_RUNS_DIR = "evaluations/ragas/runs"


def run_is_usable(data: dict) -> bool:
    """A usable RAGAS run has at least one finite aggregate metric.

    A FAILED status is never usable; legacy runs (no status) are judged purely on
    metric finiteness, so an all-NaN/null legacy run is correctly rejected.
    """
    from src.copilot.evaluation.ragas_adapter import STATUS_FAILED, is_valid_score

    if (data.get("run_config", {}) or {}).get("status") == STATUS_FAILED:
        return False
    return any(is_valid_score(v) for v in (data.get("metrics") or {}).values())


def latest_evaluation_run(runs_dir: str = _RUNS_DIR) -> dict | None:
    """Load the most recent USABLE RAGAS run's results.json, or ``None``.

    Never executes RAGAS. Invalid runs (all-NaN/null legacy runs, or FAILED runs)
    are skipped in favour of the newest usable prior run; ``_invalid_ignored`` on
    the returned dict flags that at least one newer invalid run was skipped.
    """
    if not os.path.isdir(runs_dir):
        return None
    run_dirs = sorted(
        (d for d in os.listdir(runs_dir) if os.path.isdir(os.path.join(runs_dir, d))),
        reverse=True,
    )
    skipped_invalid = False
    for name in run_dirs:
        path = os.path.join(runs_dir, name, "results.json")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)  # strict JSON; NaN would raise here
        except (OSError, ValueError):
            skipped_invalid = True
            continue
        if not run_is_usable(data):
            skipped_invalid = True
            continue
        data["_dir"] = os.path.join(runs_dir, name)
        data["_invalid_ignored"] = skipped_invalid
        return data
    return None


def list_evaluation_runs(runs_dir: str = _RUNS_DIR) -> list[str]:
    """Stored RAGAS run ids (directory names), newest first. No file reads."""
    if not os.path.isdir(runs_dir):
        return []
    return sorted(
        (d for d in os.listdir(runs_dir) if os.path.isdir(os.path.join(runs_dir, d))),
        reverse=True,
    )


def get_evaluation_run(run_id: str, runs_dir: str = _RUNS_DIR) -> dict | None:
    """Read one stored run's results.json (or ``None`` if absent/unreadable)."""
    path = os.path.join(runs_dir, run_id, "results.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def check_ragas_configuration(*, allow_chat_fallback: bool = False) -> dict:
    """Safe RAGAS readiness snapshot — never a secret value, never a provider call."""
    from src.copilot.evaluation import ragas_runner

    return ragas_runner.check_configuration(allow_chat_fallback=allow_chat_fallback)
