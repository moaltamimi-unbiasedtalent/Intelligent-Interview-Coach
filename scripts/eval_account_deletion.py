#!/usr/bin/env python
"""Capstone P8 account-deletion evaluation (§51).

Deterministic, offline verification that the application-controlled deletion cascade removes
every user-owned resource, purges private files + agent checkpoints, anonymizes audit, leaves
OTHER users untouched, and is idempotent. Uses an in-memory SQLite DB and fakes — zero paid
calls, no network. Also importable (``run()``) so the pytest suite shares the invariants.
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make the script runnable directly from a fresh CI checkout (python scripts/eval_*.py):
# add the repo root to sys.path before importing any `src.*` module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select

from src import persistence as P  # noqa: E402
from src.application.account_deletion_service import AccountDeletionService  # noqa: E402


class _FakeStore:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete(self, key: str) -> None:
        self.deleted.append(key)


class _FakeAgent:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete_run(self, run_id: str, user_id: str) -> bool:
        self.deleted.append(run_id)
        return True


def _mk_user(s, subject: str) -> P.User:
    u = P.User(subject=subject, provider="password", email=f"{subject}@ex.com",
               display_name=subject)
    s.add(u)
    s.flush()
    return u


def _seed_user(s, u: P.User, *, run_id: str | None = None) -> None:
    s.add(P.UserPreference(user_id=u.id))
    s.add(P.AuthSession(token_hash=f"tok-{u.id}", user_id=u.id,
                        expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
    s.add(P.PreparationMemory(user_id=u.id, category="fact", summary="prep note",
                              source_run_id=run_id))
    s.add(P.UserFeedback(user_id=u.id, surface="interview", target_id="t1", rating="up"))
    doc = P.CandidateDocument(user_id=u.id, title="CV")
    s.add(doc)
    s.flush()
    s.add(P.DocumentVersion(document_id=doc.id, original_filename="cv.pdf",
                            storage_key=f"key-{u.id}", mime_type="application/pdf"))
    iv = P.Interview(user_id=u.id)
    s.add(iv)
    s.flush()
    q = P.Question(interview_id=iv.id, canonical_question="Tell me about yourself")
    s.add(q)
    s.flush()
    s.add(P.Answer(question_id=q.id, text="my answer"))
    s.add(P.Report(interview_id=iv.id, report={"score": 7}))
    s.add(P.InterviewSession(session_id=f"sess-{u.id}", user_id=u.id))
    ws = P.Workspace(owner_user_id=u.id, name=f"ws-{u.id}")
    s.add(ws)
    s.flush()
    s.add(P.WorkspaceMembership(workspace_id=ws.id, user_id=u.id,
                                role=P.WORKSPACE_ROLE_OWNER))
    s.add(P.AuditEvent(actor_user_id=u.id, event_type="account.login"))


def _count_for_user(sf, user_id: int) -> int:
    """Total owned rows across the primary user-owned tables (0 == fully deleted)."""
    total = 0
    with sf() as s:
        for model, col in (
            (P.UserPreference, P.UserPreference.user_id),
            (P.AuthSession, P.AuthSession.user_id),
            (P.PreparationMemory, P.PreparationMemory.user_id),
            (P.UserFeedback, P.UserFeedback.user_id),
            (P.CandidateDocument, P.CandidateDocument.user_id),
            (P.Interview, P.Interview.user_id),
            (P.InterviewSession, P.InterviewSession.user_id),
            (P.WorkspaceMembership, P.WorkspaceMembership.user_id),
        ):
            total += s.execute(select(func.count()).select_from(model)
                               .where(col == user_id)).scalar() or 0
    return total


def run() -> dict[str, tuple[bool, str]]:
    r: dict[str, tuple[bool, str]] = {}
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    engine = P.make_engine(f"sqlite:///{tmp.name}")
    P.init_db(engine, force=True)
    sf = P.make_session_factory(engine)

    with sf() as s:
        a = _mk_user(s, "alice")
        b = _mk_user(s, "bob")
        _seed_user(s, a, run_id="run-alice")
        _seed_user(s, b, run_id="run-bob")
        s.commit()
        a_id, b_id = a.id, b.id

    before_a = _count_for_user(sf, a_id)
    before_b = _count_for_user(sf, b_id)

    store, agent = _FakeStore(), _FakeAgent()
    svc = AccountDeletionService(sf, document_store=store, agent_service=agent)
    summary = svc.delete_account(a_id)

    after_a = _count_for_user(sf, a_id)
    after_b = _count_for_user(sf, b_id)

    def check(name: str, ok: bool, detail: str = "") -> None:
        r[name] = (bool(ok), detail)

    check("seeded_data", before_a > 0 and before_b > 0, f"a={before_a} b={before_b}")
    check("all_owned_rows_removed", after_a == 0, f"remaining rows for deleted user: {after_a}")
    check("other_user_untouched", after_b == before_b, f"before={before_b} after={after_b}")
    check("private_files_purged", store.deleted == [f"key-{a_id}"], f"purged={store.deleted}")
    check("checkpoints_purged", agent.deleted == ["run-alice"], f"purged={agent.deleted}")

    with sf() as s:
        user_gone = s.get(P.User, a_id) is None
        # Audit anonymized (retained, actor NULL), not deleted.
        anon = s.execute(select(func.count()).select_from(P.AuditEvent)
                         .where(P.AuditEvent.actor_user_id.is_(None))).scalar() or 0
        b_audit = s.execute(select(func.count()).select_from(P.AuditEvent)
                            .where(P.AuditEvent.actor_user_id == b_id)).scalar() or 0
    check("user_row_deleted", user_gone, "user row removed")
    check("audit_anonymized_not_deleted", anon >= 1, f"anonymized audit rows={anon}")
    check("other_user_audit_intact", b_audit >= 1, f"bob audit rows={b_audit}")

    # Idempotency: deleting again is a safe no-op.
    again = svc.delete_account(a_id)
    check("idempotent", again.existed is False, "second deletion is a no-op")

    # Summary reflects work done.
    check("summary_reports_files", summary.files_purged == 1 and summary.checkpoints_purged == 1,
          f"files={summary.files_purged} checkpoints={summary.checkpoints_purged}")

    return r


def main() -> int:
    print("ASK4MO — CAPSTONE P8 ACCOUNT-DELETION EVALUATION\n")
    results = run()
    failed = False
    for name in sorted(results):
        ok, detail = results[name]
        failed = failed or not ok
        print(f"  {name:30s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid calls: 0   Network calls: 0")
    if failed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS (account-deletion cascade holds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
