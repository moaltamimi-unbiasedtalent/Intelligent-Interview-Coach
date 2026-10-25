"""05B (PG-09, EX-12.9/12.10): the migration rollback rehearsal on an isolated SQLite database, its record, and proof that the harness bites (a seeder that does not make
the downgrade refuse turns the rehearsal into a FAIL). Offline; the real Alembic chain runs in child processes against a database under tmp_path."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from src.backup_set import rollback as RB
from tests._alembic_head import repository_head, revisions

ROOT = Path(__file__).resolve().parents[1]
PATHISH = re.compile(r"(/Users/|/Volumes/|/private/|/tmp/|/var/folders/|://)")


def test_head_and_previous_agree_with_the_independent_chain_parser():
    head, prev = RB.head_and_previous()
    assert head == repository_head() and revisions()[head][0] == (prev,)


@pytest.fixture(scope="module")
def rehearsal(tmp_path_factory):
    base = tmp_path_factory.mktemp("rollback")
    return RB.run_rehearsal(work_dir=base / "work", record_dir=base / "records", label="unit", commit_sha="abc1234"), base


def test_rehearsal_upgrades_refuses_the_downgrade_fail_closed_downgrades_cleanly_and_reupgrades(rehearsal):
    res, _ = rehearsal
    by = {c["id"]: c for c in res.record["checks"]}
    head, _prev = RB.head_and_previous()
    seeded = head.split("_", 1)[1] in RB.HEAD_SEEDERS
    middle = ("protected_state_retained", "unsafe_downgrade_not_attempted", "new_target_protected_state") if head.endswith("agent_run_controls") else ("downgrade_one_revision", "reupgrade_to_head")
    for step in ("upgrade_to_head", "pre_migration_backup_taken", *middle, "restore_of_pre_migration_backup"):
        assert by[step]["result"] == "PASS", (step, by[step])
    refusal = by["downgrade_refused_fail_closed"]
    if seeded:
        assert refusal["result"] == "PASS" and refusal["detail"] == {"exit_nonzero": True, "refusal_message_present": True, "revision_and_all_row_counts_unchanged": True}
    else:
        assert refusal["result"] == "NOT_RUN"                              # a new head without a registered seeder is honestly reported, never silently green
    # the two things this rehearsal can NOT show are recorded as NOT_RUN, so the overall result is PARTIAL, never PASS
    assert by["application_rollback_by_image_tag"]["result"] == "NOT_RUN" and by["postgresql_ddl_branches"]["result"] == "NOT_RUN"
    assert res.overall == "PARTIAL" and not any(c["result"] == "FAIL" for c in res.record["checks"])


def test_rehearsal_record_is_written_as_json_and_markdown_with_no_path_url_or_data(rehearsal):
    res, base = rehearsal
    data = json.loads((base / "records" / res.json_name).read_text())
    md = (base / "records" / res.md_name).read_text()
    assert data == res.record and data["hosted_verification"] == "NOT RUN (OD-HOSTED)" and data["kind"] == "offline_synthetic_sqlite" and data["commit_sha"] == "abc1234"
    assert data["migration"]["head"] == repository_head() and "NOT RUN (OD-HOSTED)" in md and "PostgreSQL DDL branches" in md
    assert not PATHISH.search(json.dumps(data) + md) and "example.invalid" not in md


def test_the_rehearsal_refuses_a_used_work_directory_and_never_overwrites_a_record(rehearsal, tmp_path):
    res, base = rehearsal
    with pytest.raises(ValueError):
        RB.run_rehearsal(work_dir=base / "work", record_dir=None, label="again")
    with pytest.raises(ValueError):
        RB.run_rehearsal(work_dir=tmp_path / "w", record_dir=None, label="bad label")
    assert (base / "records" / res.json_name).is_file()


def test_the_harness_bites_a_state_seeder_that_fails_to_make_the_downgrade_refuse_turns_the_rehearsal_into_a_fail(tmp_path, monkeypatch):
    head, _ = RB.head_and_previous()
    suffix = head.split("_", 1)[1]
    if suffix not in RB.HEAD_SEEDERS:
        pytest.skip("head has no registered seeder")
    monkeypatch.setitem(RB.HEAD_SEEDERS, suffix, (lambda url: None, lambda path: None))       # seeds nothing: the downgrade will NOT be refused
    res = RB.run_rehearsal(work_dir=tmp_path / "w", record_dir=None, label="neg")
    by = {c["id"]: c["result"] for c in res.record["checks"]}
    assert by["downgrade_refused_fail_closed"] == "FAIL" and res.overall == "FAIL"


def test_the_rehearsal_cli_exit_status_and_output(tmp_path, capsys):
    sys.path.insert(0, str(ROOT / "scripts"))
    import rollback_rehearsal as cli

    rc = cli.main(["--record-dir", str(tmp_path / "rec"), "--label", "cli"])
    out = capsys.readouterr().out
    assert rc == 3 and '"overall": "PARTIAL"' in out and not PATHISH.search(out)             # 3 = PARTIAL (documented NOT_RUN steps), 0 would mean nothing was left unexercised
    assert len(list((tmp_path / "rec").glob("rollback-*-cli.json"))) == 1
