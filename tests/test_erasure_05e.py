"""05E (W9.8-D10, W9.8-D1a, W10.10-AUDIT-CTX): account and privacy-request deletion are complete, idempotent and resumable, and the preparation-run ownership index is
the only way chat data is ever found. Offline; fakes for the document store and the checkpoint saver; cross-user isolation throughout."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select, text

import tests.conftest  # noqa: F401  (isolation first)
from src import persistence as P
from src.application.account_deletion_service import AccountDeletionService, DeletionIncomplete
from src.documents.storage import LocalDocumentStore
from src.persistence import Base, make_session_factory
from src.privacy import erasure
from src.privacy.preparation import PreparationRunIndex, sweep_orphaned_runs
from tests._erasure_world_05e import STATE_OVERRIDES, make_row

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def sf():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def _user(sf, tag: str | None = None, **kw) -> int:
    tag = tag or uuid.uuid4().hex[:10]
    with sf() as s:
        u = P.User(subject=f"s-{tag}", provider="password", email=f"{tag}@example.com", display_name=f"Name {tag}", **kw)
        s.add(u)
        s.commit()
        return u.id


class FakeAgent:
    """A checkpoint adapter that records every call. It has NO list/scan capability at all."""

    def __init__(self, runs: dict[str, str] | None = None) -> None:
        self.runs = dict(runs or {})
        self.fail = False
        self.purged: list[str] = []
        self.lookups: list[str] = []

    def purge_run(self, run_id: str) -> bool:
        if self.fail:
            raise RuntimeError("store down")
        self.runs.pop(run_id, None)
        self.purged.append(run_id)
        return True

    def delete_run(self, run_id: str, user_id: str | None) -> bool:
        self.lookups.append(run_id)
        if self.runs.get(run_id) != user_id:
            return False
        return self.purge_run(run_id)


# ----------------------------------------------------------------------------------------------------------------- the schema-derived inventory
def test_every_reference_to_a_user_in_the_schema_is_enumerated_and_every_name_like_one_is_classified():
    refs = erasure.user_references()
    keys = {(r.table, r.column) for r in refs}
    # the foreign keys are derived, not typed in: the well-known ones must be there, and so must the non-FK references
    for expected in (("candidate_documents", "user_id"), ("interviews", "user_id"), ("audit_events", "actor_user_id"), ("support_tickets", "owner_user_id"),
                     ("preparation_runs", "owner_user_id"), ("privacy_requests", "subject_user_id"), ("report_configurations", "owner_user_id"),
                     ("email_attempts", "user_id")):
        assert expected in keys, expected
    # a column that merely LOOKS like a user reference must be classified on purpose (a new one fails here until somebody decides what deletion does with it)
    assert erasure.unclassified_user_like_columns() == []
    for table, column, _action in erasure.NON_FK_USER_REFERENCES:
        assert column in Base.metadata.tables[table].c
    for (table, column) in erasure.NOT_USER_REFERENCES:
        assert column in Base.metadata.tables[table].c


def test_an_unclassified_new_reference_like_column_is_detected():
    from sqlalchemy import Column, Integer, MetaData, Table

    md = MetaData()
    Table("users", md, Column("id", Integer, primary_key=True))
    Table("brand_new_table", md, Column("id", Integer, primary_key=True), Column("owner_account", Integer))
    assert erasure.unclassified_user_like_columns(md) == [("brand_new_table", "owner_account")]


def test_a_new_table_with_a_user_foreign_key_is_swept_without_any_code_change_here():
    from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table

    md = MetaData()
    Table("users", md, Column("id", Integer, primary_key=True))
    Table("future_notes", md, Column("id", Integer, primary_key=True), Column("user_id", ForeignKey("users.id", ondelete="CASCADE")), Column("body", String))
    Table("future_log", md, Column("id", Integer, primary_key=True), Column("actor_user_id", ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    engine = create_engine("sqlite://")
    md.create_all(engine)
    with engine.begin() as c:
        c.execute(text("insert into users (id) values (1), (2)"))
        c.execute(text("insert into future_notes (user_id, body) values (1, 'a'), (2, 'b')"))
        c.execute(text("insert into future_log (actor_user_id) values (1), (2)"))
    Session = make_session_factory(engine)
    with Session() as s:
        changed = erasure.sweep(s, 1, metadata=md)
        s.commit()
        assert changed == {"future_notes.user_id": 1, "future_log.actor_user_id": 1}
        assert erasure.residual_references(s, 1, metadata=md) == {}
        assert s.execute(text("select count(*) from future_notes where user_id = 2")).scalar() == 1             # the bystander is untouched
        assert s.execute(text("select count(*) from future_log where actor_user_id = 2")).scalar() == 1
        assert erasure.sweep(s, 1, metadata=md) == {}                                                           # idempotent


# ----------------------------------------------------------------------------------------------------------------- the whole schema, one account
def _world(sf, victim: int, bystander: int, refs, overrides=None):
    counts_before: dict[str, int] = {}
    with sf() as s:
        conn = s.connection()
        for ref in refs:
            table = Base.metadata.tables[ref.table]
            extra = {**STATE_OVERRIDES.get(ref.table, {}), **(overrides or {}).get(ref.table, {})}
            for owner in (victim, bystander):
                make_row(conn, table, **{ref.column: owner}, **extra)
        s.commit()
        for ref in refs:
            table = Base.metadata.tables[ref.table]
            counts_before[f"{ref.table}.{ref.column}"] = s.scalar(select(func.count()).select_from(table).where(table.c[ref.column] == bystander)) or 0
    return counts_before


def test_deleting_an_account_leaves_no_row_anywhere_that_references_it_and_never_touches_another_account(sf):
    victim, bystander = _user(sf, "victim"), _user(sf, "bystander")
    refs = [r for r in erasure.user_references() if r.table != "preparation_runs"]
    before = _world(sf, victim, bystander, refs)
    assert before and all(n >= 1 for n in before.values()), before
    with sf() as s:                                            # the world really holds victim rows to remove
        n_victim = sum(s.scalar(select(func.count()).select_from(Base.metadata.tables[r.table]).where(Base.metadata.tables[r.table].c[r.column] == victim)) or 0 for r in refs)
    assert n_victim >= len(refs)
    summary = AccountDeletionService(sf, document_store=SimpleNamespace(delete=lambda k: True)).delete_account(victim)
    assert summary.existed and summary.residual == {} and summary.sql_complete, summary.residual
    with sf() as s:
        assert s.get(P.User, victim) is None and s.get(P.User, bystander) is not None
        assert erasure.residual_references(s, victim) == {}
        after = {f"{r.table}.{r.column}": s.scalar(select(func.count()).select_from(Base.metadata.tables[r.table]).where(Base.metadata.tables[r.table].c[r.column] == bystander)) or 0
                 for r in refs}
    assert after == before                                     # cross-user isolation: every bystander row survives


def test_deletion_is_idempotent_and_a_second_run_changes_nothing(sf):
    victim, bystander = _user(sf, "victim"), _user(sf, "bystander")
    refs = [r for r in erasure.user_references() if r.table != "preparation_runs"]
    _world(sf, victim, bystander, refs)
    svc = AccountDeletionService(sf, document_store=SimpleNamespace(delete=lambda k: True))
    first = svc.delete_account(victim)
    with sf() as s:
        snapshot = {t.name: s.scalar(select(func.count()).select_from(t)) for t in Base.metadata.sorted_tables}
    second = svc.delete_account(victim)
    assert first.existed and not second.existed and second.residual == {} and second.deleted_rows == {}
    with sf() as s:
        assert {t.name: s.scalar(select(func.count()).select_from(t)) for t in Base.metadata.sorted_tables} == snapshot


def test_the_sweep_mirrors_the_foreign_key_actions_for_operator_references_on_sqlite(sf):
    admin, other = _user(sf, "admin"), _user(sf, "other")
    with sf() as s:
        conn = s.connection()
        make_row(conn, Base.metadata.tables["knowledge_sources"], created_by_user_id=admin)
        make_row(conn, Base.metadata.tables["report_configurations"], owner_user_id=admin)
        make_row(conn, Base.metadata.tables["email_attempts"], user_id=admin)
        make_row(conn, Base.metadata.tables["jobs"], created_by_user_id=admin)
        s.commit()
    summary = AccountDeletionService(sf).delete_account(admin)
    assert summary.fk_swept.get("report_configurations.owner_user_id") == 1                      # CASCADE reference: deleted
    assert summary.fk_swept.get("knowledge_sources.created_by_user_id") == 1                     # SET NULL reference: cleared
    assert summary.fk_swept.get("email_attempts.user_id") == 1 and summary.fk_swept.get("jobs.created_by_user_id") == 1
    with sf() as s:
        assert s.scalar(text("select count(*) from knowledge_sources where created_by_user_id is null")) == 1
        assert s.scalar(text("select count(*) from report_configurations")) == 0
    assert other is not None


# ----------------------------------------------------------------------------------------------------------------- retained modes stay exactly as documented
def test_with_a_retained_billing_reference_only_the_documented_billing_rows_and_the_shell_remain(sf):
    victim, bystander = _user(sf, "victim"), _user(sf, "bystander")
    refs = [r for r in erasure.user_references() if r.table != "preparation_runs"]
    _world(sf, victim, bystander, refs, overrides={"billing_provider_links": {"provider_state": "active"}})               # a LIVE provider subscription: the closure is blocked
    with pytest.raises(Exception) as refused:
        AccountDeletionService(sf, document_store=SimpleNamespace(delete=lambda k: True)).delete_account(victim)             # self-service is refused (nothing deleted)
    assert type(refused.value).__name__ == "SubscriptionResolutionRequired"
    summary = AccountDeletionService(sf, document_store=SimpleNamespace(delete=lambda k: True)).delete_account(victim, preserve_billing_reference=True)
    assert summary.user_row_remaining and not summary.sql_complete
    assert set(r.split(".")[0] for r in summary.residual) == set()                                # nothing outside the retained set is reported as residual
    with sf() as s:
        shell = s.get(P.User, victim)
        assert shell.email is None and shell.display_name is None and shell.status == P.ACCOUNT_STATUS_DELETION_REQUESTED
        raw = erasure.residual_references(s, victim)
        assert set(r.split(".")[0] for r in raw) <= set(erasure.RETAINED_FOR_BILLING)             # only the three billing tables still point at the shell
        assert not [k for k in raw if k.startswith(("candidate_", "interviews", "opportunities", "preparation_memories", "user_feedback"))]


def test_a_privacy_request_row_may_stay_while_its_job_runs_and_is_the_only_exception(sf):
    victim = _user(sf, "victim")
    with sf() as s:
        make_row(s.connection(), Base.metadata.tables["privacy_requests"], user_id=victim, subject_user_id=victim, request_type="deletion")
        s.commit()
    summary = AccountDeletionService(sf, retain_privacy_requests=True).delete_account(victim)
    assert summary.residual == {} and summary.sql_complete                                              # the request row is the one documented exception while its job runs
    with sf() as s:
        assert erasure.residual_references(s, victim, retain_requests=True) == {}
        assert set(erasure.residual_references(s, victim)) == {"privacy_requests.user_id", "privacy_requests.subject_user_id"}      # still linked until the job completes it
        assert s.scalar(select(P.PrivacyRequest.request_note)) is None


# ----------------------------------------------------------------------------------------------------------------- private files: fail closed, resumable
def _doc_with_file(sf, store: LocalDocumentStore, user_id: int, key: str) -> None:
    store.save(key, b"private bytes")
    with sf() as s:
        d = P.CandidateDocument(user_id=user_id, title="CV")
        s.add(d)
        s.flush()
        s.add(P.DocumentVersion(document_id=d.id, version=1, original_filename="cv.txt", mime_type="text/plain", size_bytes=13, storage_key=key, status="ready"))
        s.commit()


class _FlakyStore:
    def __init__(self, inner: LocalDocumentStore, fail_keys: set[str]) -> None:
        self.inner, self.fail_keys = inner, set(fail_keys)

    def delete(self, key: str) -> bool:
        if key in self.fail_keys:
            raise OSError("disk error at /secret/path")
        return self.inner.delete(key)


def test_a_file_that_cannot_be_deleted_aborts_the_whole_deletion_and_the_rerun_completes_it(sf, tmp_path):
    store = LocalDocumentStore(str(tmp_path / "docs"))
    uid, other = _user(sf, "victim"), _user(sf, "bystander")
    _doc_with_file(sf, store, uid, "aaaaaaaa11111111")
    _doc_with_file(sf, store, uid, "bbbbbbbb22222222")
    _doc_with_file(sf, store, other, "cccccccc33333333")
    flaky = _FlakyStore(store, {"bbbbbbbb22222222"})
    with pytest.raises(DeletionIncomplete) as exc:
        AccountDeletionService(sf, document_store=flaky).delete_account(uid)
    assert exc.value.category == "private_files" and "secret" not in str(exc.value) and "bbbbbbbb" not in str(exc.value)
    with sf() as s:                                                    # NOTHING was committed: the account and its rows are intact and re-runnable
        assert s.get(P.User, uid) is not None
        assert s.scalar(select(func.count()).select_from(P.CandidateDocument).where(P.CandidateDocument.user_id == uid)) == 2
    flaky.fail_keys.clear()
    summary = AccountDeletionService(sf, document_store=flaky).delete_account(uid)             # the same call, repeated: the first key is already gone and that is fine
    assert summary.sql_complete and summary.files_failed == 0
    assert not store.exists("aaaaaaaa11111111") and not store.exists("bbbbbbbb22222222")
    assert store.exists("cccccccc33333333")                                                     # another user's file is never touched
    with sf() as s:
        assert s.get(P.User, uid) is None and s.get(P.User, other) is not None


def test_without_a_store_unpurged_files_are_reported_never_claimed(sf):
    uid = _user(sf, "victim")
    with sf() as s:
        d = P.CandidateDocument(user_id=uid, title="CV")
        s.add(d)
        s.flush()
        s.add(P.DocumentVersion(document_id=d.id, version=1, original_filename="cv.txt", mime_type="text/plain", size_bytes=1, storage_key="dddddddd44444444", status="ready"))
        s.commit()
    summary = AccountDeletionService(sf).delete_account(uid)
    assert summary.files_failed == 1 and summary.files_purged == 0


def test_the_account_delete_route_answers_503_and_keeps_the_account_when_a_file_cannot_be_deleted(tmp_path):
    from fastapi.testclient import TestClient

    from src.api import dependencies as deps
    from tests._auth_factories import build_auth_app, cookies_for, login_token, register, verification_token

    app, repo, mail = build_auth_app()
    store = LocalDocumentStore(str(tmp_path / "docs"))
    app.dependency_overrides[deps.get_document_store] = lambda: _FlakyStore(store, {"eeeeeeee55555555"})
    with TestClient(app) as client:
        register(client, "route@example.com", "password123")
        client.post("/api/v1/auth/verify-email", json={"token": verification_token(mail)})
        token = login_token(client, "route@example.com", "password123")
        with repo.session_factory() as s:
            uid = s.scalar(select(P.User.id).where(P.User.email == "route@example.com"))
        _doc_with_file(repo.session_factory, store, uid, "eeeeeeee55555555")
        r = client.post("/api/v1/auth/account/delete", cookies=cookies_for(token))
        assert r.status_code == 503 and "secret" not in r.text and "eeeeeeee" not in r.text, r.text
        assert client.get("/api/v1/auth/me", cookies=cookies_for(token)).status_code == 200            # still signed in, account intact
        app.dependency_overrides[deps.get_document_store] = lambda: store
        assert client.post("/api/v1/auth/account/delete", cookies=cookies_for(token)).status_code == 200
        assert client.get("/api/v1/auth/me", cookies=cookies_for(token)).status_code == 401
        assert not store.exists("eeeeeeee55555555")


# ----------------------------------------------------------------------------------------------------------------- checkpoints and the ownership index
def test_account_deletion_purges_every_indexed_run_and_nothing_is_ever_listed_or_scanned(sf):
    victim, other = _user(sf, "victim"), _user(sf, "bystander")
    idx = PreparationRunIndex(sf)
    for r in ("run-a-0001", "run-a-0002"):
        idx.register(r, victim)
    idx.register("run-b-0001", other)
    agent = FakeAgent({"run-a-0001": str(victim), "run-a-0002": str(victim), "run-b-0001": str(other), "run-orphan-9": str(victim)})
    summary = AccountDeletionService(sf, agent_service=agent, preparation_index=idx).delete_account(victim)
    assert summary.checkpoints_purged == 2 and summary.sql_complete
    assert sorted(agent.purged) == ["run-a-0001", "run-a-0002"] and "run-b-0001" in agent.runs               # another user's run is untouched
    assert "run-orphan-9" in agent.runs                                                                      # never indexed, never referenced: not found, documented limit
    assert not hasattr(agent, "list_runs") and not hasattr(agent, "scan") and agent.lookups == []
    assert idx.run_ids_for_owner(victim) == [] and idx.run_ids_for_owner(other) == ["run-b-0001"]


def test_a_failed_purge_is_reported_residual_and_kept_for_the_retry(sf):
    victim = _user(sf, "victim")
    idx = PreparationRunIndex(sf)
    idx.register("run-f-0001", victim)
    agent = FakeAgent({"run-f-0001": str(victim)})
    agent.fail = True
    summary = AccountDeletionService(sf, agent_service=agent, preparation_index=idx).delete_account(victim)
    assert summary.checkpoints_failed == 1 and summary.purge_failed_run_ids == ["run-f-0001"]
    assert summary.residual == {"preparation_runs.owner_user_id": 1} and not summary.sql_complete
    assert idx.pending_purge(victim) == [("run-f-0001", victim)]


def test_orphaned_runs_of_a_deleted_account_are_found_by_one_indexed_join_and_swept_without_a_scan(sf):
    victim, alive = _user(sf, "victim"), _user(sf, "alive")
    idx = PreparationRunIndex(sf)
    for r in ("run-o-0001", "run-o-0002"):
        idx.register(r, victim)
    idx.register("run-alive-01", alive)
    agent = FakeAgent({"run-o-0001": str(victim), "run-o-0002": str(victim), "run-alive-01": str(alive), "run-never-indexed": str(victim)})
    with sf() as s:                                                                                    # simulate a crash right after the SQL commit: the user is gone, the index rows remain
        s.execute(text("delete from users where id = :i"), {"i": victim})
        s.commit()
    assert sorted(r for r, _ in idx.orphaned_runs()) == ["run-o-0001", "run-o-0002"]
    dry = sweep_orphaned_runs(idx, agent)                                                              # dry-run: counts only, nothing purged
    assert dry == {"orphaned": 2, "purged": 0, "failed": 0, "executed": False} and agent.purged == []
    agent.fail = True
    bad = sweep_orphaned_runs(idx, agent, execute=True)
    assert bad["failed"] == 2 and bad["purged"] == 0 and idx.run_ids_for_owner(victim) == ["run-o-0001", "run-o-0002"]           # rows kept for the next sweep
    agent.fail = False
    ok = sweep_orphaned_runs(idx, agent, execute=True)
    assert ok["purged"] == 2 and idx.orphaned_runs() == [] and sorted(agent.purged) == ["run-o-0001", "run-o-0002"]
    assert "run-alive-01" in agent.runs and "run-never-indexed" in agent.runs                          # live users' runs untouched; the never-indexed run is not discoverable
    assert sweep_orphaned_runs(idx, agent, execute=True)["orphaned"] == 0                              # idempotent
    assert sweep_orphaned_runs(idx, None, execute=True) == {"orphaned": 0, "purged": 0, "failed": 0, "executed": True}


def test_the_sweep_without_a_checkpoint_store_fails_closed_and_keeps_the_rows(sf):
    victim = _user(sf, "victim")
    idx = PreparationRunIndex(sf)
    idx.register("run-n-00001", victim)
    with sf() as s:
        s.execute(text("delete from users where id = :i"), {"i": victim})
        s.commit()
    out = sweep_orphaned_runs(idx, None, execute=True)
    assert out["failed"] == 1 and out["purged"] == 0 and idx.owner_of("run-n-00001") == victim


def test_the_sweep_cli_is_dry_run_by_default_and_prints_counts_only(sf, tmp_path, capsys, monkeypatch):
    import importlib.util

    db = tmp_path / "cli.db"
    eng = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(eng)
    cli_sf = make_session_factory(eng)
    idx = PreparationRunIndex(cli_sf)
    idx.register("run-cli-0001", 987654)                                                               # an owner that does not exist
    spec = importlib.util.spec_from_file_location("privacy_sweep_orphan_runs", ROOT / "scripts" / "privacy_sweep_orphan_runs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(["--database-url", f"sqlite:///{db}"]) == 0
    out = capsys.readouterr().out
    assert "orphaned runs found: 1" in out and "dry-run" in out and "run-cli-0001" not in out and "987654" not in out
    assert idx.owner_of("run-cli-0001") == 987654                                                      # nothing changed


# ----------------------------------------------------------------------------------------------------------------- the privacy-request deletion job
def _job_ctx(sf, agent):
    from src.privacy.runtime import PrivacyRuntime

    rt = PrivacyRuntime(session_factory=sf, adapter=agent, doc_store=SimpleNamespace(delete=lambda k: True), audit_repository=None, jobs=None)
    return SimpleNamespace(services=SimpleNamespace(privacy=rt), created_by_user_id=None)


def _deletion_request(sf, subject: int) -> str:
    from src.privacy.requests import PrivacyRequestService

    view = PrivacyRequestService(sf).create(subject, "deletion", None, source="candidate_portal")
    with sf() as s:
        s.execute(text("update privacy_requests set status = 'in_progress' where public_id = :p"), {"p": view["public_id"]})
        s.commit()
    return view["public_id"]


def test_the_deletion_job_purges_runs_left_in_any_state_by_a_crash_and_only_then_completes(sf):
    from src.jobs.registry import RetryableJobError
    from src.privacy.runtime import run_account_delete

    subject = _user(sf, "subject")
    idx = PreparationRunIndex(sf)
    idx.register("run-c-0001", subject)                                                                 # state "started": what a crash after the SQL commit leaves behind
    idx.register("run-c-0002", subject)
    idx.mark("run-c-0002", "ready")
    agent = FakeAgent({"run-c-0001": str(subject), "run-c-0002": str(subject)})
    rid = _deletion_request(sf, subject)
    agent.fail = True
    with pytest.raises(RetryableJobError):
        run_account_delete(rid, _job_ctx(sf, agent))                                                   # store down: NOT completed
    with sf() as s:
        assert s.scalar(select(P.PrivacyRequest.status).where(P.PrivacyRequest.public_id == rid)) == "in_progress"
    agent.fail = False
    run_account_delete(rid, _job_ctx(sf, agent))                                                       # the retry finds the "started"/"ready" rows too
    with sf() as s:
        row = s.scalar(select(P.PrivacyRequest).where(P.PrivacyRequest.public_id == rid))
        assert row.status == "completed" and row.result_category == "deletion_performed" and row.subject_user_id is None
        assert s.get(P.User, subject) is None
    assert sorted(agent.purged) == ["run-c-0001", "run-c-0002"] and idx.run_ids_for_owner(subject) == []
    run_account_delete(rid, _job_ctx(sf, agent))                                                       # replay after completion: a no-op


def test_the_deletion_job_never_completes_while_any_reference_to_the_account_remains(sf, monkeypatch):
    from src.jobs.registry import RetryableJobError
    from src.privacy import erasure as E
    from src.privacy.runtime import run_account_delete

    subject = _user(sf, "subject")
    rid = _deletion_request(sf, subject)
    monkeypatch.setattr(E, "residual_for_user", lambda *a, **k: {"some_table.user_id": 1})
    with pytest.raises(RetryableJobError):
        run_account_delete(rid, _job_ctx(sf, FakeAgent()))
    with sf() as s:
        assert s.scalar(select(P.PrivacyRequest.status).where(P.PrivacyRequest.public_id == rid)) == "in_progress"      # not recorded as completed


def test_a_private_file_failure_makes_the_job_retry_instead_of_completing(sf, tmp_path):
    from src.jobs.registry import RetryableJobError
    from src.privacy.runtime import PrivacyRuntime, run_account_delete

    store = LocalDocumentStore(str(tmp_path / "docs"))
    subject = _user(sf, "subject")
    _doc_with_file(sf, store, subject, "ffffffff66666666")
    rid = _deletion_request(sf, subject)
    flaky = _FlakyStore(store, {"ffffffff66666666"})
    ctx = SimpleNamespace(services=SimpleNamespace(privacy=PrivacyRuntime(session_factory=sf, adapter=FakeAgent(), doc_store=flaky)), created_by_user_id=None)
    with pytest.raises(RetryableJobError):
        run_account_delete(rid, ctx)
    flaky.fail_keys.clear()
    run_account_delete(rid, ctx)
    with sf() as s:
        assert s.scalar(select(P.PrivacyRequest.status).where(P.PrivacyRequest.public_id == rid)) == "completed" and s.get(P.User, subject) is None
    assert not store.exists("ffffffff66666666")


# ----------------------------------------------------------------------------------------------------------------- preparation-chat ownership index audit
def test_audit_every_production_agent_service_is_built_with_the_ownership_index():
    """Static audit: where the durable agent service is constructed for the product (the API dependency), the run index is passed; the offline evaluators and demos
    that build one construct in-memory services only (no durable checkpoint, nothing to index)."""
    import ast

    allowed_without_index = {"src/agent/eval.py", "src/agent/multi_agent_eval.py", "src/p10e/live_runs.py", "scripts/demo_offline_journey.py"}
    with_index = set()
    without = set()
    for base in ("src", "scripts"):
        for path in sorted((ROOT / base).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
                name = call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", "")
                if name == "AgentApplicationService":
                    (with_index if any(k.arg == "run_index" for k in call.keywords) else without).add(str(path.relative_to(ROOT)))
    assert "src/api/dependencies.py" in with_index
    assert without <= allowed_without_index, sorted(without - allowed_without_index)


def test_audit_the_privacy_package_and_the_agent_service_never_call_a_list_or_scan_api_on_the_saver():
    """Nothing may enumerate the checkpoint store. The only saver operations allowed are get_tuple (one thread) and delete_thread (one thread)."""
    import re

    banned = re.compile(r"\.(list|alist|search|scan|iterate|get_all)\s*\(")
    saver_calls = re.compile(r"(checkpointer|_cp|saver)\.(\w+)\(")
    offenders = []
    allowed = {"get_tuple", "delete_thread", "put", "get", "setup", "put_writes", "get_next_version"}
    for rel in ("src/privacy/preparation.py", "src/privacy/runtime.py", "src/application/account_deletion_service.py", "src/application/agent_service.py"):
        text_ = (ROOT / rel).read_text(encoding="utf-8")
        for m in saver_calls.finditer(text_):
            if m.group(2) not in allowed:
                offenders.append((rel, m.group(0)))
        for m in banned.finditer(text_):
            line = text_[max(0, text_.rfind("\n", 0, m.start())):text_.find("\n", m.start())]
            if "checkpointer" in line or "_cp" in line or "saver" in line:
                offenders.append((rel, line.strip()))
    assert offenders == [], offenders


def test_the_checkpoint_adapter_exposes_no_enumeration_and_the_index_coverage_states_its_limit(sf):
    from src.privacy.preparation import CheckpointAdapter

    public = {n for n in dir(CheckpointAdapter) if not n.startswith("_")}
    assert public == {"supported", "owner_of", "purge_run", "delete_run"}
    cov = PreparationRunIndex(sf).coverage()
    assert "cannot be discovered" in cov["note"]


def test_new_runs_are_indexed_before_the_checkpoint_exists_and_a_failed_index_write_creates_none(sf):
    from src.agent.errors import AgentError
    from src.agent.models import AgentRunRequest
    from src.application.agent_service import AgentApplicationService

    uid = _user(sf, "owner")
    idx = PreparationRunIndex(sf)
    order: list[str] = []
    real_register = idx.register
    idx.register = lambda *a, **k: (order.append("index"), real_register(*a, **k))[1]
    svc = AgentApplicationService(model_factory=lambda p=None: (_ for _ in ()).throw(RuntimeError("no model")), career_service=object(), run_index=idx,
                                  checkpoint_durable=False)
    real_invoke = svc._graph.invoke
    svc._graph.invoke = lambda *a, **k: (order.append("checkpoint"), real_invoke(*a, **k))[1]
    try:
        svc.run(AgentRunRequest(goal="x", user_id=str(uid)))
    except AgentError:
        pass
    assert order[:2] == ["index", "checkpoint"]
    assert idx.run_ids_for_owner(uid) and idx.run_ids_for_owner(uid + 1) == []
    idx.register = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down"))
    seen: list[str] = []
    svc._graph.invoke = lambda *a, **k: seen.append("checkpoint")
    with pytest.raises(AgentError):
        svc.run(AgentRunRequest(goal="y", user_id=str(uid)))
    assert seen == []                                                                                      # fail closed: no untracked checkpoint was created
