"""Migration rollback rehearsal (package 05B, PG-09, EX-12.9/12.10).

REHEARSES, on an isolated SQLite database under a directory the caller owns (never a development or hosted database), the ONLY rollback the deployment runbook
allows for the head migration:

1. upgrade to the head revision (the real Alembic chain), seed synthetic rows, take and verify a backup set (the pre-migration backup the runbook requires);
2. attempt the downgrade while the revision holds candidate-authored state: it MUST be refused (fail-closed) and change nothing (revision and every table's row
   count identical afterwards);
3. clear that state deliberately, downgrade ONE revision: it must succeed and preserve every other table's rows;
4. upgrade to head again: the schema is back at head and the preserved rows are intact;
5. restore the pre-migration backup set into a separate environment (the rollback path when a downgrade is refused or unsafe) and verify it.

APPLICATION rollback (the image or tag pointer) is documented, not executed: see ``docs/production/execution/BACKUP_RESTORE_RUNBOOK.md``. Database rollback is
forward-fix first; a downgrade is a rehearsed escape hatch for a reversible head, and a restore is the fallback.

What this proves: the head revision's fail-closed downgrade, the clean downgrade and re-upgrade, and that a pre-migration set restores, on SQLite. What it does NOT
prove: PostgreSQL DDL behaviour (the PostgreSQL branches of the migration are not executed here), timing at production data volume, or any hosted environment.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.backup_set import engine as E
from src.backup_set.drill import HOSTED_STATUS, Check, _LABEL, _SHA, _UNSAFE

ROOT = Path(__file__).resolve().parents[2]
RECORD_FORMAT = 1
_REV = re.compile(r"^revision(?:\s*:\s*[^=\n]+)?\s*=\s*['\"]([^'\"]+)['\"]", re.M)
_DOWN = re.compile(r"^down_revision(?:\s*:\s*[^=\n]+)?\s*=\s*['\"]([^'\"]+)['\"]", re.M)


def head_and_previous() -> tuple[str, str]:
    """The single head and its parent, read from the migration files (independent of Alembic itself)."""
    revs = {}
    for p in sorted((ROOT / "migrations" / "versions").glob("0*.py")):
        text = p.read_text(encoding="utf-8")
        m, d = _REV.search(text), _DOWN.search(text)
        if m and d:
            revs[m.group(1)] = d.group(1)
    heads = [r for r in revs if r not in set(revs.values())]
    if len(heads) != 1:
        raise RuntimeError("expected exactly one Alembic head")
    return heads[0], revs[heads[0]]


def _alembic(url: str, *args: str) -> tuple[int, bool]:
    """Run Alembic in a child process against ``url``. Returns (exit status, whether the output carried the migration's fail-closed refusal). The output itself is
    discarded: it can carry a path or a row value."""
    env = {**os.environ, "DATABASE_URL": url, "API_ENV": "test"}
    done = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True, timeout=900, check=False)
    return done.returncode, "Refusing to downgrade" in (done.stderr + done.stdout)


def _revision(path: Path) -> str | None:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT version_num FROM alembic_version").fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None
    finally:
        con.close()


# ---- head-specific seeders: put the state that makes the head's downgrade refuse (keyed by the revision name WITHOUT its number, so a renumber needs no edit)
def _seed_story_bank_completion(url: str) -> None:
    from src.persistence import CandidateStory, User, make_engine, make_session_factory, utcnow

    eng = make_engine(url)
    try:
        with make_session_factory(eng)() as s:
            u = s.query(User).first()
            s.add(CandidateStory(user_id=u.id, title="Synthetic archived story", archived_at=utcnow()))
            s.commit()
    finally:
        eng.dispose()


def _clear_story_bank_completion(path: Path) -> None:
    con = sqlite3.connect(path)
    try:
        con.execute("DELETE FROM candidate_stories WHERE archived_at IS NOT NULL OR confirmed_at IS NOT NULL OR opportunity_id IS NOT NULL")
        con.commit()
    finally:
        con.close()


HEAD_SEEDERS: dict[str, tuple[Callable[[str], None], Callable[[Path], None]]] = {
    "story_bank_completion": (_seed_story_bank_completion, _clear_story_bank_completion),
}


def _seed_baseline(url: str) -> None:
    from src.persistence import CandidateDocument, User, make_engine, make_session_factory

    eng = make_engine(url)
    try:
        with make_session_factory(eng)() as s:
            for n in (1, 2):
                u = User(subject=f"rehearsal-user-{n}", provider="synthetic", email=f"rehearsal{n}@example.invalid")
                s.add(u)
                s.flush()
                s.add(CandidateDocument(user_id=u.id, title=f"Synthetic document {n}", category="other"))
            s.commit()
    finally:
        eng.dispose()


@dataclass
class RehearsalResult:
    record: dict
    json_name: str | None = None
    md_name: str | None = None

    @property
    def overall(self) -> str:
        return self.record["overall"]


def run_rehearsal(*, work_dir: str | Path, record_dir: str | Path | None, label: str = "rehearsal", commit_sha: str | None = None,
                  clock: Callable[[], datetime] | None = None) -> RehearsalResult:
    if not _LABEL.match(label):
        raise ValueError("invalid rehearsal label")
    if commit_sha is not None and not _SHA.match(commit_sha):
        raise ValueError("invalid commit sha")
    now = clock or (lambda: datetime.now(timezone.utc))
    started = now()
    work = Path(work_dir)
    if work.exists() and any(work.iterdir()):
        raise ValueError("rehearsal work directory must be new or empty")
    work.mkdir(parents=True, exist_ok=True)
    head, prev = head_and_previous()
    suffix = head.split("_", 1)[1] if "_" in head else head
    db = work / "rehearsal.db"
    url = f"sqlite:///{db}"
    checks: list[Check] = []

    rc, _ = _alembic(url, "upgrade", "head")
    checks.append(Check("upgrade_to_head", "A new database upgrades to the head revision through the real migration chain", "PASS" if rc == 0 and _revision(db) == head else "FAIL",
                        {"head": head, "revision_reached": _revision(db)}))
    if rc != 0:
        return _finish(started, now, head, prev, checks, record_dir, label, commit_sha)
    _seed_baseline(url)
    base_counts = E.table_counts_sqlite(db)
    # the pre-migration backup the runbook requires (database only: the rehearsal has no documents or knowledge)
    pre_set = work / "pre-migration-set"
    created = E.create_set(E.Source(database_url=url, documents_dir=work / "no-documents"), out_dir=pre_set, execute=True, api_env="test")
    verified = created.ok and E.verify_set(pre_set).ok
    checks.append(Check("pre_migration_backup_taken", "A verified backup set is taken before the downgrade is attempted", "PASS" if verified else "FAIL",
                        {"codes": created.codes, "tables": created.counts.get("tables")}))
    seeder = HEAD_SEEDERS.get(suffix)
    state_counts = base_counts
    if seeder:
        seeder[0](url)
        state_counts = E.table_counts_sqlite(db)
        rc, refused = _alembic(url, "downgrade", "-1")
        unchanged = _revision(db) == head and E.table_counts_sqlite(db) == state_counts
        checks.append(Check("downgrade_refused_fail_closed", "The downgrade is REFUSED while candidate-authored state exists, and changes nothing", "PASS" if (rc != 0 and refused and unchanged) else "FAIL",
                            {"exit_nonzero": rc != 0, "refusal_message_present": refused, "revision_and_all_row_counts_unchanged": unchanged}))
        seeder[1](db)
    else:
        checks.append(Check("downgrade_refused_fail_closed", "The downgrade is REFUSED while candidate-authored state exists, and changes nothing", "NOT_RUN",
                            {"reason": "no seeder registered for the head revision; add one to HEAD_SEEDERS when the head's downgrade is state-guarded"}))
    pre_down = E.table_counts_sqlite(db)
    rc, _ = _alembic(url, "downgrade", "-1")
    after_down = E.table_counts_sqlite(db) if _revision(db) else {}
    kept = {t: n for t, n in pre_down.items() if t in after_down and t != "alembic_version"}
    preserved = all(after_down.get(t) == n for t, n in kept.items())
    checks.append(Check("downgrade_one_revision", "With the state cleared, the downgrade of one revision succeeds and every surviving table keeps its rows", "PASS" if (rc == 0 and _revision(db) == prev and preserved) else "FAIL",
                        {"revision_reached": _revision(db), "expected": prev, "surviving_tables_rows_preserved": preserved}))
    rc, _ = _alembic(url, "upgrade", "head")
    final_counts = E.table_counts_sqlite(db)
    same_rows = all(final_counts.get(t) == n for t, n in pre_down.items() if t != "alembic_version")
    checks.append(Check("reupgrade_to_head", "The database upgrades to head again and the preserved rows are intact", "PASS" if (rc == 0 and _revision(db) == head and same_rows) else "FAIL",
                        {"revision_reached": _revision(db), "rows_intact": same_rows}))
    restored = E.restore_set(pre_set, target_root=work / "restored-from-backup", execute=True)
    checks.append(Check("restore_of_pre_migration_backup", "The pre-migration backup restores into a separate environment (the fallback when a downgrade is refused or unsafe)",
                        "PASS" if restored.ok else "FAIL", {"codes": restored.codes}))
    checks.append(Check("application_rollback_by_image_tag", "Application rollback by pointing the deployment at the previous image tag", "NOT_RUN",
                        {"reason": "documentation only (runbook section 6); no deployment exists (DEPLOYMENT FREEZE, OD-HOSTED)"}))
    checks.append(Check("postgresql_ddl_branches", "The PostgreSQL branches of the migration (foreign keys added and dropped)", "NOT_RUN",
                        {"reason": "rehearsal runs on SQLite; the PostgreSQL branches execute only against a disposable PostgreSQL (tests/test_pg_05b.py when TEST_DATABASE_URL is set)"}))
    return _finish(started, now, head, prev, checks, record_dir, label, commit_sha)


def _finish(started, now, head, prev, checks, record_dir, label, commit_sha) -> RehearsalResult:
    finished = now()
    results = [c.result for c in checks]
    overall = "FAIL" if "FAIL" in results else ("PARTIAL" if "NOT_RUN" in results else "PASS")
    record = {"record_format": RECORD_FORMAT, "drill_id": f"rollback-{started.strftime('%Y%m%dT%H%M%SZ')}-{label}", "label": label, "kind": "offline_synthetic_sqlite",
              "started_at": started.isoformat(), "finished_at": finished.isoformat(), "commit_sha": commit_sha, "tool": E.TOOL, "hosted_verification": HOSTED_STATUS,
              "migration": {"head": head, "previous": prev}, "checks": [c.to_dict() for c in checks], "overall": overall,
              "not_exercised": ["PostgreSQL DDL branches", "hosted staging", "application image rollback", "timing at production volume"]}
    if _UNSAFE.search(json.dumps(record)):
        raise RuntimeError("rehearsal record contains a path-like or URL-like string")
    res = RehearsalResult(record)
    if record_dir is not None:
        rd = Path(record_dir)
        rd.mkdir(parents=True, exist_ok=True)
        stem = record["drill_id"]
        if (rd / f"{stem}.json").exists() or (rd / f"{stem}.md").exists():
            raise FileExistsError("rehearsal record already exists")
        (rd / f"{stem}.json").write_text(json.dumps(record, sort_keys=True, indent=1) + "\n", encoding="utf-8")
        (rd / f"{stem}.md").write_text(render_markdown(record), encoding="utf-8")
        res.json_name, res.md_name = f"{stem}.json", f"{stem}.md"
    return res


def render_markdown(r: dict) -> str:
    lines = [f"# Rollback rehearsal record: {r['drill_id']}", "", f"- Result: **{r['overall']}**", f"- Kind: `{r['kind']}` (isolated SQLite database, NOT hosted staging)",
             f"- Hosted verification: **{r['hosted_verification']}**", f"- Started: {r['started_at']}  Finished: {r['finished_at']}",
             f"- Commit: `{r['commit_sha'] or 'not recorded'}`  Tool: `{r['tool']}`",
             f"- Head revision `{r['migration']['head']}`, previous `{r['migration']['previous']}`", "", "## Steps", "", "| Step | Result | Detail |", "|---|---|---|"]
    for c in r["checks"]:
        lines.append(f"| {c['title']} | {c['result']} | {', '.join(f'{k}={v}' for k, v in c['detail'].items()) or '-'} |")
    lines += ["", "## Not exercised", ""] + [f"- {x}" for x in r["not_exercised"]]
    lines += ["", "This record contains revision names, counts and fixed codes only. No path, key, URL or candidate data.", ""]
    return "\n".join(lines)
