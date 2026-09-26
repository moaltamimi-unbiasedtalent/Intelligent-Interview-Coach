#!/usr/bin/env python
"""Capstone P9 restart / recovery / backup-restore evaluation (AC-20).

Deterministic proof on DISPOSABLE local state (SQLite analog of the hosted Postgres flow):
seed representative owned records → simulate an application RESTART (dispose the engine, reopen
on the same file) and verify persistence → BACKUP the file → DESTROY/replace the state → RESTORE
from backup → reopen and verify the owned records survive. No real user data, no network.

The production Postgres path is exercised by `deploy/scripts/{backup,restore,migrate}.sh`
(syntax-checked) and documented in `docs/capstone/p8_hosting_operations.md`; a real hosted
restore remains part of EX-12 (NOT RUN without an authorized deployment).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select  # noqa: E402

from src import persistence as P  # noqa: E402


def _seed(sf) -> int:
    with sf() as s:
        u = P.User(subject="rc-user", provider="password", email="rc@ex.com",
                   display_name="RC User")
        s.add(u)
        s.flush()
        s.add(P.UserPreference(user_id=u.id))
        s.add(P.PreparationMemory(user_id=u.id, category="fact", summary="survives restart"))
        doc = P.CandidateDocument(user_id=u.id, title="CV")
        s.add(doc)
        s.flush()
        s.add(P.DocumentVersion(document_id=doc.id, original_filename="cv.pdf",
                                storage_key="rc-key", mime_type="application/pdf"))
        iv = P.Interview(user_id=u.id)
        s.add(iv)
        s.flush()
        q = P.Question(interview_id=iv.id, canonical_question="Q1")
        s.add(q)
        s.flush()
        s.add(P.Answer(question_id=q.id, text="my answer"))
        s.add(P.Report(interview_id=iv.id, report={"score": 8}))
        ws = P.Workspace(owner_user_id=u.id, name="rc-ws")
        s.add(ws)
        s.flush()
        s.add(P.WorkspaceMembership(workspace_id=ws.id, user_id=u.id,
                                    role=P.WORKSPACE_ROLE_OWNER))
        s.add(P.AuthSession(token_hash="rc-tok", user_id=u.id,
                            expires_at=datetime.now(timezone.utc)))
        s.commit()
        return u.id


def _snapshot(sf, user_id: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    with sf() as s:
        for label, model, col in (
            ("preferences", P.UserPreference, P.UserPreference.user_id),
            ("memory", P.PreparationMemory, P.PreparationMemory.user_id),
            ("documents", P.CandidateDocument, P.CandidateDocument.user_id),
            ("interviews", P.Interview, P.Interview.user_id),
            ("memberships", P.WorkspaceMembership, P.WorkspaceMembership.user_id),
            ("sessions", P.AuthSession, P.AuthSession.user_id),
        ):
            counts[label] = s.execute(
                select(func.count()).select_from(model).where(col == user_id)).scalar() or 0
        counts["reports"] = s.execute(select(func.count()).select_from(P.Report)).scalar() or 0
    return counts


def run() -> dict[str, tuple[bool, str]]:
    r: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        r[name] = (bool(ok), detail)

    tmpdir = tempfile.mkdtemp(prefix="ask4mo_rc_")
    db = Path(tmpdir) / "app.db"
    backup = Path(tmpdir) / "backup.db"

    # 1) Clean DB → head (migration path already proven separately; here we build the schema).
    engine = P.make_engine(f"sqlite:///{db}")
    P.init_db(engine, force=True)
    sf = P.make_session_factory(engine)
    user_id = _seed(sf)
    seeded = _snapshot(sf, user_id)
    check("seeded_state", all(v > 0 for v in seeded.values()), f"{seeded}")

    # 2) RESTART: dispose the engine and reopen on the SAME file — committed state must survive.
    engine.dispose()
    engine2 = P.make_engine(f"sqlite:///{db}")
    sf2 = P.make_session_factory(engine2)
    after_restart = _snapshot(sf2, user_id)
    check("survives_restart", after_restart == seeded, f"{after_restart}")

    # 3) BACKUP: copy the datastore.
    engine2.dispose()
    shutil.copy2(db, backup)
    check("backup_created", backup.exists() and backup.stat().st_size > 0,
          f"backup {backup.stat().st_size} bytes")

    # 4) DESTROY/REPLACE the live state (disposable).
    db.unlink()
    check("state_destroyed", not db.exists(), "live DB removed")

    # 5) RESTORE from backup and reopen.
    shutil.copy2(backup, db)
    engine3 = P.make_engine(f"sqlite:///{db}")
    sf3 = P.make_session_factory(engine3)
    after_restore = _snapshot(sf3, user_id)
    check("survives_restore", after_restore == seeded, f"{after_restore}")

    # 6) Representative owned records present after restore.
    with sf3() as s:
        user = s.get(P.User, user_id)
    check("owned_user_restored", user is not None and user.email == "rc@ex.com",
          "account restored with identity intact")
    engine3.dispose()

    return r


def main() -> int:
    print("ASK4MO — CAPSTONE P9 RESTART / RECOVERY / BACKUP-RESTORE (AC-20)\n")
    results = run()
    failed = False
    for name in sorted(results):
        ok, detail = results[name]
        failed = failed or not ok
        print(f"  {name:24s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid calls: 0   Network calls: 0   (SQLite disposable state; Postgres path via deploy/scripts)")
    if failed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS (restart/recovery + backup/restore hold on disposable state)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
