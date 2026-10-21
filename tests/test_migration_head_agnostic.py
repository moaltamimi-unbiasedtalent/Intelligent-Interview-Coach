"""The migration-head checks are version-independent AND not weakened.

Proof, all on disposable copies of the real versions directory (nothing under ``migrations/`` is modified):

* the shared helper (``tests/_alembic_head.py``) and every converted evaluator check PASS when a synthetic extra linear revision is appended;
* they FAIL for two heads (a branch), a gap in the numbering, a down_revision that does not resolve, a merge revision, a file whose name does not match its revision id
  and a missing required historical revision;
* the repository head still equals Alembic's own ``ScriptDirectory`` head, so a test that upgrades a database to "head" and compares with ``repository_head()`` bites.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory

import tests._alembic_head as H

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "migrations" / "versions"


@pytest.fixture()
def copy(tmp_path) -> Path:
    dst = tmp_path / "migrations" / "versions"
    dst.mkdir(parents=True)
    for p in REAL.glob("0*.py"):
        shutil.copy(p, dst / p.name)
    return dst


def _add(versions: Path, number: int, down: str | tuple[str, ...], suffix: str = "synthetic", *, rev: str | None = None, fname: str | None = None) -> str:
    rev = rev or f"{number:04d}_{suffix}"
    downs = (down,) if isinstance(down, str) else down
    text = f'revision = "{rev}"\ndown_revision = {downs[0]!r}\n' if len(downs) == 1 else f'revision = "{rev}"\ndown_revision = {downs!r}\n'
    (versions / (fname or f"{rev}.py")).write_text(text, encoding="utf-8")
    return rev


# ------------------------------------------------------------------------------------------------------------------ the real tree
def test_the_real_history_is_healthy_and_the_helper_agrees_with_alembic():
    head = H.repository_head()
    assert H.problems() == []
    assert ScriptDirectory(str(ROOT / "migrations")).get_heads() == [head]            # independent derivations agree
    chain = H.chain()
    assert chain[0].startswith("0001_") and chain[-1] == head
    assert [H.number(r) for r in chain] == list(range(1, len(chain) + 1))             # contiguous from 0001, count == highest number
    assert H.head_number() == len(chain) == len(H.migration_files())
    assert H.assert_chain(require=("0025_security_audit_incidents", "0015", "0014_opportunities")) == head


# ------------------------------------------------------------------------------------------------------------------ a new linear revision
def test_an_appended_linear_revision_passes_the_helper_and_becomes_the_head(copy):
    old = H.repository_head(copy)
    n = H.head_number(copy) + 1
    new = _add(copy, n, old)
    assert H.problems(copy) == []
    assert H.repository_head(copy) == new and H.repository_heads(copy) == [new]
    assert H.chain(copy)[-2:] == [old, new] and H.head_number(copy) == n == len(H.migration_files(copy))
    assert ScriptDirectory(str(copy.parent)).get_heads() == [new]                      # a "head" upgrade target would be the new revision, and the helper says so
    assert H.chain_ok(copy, require=("0025_security_audit_incidents",), min_head=38) == (True, new)


# ------------------------------------------------------------------------------------------------------------------ the checks still bite
def test_two_heads_fail(copy):
    head = H.repository_head(copy)
    n = H.head_number(copy) + 1
    _add(copy, n, head, "left")
    _add(copy, n + 1, H.chain(copy)[-2], "right")                                       # a second child of the old head: a branch
    found = H.problems(copy)
    assert any("exactly one head" in f for f in found) and any("more than one child" in f for f in found)
    assert H.chain_ok(copy)[0] is False
    with pytest.raises(H.MigrationChainError):
        H.repository_head(copy)
    with pytest.raises(AssertionError):
        H.assert_chain(copy)
    assert len(ScriptDirectory(str(copy.parent)).get_heads()) == 2                     # Alembic itself sees the same branch


def test_a_gap_in_the_numbering_fails(copy):
    (copy / next(p.name for p in copy.glob("0030_*.py"))).unlink()                     # removing a middle file also breaks the link above it
    assert any("not contiguous" in f for f in H.problems(copy))
    assert H.chain_ok(copy)[0] is False


def test_a_pure_numbering_gap_with_a_resolving_chain_fails(copy):
    head = H.repository_head(copy)
    _add(copy, H.head_number(copy) + 2, head, "skips_0041")                            # 0042 chained straight onto 0040: linear, but 0041 is missing
    found = H.problems(copy)
    assert found == [f for f in found if "not contiguous" in f] and found
    assert H.chain_ok(copy)[0] is False


def test_a_down_revision_that_does_not_resolve_fails(copy):
    _add(copy, H.head_number(copy) + 1, "0099_does_not_exist", "orphan")
    found = H.problems(copy)
    assert any("does not resolve" in f for f in found) and any("exactly one head" in f or "exactly one base" in f for f in found)
    assert H.chain_ok(copy)[0] is False


def test_a_merge_revision_fails(copy):
    head = H.repository_head(copy)
    n = H.head_number(copy) + 1
    a = _add(copy, n, head, "a")
    _add(copy, n + 1, (a, H.chain(copy)[-3]), "merge")
    assert any("merge revision" in f for f in H.problems(copy))


def test_a_file_name_that_does_not_match_its_revision_id_fails(copy):
    _add(copy, H.head_number(copy) + 1, H.repository_head(copy), "x", fname=f"{H.head_number(copy) + 1:04d}_other_name.py")
    assert any("does not start with its revision id" in f for f in H.problems(copy))


def test_a_missing_required_historical_revision_fails(copy):
    assert H.chain_ok(copy, require=("0025_security_audit_incidents",))[0] is True
    assert H.chain_ok(copy, require=("0025_security_audit_incidents", "0099_never_existed"))[0] is False
    assert H.chain_ok(copy, require=("0099",))[0] is False                              # a number prefix with no revision
    assert H.chain_ok(copy, min_head=H.head_number(copy) + 1)[0] is False              # head older than the registered baseline
    (copy / "0025_security_audit_incidents.py").unlink()
    ok, detail = H.chain_ok(copy, require=("0025_security_audit_incidents",))
    assert ok is False and "required historical revision" in detail


def test_unreadable_revision_declarations_fail(copy):
    (copy / "0099_broken.py").write_text("# no revision here\n", encoding="utf-8")
    with pytest.raises(H.MigrationChainError):
        H.revisions(copy)
    ok, detail = H.chain_ok(copy)
    assert ok is False and "no revision/down_revision" in detail


# ------------------------------------------------------------------------------------------------------------------ the converted evaluators
# (evaluator script, name of its converted migration check)
EVALUATORS = [
    ("eval_admin_access", "no_migration_added"),
    ("eval_admin_design", "no_migration_added"),
    ("eval_admin_foundation", "no_migration_added"),
    ("eval_product_positioning", "no_migration_added"),
    ("eval_admin_qualification", "one_alembic_head_after_the_w12_4b_to_w12_4d_p5a_migrations"),
    ("eval_admin_security", "alembic_head_is_single_and_0025_is_in_the_chain"),
    ("eval_admin_support", "migration_head_is_support"),
    ("eval_admin_entitlements", "migration_chain_valid"),
    ("eval_engineering_quality", "migration_chain_contiguous_from_registered_baseline"),
    ("eval_global_fallback", "no_schema_change"),
    ("eval_rc_p10_003", "alembic_head_single_and_the_immutable_manifest_still_records_0025"),
    ("eval_w11_integrated", "one_alembic_head"),
    ("eval_release_matrix", "schema_head_matches_the_matrix"),
]


def _result(script: str, check: str, monkeypatch, versions: Path) -> bool:
    monkeypatch.setattr(H, "VERSIONS", versions)
    spec = importlib.util.spec_from_file_location(f"{script}_headagnostic", ROOT / "scripts" / f"{script}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = mod.run()
    if isinstance(out, tuple):
        out = out[0]
    if isinstance(out, list):                                                           # evaluators that return a list of (name, ok, detail)
        out = {row[0]: (row[1], row[2]) for row in out}
    return bool(out[check][0])


@pytest.mark.parametrize("script, check", EVALUATORS)
def test_each_converted_evaluator_check_passes_on_the_real_tree_and_on_an_appended_revision(script, check, copy, monkeypatch):
    assert _result(script, check, monkeypatch, REAL) is True
    _add(copy, H.head_number(copy) + 1, H.repository_head(copy))
    assert _result(script, check, monkeypatch, copy) is True                            # no edit needed for a newer linear revision


@pytest.mark.parametrize("script, check", EVALUATORS)
def test_each_converted_evaluator_check_fails_on_a_branch_a_gap_and_an_orphan(script, check, copy, tmp_path, monkeypatch):
    broken = {}
    b = tmp_path / "branch"
    shutil.copytree(copy, b)
    _add(b, H.head_number(b) + 1, H.repository_head(b), "left")
    _add(b, H.head_number(b) + 1, H.chain(b)[-2], "right", rev=f"{H.head_number(b):04d}_right")
    broken["branch"] = b
    g = tmp_path / "gap"
    shutil.copytree(copy, g)
    _add(g, H.head_number(g) + 2, H.repository_head(g), "skip")
    broken["gap"] = g
    o = tmp_path / "orphan"
    shutil.copytree(copy, o)
    _add(o, H.head_number(o) + 1, "0099_missing", "orphan")
    broken["orphan"] = o
    for name, v in broken.items():
        assert _result(script, check, monkeypatch, v) is False, name


def test_the_checks_requiring_a_historical_revision_fail_when_it_is_missing(copy, monkeypatch):
    for script, check in (("eval_admin_security", "alembic_head_is_single_and_0025_is_in_the_chain"), ("eval_release_matrix", "schema_head_matches_the_matrix"),
                          ("eval_rc_p10_003", "alembic_head_single_and_the_immutable_manifest_still_records_0025")):
        # drop 0025 AND repair the link above it so ONLY the required-revision property is violated
        v = copy.parent / f"nofive_{script}"
        shutil.copytree(copy, v)
        (v / "0025_security_audit_incidents.py").unlink()
        up = next(p for p in v.glob("0026_*.py"))
        up.write_text(up.read_text(encoding="utf-8").replace("0025_security_audit_incidents", "0024_reporting_analytics"), encoding="utf-8")
        for p in v.glob("0*.py"):
            if "0025_security_audit_incidents" in p.read_text(encoding="utf-8"):
                p.write_text(p.read_text(encoding="utf-8").replace("0025_security_audit_incidents", "0024_reporting_analytics"), encoding="utf-8")
        found = H.problems(v, require=("0025_security_audit_incidents",))
        assert any("required historical revision" in f for f in found), found
        assert _result(script, check, monkeypatch, v) is False


def test_no_evaluator_or_test_hard_codes_a_head_literal_again():
    import re

    pat = re.compile(r"get_heads\(\) == \[\"0|== \"0040_knowledge|startswith\(\(\"0014_")
    offenders = [str(p.relative_to(ROOT)) for d in ("scripts", "tests") for p in (ROOT / d).rglob("*.py") if p.name != Path(__file__).name and pat.search(p.read_text(encoding="utf-8"))]
    assert offenders == []
