"""Privacy schema invariant (02A integration fix): migrations after the W9.8 baseline may not touch candidate privacy, export, deletion or ownership tables, and the
approved Knowledge alert migration 0040 changes only the notification category constraint. Offline; negative cases use disposable migration files in tmp_path."""

from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

import tests.conftest  # noqa: F401  (isolation first)
from src.persistence import Base

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("eval_privacy_controls", ROOT / "scripts/eval_privacy_controls.py")
EV = importlib.util.module_from_spec(spec)
spec.loader.exec_module(EV)

KNOWN = set(Base.metadata.tables)


def _write(tmp_path: Path, name: str, body: str) -> Path:
    (tmp_path / name).write_text(textwrap.dedent(body), encoding="utf-8")
    return tmp_path


def test_the_real_history_holds_the_invariant_and_0040_touches_only_admin_notifications():
    assert EV.post_baseline_privacy_touches(ROOT / "migrations/versions", KNOWN) == {}
    src = (ROOT / "migrations/versions/0040_knowledge_alert_categories.py").read_text(encoding="utf-8")
    assert EV.migration_tables_touched(src, KNOWN) == {"admin_notifications"}
    assert "admin_notifications" not in EV.PRIVACY_TABLES
    assert EV.PRIVACY_TABLES <= KNOWN                                           # every protected name is a real table (no silent typo)


def test_the_evaluator_check_passes_without_a_hard_coded_head_allowlist():
    ok, detail = EV.run()["no_unreviewed_privacy_schema_change"]
    assert ok, detail
    assert "no_migration_added" not in EV.run()
    assert "0040_" not in (ROOT / "scripts/eval_privacy_controls.py").read_text(encoding="utf-8")        # not an appended allowlist entry


@pytest.mark.parametrize("body, table", [
    ('def upgrade():\n    op.add_column("users", sa.Column("x", sa.Text()))\n', "users"),
    ('def upgrade():\n    with op.batch_alter_table("candidate_documents") as b:\n        b.drop_column("filename")\n', "candidate_documents"),
    ('def upgrade():\n    op.execute("UPDATE privacy_requests SET status = \'x\'")\n', "privacy_requests"),
    ('def upgrade():\n    op.drop_table("share_grants")\n', "share_grants"),
])
def test_a_genuine_unauthorised_privacy_schema_change_fails_whatever_its_revision_number(tmp_path, body, table):
    for number in ("0041", "0099", "0150"):
        d = tmp_path / number
        d.mkdir()
        _write(d, f"{number}_change.py", '"""fixture"""\nimport sqlalchemy as sa\nfrom alembic import op\n' + body)
        assert EV.post_baseline_privacy_touches(d, KNOWN) == {f"{number}_change.py": [table]}


def test_non_privacy_tables_docstrings_comments_and_pre_baseline_history_do_not_trip_it(tmp_path):
    _write(tmp_path, "0041_ok.py", '"""Mentions users and privacy_requests only in prose."""\n# users privacy_requests\nfrom alembic import op\n'
                                   'def upgrade():\n    op.add_column("admin_notifications", None)\n')
    assert EV.post_baseline_privacy_touches(tmp_path, KNOWN) == {}
    other = tmp_path / "old"
    other.mkdir()
    _write(other, "0014_historic.py", 'from alembic import op\ndef upgrade():\n    op.add_column("users", None)\n')              # reviewed history is exempt
    assert EV.post_baseline_privacy_touches(other, KNOWN) == {}


def test_migration_0040_changes_only_the_notification_category_constraint(tmp_path, monkeypatch):
    from alembic import command
    from alembic.script import ScriptDirectory
    from tests.test_billing_f1_qualification import _alembic

    cfg, url = _alembic(tmp_path, monkeypatch)
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == ["0040_knowledge_alert_categories"]
    assert script.get_revision("0040_knowledge_alert_categories").down_revision == "0039_speech_governance"
    command.upgrade(cfg, "0039_speech_governance")
    eng = create_engine(url)
    ins = ("insert into admin_notifications (public_id, category, severity, dedupe_key, state, source_type, title, occurrence_count, first_seen_at, last_seen_at, created_at, updated_at, revision) "
           "values ('keep1', 'job_failed', 'high', 'k1', 'active', 'job', 't', 1, '2026-01-01', '2026-01-01', '2026-01-01', '2026-01-01', 0)")
    with eng.begin() as c:
        c.execute(text(ins))

    def schema() -> dict[str, str]:
        with eng.connect() as c:
            return {n: (sql or "") for n, sql in c.execute(text("select name, sql from sqlite_master where type in ('table','index') and name not like 'sqlite_%'"))}

    def rows(table: str) -> list:
        with eng.connect() as c:
            return [tuple(r) for r in c.execute(text(f"select * from {table} order by 1"))]

    before = schema()
    privacy_rows_before = {t: rows(t) for t in sorted(EV.PRIVACY_TABLES & set(before))}
    notifications_before = rows("admin_notifications")
    command.upgrade(cfg, "head")
    after = schema()
    changed = {n for n in set(before) | set(after) if before.get(n) != after.get(n)}
    assert changed == {"admin_notifications"}, changed                           # nothing else in the schema changed, privacy tables included
    assert {t: rows(t) for t in privacy_rows_before} == privacy_rows_before    # no privacy row was touched
    assert rows("admin_notifications") == notifications_before                  # the existing alert was preserved untouched
