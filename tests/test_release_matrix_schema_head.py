"""The release matrix R-39 declares a single Alembic head verified dynamically (version-independent); the check still fails on a wrong declaration, a branch, a gap,
an unresolved down_revision or a missing row. Negative cases run on COPIES in a temporary tree; no real evidence file is modified."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import tests._alembic_head as H
from tests._alembic_head import head_number, repository_head


ROOT = Path(__file__).resolve().parents[1]
CHECK = "schema_head_matches_the_matrix"


@pytest.fixture(autouse=True)
def _restore_versions():
    saved = H.VERSIONS
    yield
    H.VERSIONS = saved


def _load():
    spec = importlib.util.spec_from_file_location("eval_release_matrix_under_test", ROOT / "scripts/eval_release_matrix.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tree(tmp_path: Path, *, matrix_edit=None, extra_migration: tuple[str, str] | None = None, drop: str | None = None) -> Path:
    (tmp_path / "docs/capstone/p10").mkdir(parents=True)
    text = (ROOT / "docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md").read_text(encoding="utf-8")
    if matrix_edit:
        text = matrix_edit(text)
    (tmp_path / "docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md").write_text(text, encoding="utf-8")
    mig = tmp_path / "migrations/versions"
    mig.mkdir(parents=True)
    for p in (ROOT / "migrations/versions").glob("0*.py"):
        if drop and p.name.startswith(drop):
            continue
        (mig / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")      # real contents: the check parses revision / down_revision
    if extra_migration:
        (mig / extra_migration[0]).write_text(extra_migration[1], encoding="utf-8")
    return tmp_path


def _next_revision(name_suffix: str = "synthetic_next", down: str | None = None) -> tuple[str, str]:
    head = repository_head(ROOT / "migrations/versions")
    nxt = f"{head_number(ROOT / 'migrations/versions') + 1:04d}_{name_suffix}"
    return f"{nxt}.py", f'revision = "{nxt}"\ndown_revision = "{down or head}"\n'


def _run(root: Path) -> bool:
    H.VERSIONS = root / "migrations/versions"                                  # the evaluator reads the chain through the shared helper (restored by the autouse fixture)
    mod = _load()
    mod.ROOT = root
    mod.MATRIX = root / "docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md"
    return mod.run()[CHECK][0]


def test_the_real_repository_passes_and_the_matrix_row_declares_a_dynamically_verified_single_head():
    mod = _load()
    assert mod.run()[CHECK][0] is True
    text = (ROOT / "docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md").read_text(encoding="utf-8")
    row = next(l for l in text.splitlines() if l.startswith("| R-39 |"))
    assert "single Alembic head" in row and "verified dynamically by `scripts/eval_release_matrix.py`" in row
    assert f"{head_number(ROOT / 'migrations/versions') + 1:04d}_" not in row                              # the row never needs the next revision
    for historical in ("0031_account_closure", "0030_billing_recovery", "0029_provider_webhooks", "0028_checkout_sessions", "0027_email_attempts", "0026_managed_secrets"):
        assert historical in row                                              # earlier migration history is preserved, not erased


def test_a_matrix_row_that_stops_declaring_the_dynamic_verification_fails(tmp_path):
    stale = _tree(tmp_path / "a", matrix_edit=lambda t: t.replace("verified dynamically by `scripts/eval_release_matrix.py`", "verified by hand"))
    assert _run(stale) is False
    wrong = _tree(tmp_path / "b", matrix_edit=lambda t: t.replace("single Alembic head", "two Alembic heads"))
    assert _run(wrong) is False


def test_a_newer_linear_migration_passes_without_any_edit_but_a_broken_chain_fails(tmp_path):
    assert _run(_tree(tmp_path / "ok")) is True                                # the isolated copy of the real state passes
    assert _run(_tree(tmp_path / "next", extra_migration=_next_revision())) is True            # a new linear revision needs no matrix or evaluator edit
    assert _run(_tree(tmp_path / "branch", extra_migration=_next_revision(down="0039_speech_governance"))) is False      # a second head
    assert _run(_tree(tmp_path / "orphan", extra_migration=_next_revision(down="0099_does_not_exist"))) is False         # unresolved down_revision
    assert _run(_tree(tmp_path / "gap", drop="0030_")) is False                # a hole in the numbering (and a broken link)


def test_a_missing_r39_row_fails(tmp_path):
    gone = _tree(tmp_path / "gone", matrix_edit=lambda t: "\n".join(l for l in t.splitlines() if not l.startswith("| R-39 |")))
    assert _run(gone) is False


def test_the_check_pins_no_revision_literal():
    src = (ROOT / "scripts/eval_release_matrix.py").read_text(encoding="utf-8")
    line = next(l for l in src.splitlines() if f'"{CHECK}"' in l)
    assert "chain_ok" in src and "R-39" in src
    assert "startswith" not in line and "0040_" not in line                    # no revision literal and no accepted-prefix tuple


def test_matrix_totals_and_requirement_range_are_preserved():
    mod = _load()
    res = mod.run()
    assert res["matrix_exists_with_rows"][1].startswith("99 requirements x 7 columns")
    assert res["totals_match_rows"][1] == "rows (99, 88, 11, 0)"
    assert res["requirement_ids_contiguous_and_historical_range_preserved"][1] == "R-01..R-99"
    assert all(ok for ok, _ in res.values())
