"""W12.4D-P2-A CI remediation: the release matrix tracks the CURRENT Alembic head (R-39), and the integrity check still fails on a wrong declaration, an
unexpected migration or a missing row. Negative cases run on COPIES in a temporary tree; no real evidence file is modified."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK = "schema_head_matches_the_matrix"
HEAD = "0036_multilingual_aliases"


def _load():
    spec = importlib.util.spec_from_file_location("eval_release_matrix_under_test", ROOT / "scripts/eval_release_matrix.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tree(tmp_path: Path, *, matrix_edit=None, extra_migration: str | None = None) -> Path:
    (tmp_path / "docs/capstone/p10").mkdir(parents=True)
    text = (ROOT / "docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md").read_text(encoding="utf-8")
    if matrix_edit:
        text = matrix_edit(text)
    (tmp_path / "docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md").write_text(text, encoding="utf-8")
    mig = tmp_path / "migrations/versions"
    mig.mkdir(parents=True)
    for p in (ROOT / "migrations/versions").glob("0*.py"):
        (mig / p.name).write_text("", encoding="utf-8")                      # names only: the check reads file names
    if extra_migration:
        (mig / extra_migration).write_text("", encoding="utf-8")
    return tmp_path


def _run(root: Path) -> bool:
    mod = _load()
    mod.ROOT = root
    mod.MATRIX = root / "docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md"
    return mod.run()[CHECK][0]


def test_the_real_repository_passes_and_the_matrix_declares_the_current_head_with_provenance():
    mod = _load()
    assert mod.run()[CHECK][0] is True
    text = (ROOT / "docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md").read_text(encoding="utf-8")
    row = next(l for l in text.splitlines() if l.startswith("| R-39 |"))
    assert HEAD in row and "W12.4D-P2-A" in row                                # current head and its provenance
    for historical in ("0031_account_closure", "0030_billing_recovery", "0029_provider_webhooks", "0028_checkout_sessions", "0027_email_attempts", "0026_managed_secrets"):
        assert historical in row                                              # earlier migration history is preserved, not erased


def test_a_stale_or_wrong_declaration_in_the_matrix_fails(tmp_path):
    stale = _tree(tmp_path / "a", matrix_edit=lambda t: t.replace(HEAD, "0031_account_closure"))
    assert _run(stale) is False
    wrong = _tree(tmp_path / "b", matrix_edit=lambda t: t.replace(HEAD, "0099_something_else"))
    assert _run(wrong) is False


def test_an_unexpected_newer_migration_fails_until_the_matrix_is_deliberately_updated(tmp_path):
    assert _run(_tree(tmp_path / "ok")) is True                                # the isolated copy of the real state passes
    assert _run(_tree(tmp_path / "extra", extra_migration="0037_unreviewed_change.py")) is False


def test_a_missing_r39_row_fails(tmp_path):
    gone = _tree(tmp_path / "gone", matrix_edit=lambda t: "\n".join(l for l in t.splitlines() if not l.startswith("| R-39 |")))
    assert _run(gone) is False


def test_the_check_is_pinned_to_one_exact_head_and_is_not_a_wildcard():
    src = (ROOT / "scripts/eval_release_matrix.py").read_text(encoding="utf-8")
    line = next(l for l in src.splitlines() if CHECK in l)
    assert f'startswith("{HEAD}")' in line and "R-39" in line
    assert not re.search(r"startswith\(\(", line)                              # no accepted-prefix tuple that would let any future head through


def test_matrix_totals_and_requirement_range_are_preserved():
    mod = _load()
    res = mod.run()
    assert res["matrix_exists_with_rows"][1].startswith("99 requirements x 7 columns")
    assert res["totals_match_rows"][1] == "rows (99, 88, 11, 0)"
    assert res["requirement_ids_contiguous_and_historical_range_preserved"][1] == "R-01..R-99"
    assert all(ok for ok, _ in res.values())
