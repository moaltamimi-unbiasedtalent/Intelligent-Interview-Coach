"""The offline demonstration journey is deterministic, passes its own checks, contacts nothing outside the process and labels every component. No provider, no network, no paid call."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("demo_offline_journey", ROOT / "scripts/demo_offline_journey.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def runs():
    mod = _load()
    with mod._Block():
        return mod.run_journey(), mod.run_journey()


def test_every_step_check_passes(runs):
    a, _ = runs
    assert a["ok"] and len(a["steps"]) == 5
    assert all(all(s["checks"].values()) for s in a["steps"])


def test_the_journey_is_deterministic(runs):
    a, b = runs
    assert a["transcript_sha256"] == b["transcript_sha256"]


def test_every_step_labels_its_components_real_mocked_or_disabled(runs):
    a, _ = runs
    for s in a["steps"]:
        assert s["components"] and all(any(w in v for w in ("REAL", "MOCKED", "DISABLED", "available")) for v in s["components"].values())
    assert any("MOCKED" in v for s in a["steps"] for v in s["components"].values())


def test_the_demonstration_data_is_synthetic():
    d = json.loads((ROOT / "evaluations/demo/synthetic_demo_candidate.json").read_text())
    assert "SYNTHETIC" in d["note"] and d["candidate"]["email"].endswith(".invalid") and "fictional" in d["opportunity"]["company_name"]


def test_the_committed_transcript_is_a_passing_run_without_secrets_or_paths():
    t = (ROOT / "docs/capstone/submission/DEMO_TRANSCRIPT_OFFLINE.md").read_text()
    assert "All checks passed: True" in t and "FAIL" not in t
    assert "sk-or-" not in t and "/Users/" not in t and "/Volumes/" not in t


def test_the_demo_blocks_any_external_request():
    import httpx

    mod = _load()
    with mod._Block():
        with pytest.raises(RuntimeError):
            httpx.Client().send(httpx.Request("GET", "https://openrouter.ai/api/v1/models"))
