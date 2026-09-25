"""Retention (Capstone P6/E7): inventory + safe temp cleanup. Fixture-only, no live data."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from src.application.retention_service import TemporaryArtifactCleaner, retention_inventory


def _fixture(tmp_path: Path) -> Path:
    old = time.time() - 30 * 86400
    for name in ["tmp_a.bin", "ocr_b.png"]:
        p = tmp_path / name
        p.write_text("x")
        os.utime(p, (old, old))
    keep = tmp_path / "README.md"
    keep.write_text("keep")
    os.utime(keep, (old, old))
    (tmp_path / "fresh.bin").write_text("new")
    return tmp_path


def test_dry_run_is_default_and_deletes_nothing(tmp_path):
    _fixture(tmp_path)
    m = TemporaryArtifactCleaner(tmp_path, retention_days=7).clean()  # default dry_run
    assert m.dry_run and not m.deleted and m.candidates
    assert (tmp_path / "tmp_a.bin").exists()


def test_apply_deletes_stale_preserves_evidence_and_fresh(tmp_path):
    _fixture(tmp_path)
    m = TemporaryArtifactCleaner(tmp_path, retention_days=7).clean(dry_run=False)
    assert "tmp_a.bin" in m.deleted and "ocr_b.png" in m.deleted
    assert (tmp_path / "README.md").exists() and (tmp_path / "fresh.bin").exists()


def test_idempotent(tmp_path):
    _fixture(tmp_path)
    c = TemporaryArtifactCleaner(tmp_path, retention_days=7)
    c.clean(dry_run=False)
    second = c.clean(dry_run=False)
    assert not second.deleted and not second.candidates


def test_never_deletes_outside_root(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    victim = other / "someone_else.bin"
    victim.write_text("data")
    os.utime(victim, (time.time() - 30 * 86400,) * 2)
    root = tmp_path / "root"
    root.mkdir()
    old = tmp_path / "root" / "mine.bin"
    old.write_text("x")
    os.utime(old, (time.time() - 30 * 86400,) * 2)
    TemporaryArtifactCleaner(root, retention_days=7).clean(dry_run=False)
    assert victim.exists()  # outside the root — never touched


def test_inventory_classifies_key_stores():
    inv = retention_inventory()
    resources = " ".join(e["resource"].lower() for e in inv)
    for needed in ("session", "token", "audit", "checkpoint", "feedback", "prompt lab",
                   "ocr", "document", "observability"):
        assert needed in resources
    assert all(e["classification"] for e in inv)


def test_retention_eval_gate_passes():
    r = subprocess.run([sys.executable, "scripts/eval_retention.py"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
