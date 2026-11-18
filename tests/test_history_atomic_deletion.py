"""F1-P2: real SQLite/PG16 transactions, synthetic identities and no provider I/O."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from src import persistence as P
from src.api import dependencies as deps
from src.api.main import create_app
from src.application import history_service
from src.application.sharing_service import SharingNotFoundError, SharingService
from src.auth_repository import AuditRepository
from src.interview.session_codec import encode_session_data
from src.interview.session_repository import DurableInterviewSessionStore, SessionConflictError
from src.repository import InterviewRepository
from src.workspace_repository import WorkspaceRepository
from tests.test_history_idempotency import _completed_session

TABLES = ('users', 'candidate_documents', 'opportunities', 'interview_sessions', 'interviews',
          'questions', 'answers', 'reports', 'workspaces', 'workspace_memberships', 'share_grants', 'audit_events')
STATE_TABLES = ('interview_sessions', 'interviews', 'questions', 'answers', 'reports', 'share_grants', 'audit_events')


class Fixture:
    def __init__(self, url):
        self.url = url
        self.engine = P.make_engine(url)
        P.Base.metadata.create_all(self.engine, tables=[P.Base.metadata.tables[n] for n in TABLES])
        self.sf = P.make_session_factory(self.engine)
        self.repo = InterviewRepository(self.sf)
        self.store = DurableInterviewSessionStore(self.sf)
        self.ws = WorkspaceRepository(self.sf)
        self.audit = AuditRepository(self.sf)
        self.sharing = SharingService(workspaces=self.ws, audit=self.audit,
            owner_verifiers={'interview_report': lambda rid, uid: self.repo.get_interview(uid, int(rid)) is not None},
            owner_loaders={'interview_report': lambda rid, uid: self.repo.get_interview(uid, int(rid))})
        with self.sf() as db:
            a, b = P.User(subject='synthetic-owner', provider='test'), P.User(subject='synthetic-foreign', provider='test')
            db.add_all([a, b]); db.flush()
            self.owner, self.foreign = a.id, b.id
            ws = P.Workspace(owner_user_id=a.id, name='Synthetic', status='active')
            db.add(ws); db.flush(); self.workspace = ws.id
            db.add_all([P.WorkspaceMembership(workspace_id=ws.id, user_id=uid, role=role, status='active')
                        for uid, role in [(a.id, 'owner'), (b.id, 'member')]])
            db.commit()
        self.sid, self.rid = self.seed(self.owner, 'target')
        self.keep_sid, self.keep_rid = self.seed(self.owner, 'keeper')
        self.foreign_sid, self.foreign_rid = self.seed(self.foreign, 'foreign')
        self.before = self.snapshot()
        app = create_app()
        def identity(x_fixture_user: str | None = Header(default=None)):
            if x_fixture_user not in (str(self.owner), str(self.foreign)):
                raise HTTPException(401, 'Authentication required.')
            return int(x_fixture_user)
        def override(value):
            return lambda: value
        for dependency, value in [(deps.get_repository, self.repo), (deps.get_session_store, self.store),
                                  (deps.get_sharing_service, self.sharing), (deps.get_audit_repository, self.audit)]:
            app.dependency_overrides[dependency] = override(value)
        app.dependency_overrides[deps.get_current_user_id] = identity
        self.client = TestClient(app, raise_server_exceptions=False)

    def seed(self, owner, key):
        sid, _ = self.store.create_or_get(owner, key)
        data = _completed_session().data
        rid = self.repo.save_interview(owner, history_service.build_interview_payload(data), source_session_id=sid)
        data.saved_report_id = rid
        with self.sf() as db:
            db.execute(update(P.InterviewSession).where(P.InterviewSession.session_id == sid)
                       .values(status=data.state.value, state_payload=encode_session_data(data)))
            db.add(P.ShareGrant(owner_user_id=owner, workspace_id=self.workspace,
                                resource_type='interview_report', resource_id=str(rid), permission='view', status='active'))
            db.commit()
        return sid, rid

    def snapshot(self):
        with self.sf() as db:
            return {name: sorted([repr(tuple(row)) for row in db.execute(select(P.Base.metadata.tables[name]))])
                    for name in STATE_TABLES}

    def delete(self, user=None, report=None):
        return self.client.delete(f'/api/v1/history/interviews/{self.rid if report is None else report}',
                                  headers={'X-Fixture-User': str(self.owner if user is None else user)})

    def assert_success(self, *, prior_audits=None):
        if prior_audits is None:
            prior_audits = self.before["audit_events"]
        with self.sf() as db:
            assert db.get(P.Interview, self.rid) is None
            assert db.get(P.InterviewSession, self.sid) is None
            for rid in (self.keep_rid, self.foreign_rid):
                assert db.get(P.Interview, rid) is not None
            for sid in (self.keep_sid, self.foreign_sid):
                assert db.get(P.InterviewSession, sid) is not None
            assert db.scalar(select(func.count()).select_from(P.Question)) == 2
            assert db.scalar(select(func.count()).select_from(P.Answer)) == 2
            assert db.scalar(select(func.count()).select_from(P.Report)) == 2
            grants = db.scalars(select(P.ShareGrant)).all()
            assert len(grants) == 3
            assert all(g.status == ('revoked' if g.resource_id == str(self.rid) else 'active') for g in grants)
            events = db.scalars(select(P.AuditEvent)).all()
            assert len(events) == len(prior_audits) + 1
            deletions = [ev for ev in events if ev.event_type == 'interview.deleted']
            assert len(deletions) == 1
            ev = deletions[0]
            assert (ev.event_type, ev.actor_user_id, ev.target_type, ev.target_id, ev.result, ev.context) == (
                'interview.deleted', self.owner, 'interview', str(self.rid), 'success', None)
            assert uuid.UUID(hex=ev.request_id).hex == ev.request_id and len(ev.request_id) == 32
        assert self.store.find_idempotent_session(self.owner, 'target') is None
        after = self.snapshot()
        assert set(prior_audits).issubset(after['audit_events'])
        # Every unrelated row remains byte-for-byte equivalent as a typed SQL projection.
        for table in STATE_TABLES[:-1]:
            if table == 'share_grants':
                assert set(after[table]) & set(self.before[table]) == set(self.before[table]) - {
                    row for row in self.before[table] if f"'{self.rid}', 'view'" in row}
            else:
                assert set(after[table]).issubset(set(self.before[table]))
        with pytest.raises(SharingNotFoundError):
            self.sharing.resolve_shared_resource(user_id=self.foreign, resource_type='interview_report', resource_id=str(self.rid))
        assert self.delete().status_code == 404
        with pytest.raises(SessionConflictError):
            self.repo.save_interview_from_runtime(self.owner, {}, source_session_id=self.sid)
        with self.sf() as db:
            assert db.scalar(select(func.count()).select_from(P.AuditEvent)) == len(prior_audits) + 1
            assert db.scalar(select(func.count()).select_from(P.Interview)) == 2

    def close(self):
        self.client.close(); self.engine.dispose()


@pytest.fixture(params=['sqlite', 'postgresql'])
def f(request, tmp_path):
    if request.param == 'sqlite':
        fixture = Fixture(f'sqlite:///{tmp_path / "history.sqlite"}')
        try: yield fixture
        finally: fixture.close()
    else:
        admin = os.environ.get('P5B_PG_ADMIN_URL')
        if not admin:
            pytest.skip('Operation-owned PostgreSQL 16 fixture not supplied')
        import psycopg
        from psycopg import sql
        name = 'p5b_history_' + uuid.uuid4().hex
        with psycopg.connect(admin.replace('postgresql+psycopg://', 'postgresql://'), autocommit=True) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        fixture = None
        try:
            fixture = Fixture(admin.rsplit('/', 1)[0] + '/' + name)
            yield fixture
        finally:
            if fixture: fixture.close()
            with psycopg.connect(admin.replace('postgresql+psycopg://', 'postgresql://'), autocommit=True) as db:
                db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))


def test_normal_owned_delete(f):
    assert f.sharing.resolve_shared_resource(user_id=f.foreign, resource_type='interview_report', resource_id=str(f.rid))
    r = f.delete(); assert r.status_code == 200 and r.json() == {'deleted': True}
    f.assert_success()


@pytest.mark.parametrize('source', ['absent', 'legacy'])
def test_missing_or_legacy_runtime(f, source):
    f.store.discard(f.sid, f.owner)
    if source == 'legacy':
        with f.sf() as db:
            db.execute(update(P.Interview).where(P.Interview.id == f.rid).values(source_session_id=None)); db.commit()
    f.before = f.snapshot()
    assert f.delete().status_code == 200
    f.assert_success()


def test_foreign_unknown_and_anonymous(f):
    before = f.snapshot()
    assert f.delete(user=f.foreign).status_code == 404
    assert f.delete(report=999999).status_code == 404
    assert f.client.delete(f'/api/v1/history/interviews/{f.rid}').status_code == 401
    assert f.snapshot() == before


@pytest.mark.parametrize('phase', ['active', 'expired', 'dispatch', 'expired_dispatch', 'hold', 'legacy'])
def test_lease_and_hold_contract(f, phase):
    token = f.store._claim_lease(f.sid, f.owner, 'report')
    with f.sf() as db:
        row = db.get(P.InterviewSession, f.sid)
        if phase in ('expired', 'expired_dispatch', 'legacy'):
            row.operation_leased_at = P.utcnow() - timedelta(days=1)
        if phase in ('dispatch', 'expired_dispatch'): row.active_operation = 'create@2:dispatch'
        if phase == 'hold': row.active_operation = 'create@2:hold'
        if phase == 'legacy': row.active_operation = 'create'
        db.commit()
    before = f.snapshot()
    response = f.delete()
    if phase == 'expired':
        assert response.status_code == 200; f.before = before; f.assert_success()
    else:
        assert response.status_code == 409
        assert response.json()['error']['code'] == (
            'practice_setup_outcome_uncertain' if phase in ('expired_dispatch', 'hold', 'legacy')
            else 'interview_operation_in_progress' if phase == 'dispatch' else 'conflict')
        assert f.snapshot() == before
        if phase == 'active':
            f.store._release_lease(f.sid, f.owner, token)
            assert f.delete().status_code == 200; f.assert_success()


@pytest.mark.parametrize('stage', ['runtime', 'history', 'shares', 'audit', 'commit'])
def test_failure_rolls_back_every_effect(f, monkeypatch, stage):
    before = f.snapshot()
    if stage == 'commit':
        monkeypatch.setattr(f.sf.class_, 'commit', lambda db: (_ for _ in ()).throw(RuntimeError('SYNTHETIC_PRIVATE_FAILURE')))
    else:
        obj, name = {'runtime': (f.store, 'discard_in_transaction'), 'history': (f.repo, 'delete_interview_in_transaction'),
                     'shares': (f.sharing, 'invalidate_in_transaction'), 'audit': (f.audit, 'record_interview_deletion_in_transaction')}[stage]
        real = getattr(obj, name)
        def fail(*args, **kwargs):
            real(*args, **kwargs)
            raise RuntimeError('SYNTHETIC_PRIVATE_FAILURE')
        monkeypatch.setattr(obj, name, fail)
    response = f.delete()
    assert response.status_code == 503 and response.json()['error']['code'] == 'service_unavailable'
    assert 'SYNTHETIC_PRIVATE_FAILURE' not in response.text and 'Traceback' not in response.text
    assert f.snapshot() == before


def test_lost_commit_ack_is_confirmed_without_replay(f, monkeypatch):
    commit = f.sf.class_.commit
    calls = []
    def lost(db):
        calls.append(True); commit(db); raise RuntimeError('SYNTHETIC_LOST_ACK')
    monkeypatch.setattr(f.sf.class_, 'commit', lost)
    assert f.delete().status_code == 200 and len(calls) == 1
    f.assert_success()


def test_conditional_delete_does_not_accept_changed_version(f, monkeypatch):
    before = f.snapshot(); real = f.store.discard_in_transaction
    def changed(db, row, owner):
        db.execute(update(P.InterviewSession).where(P.InterviewSession.session_id == row.session_id)
                   .values(version=row.version + 1).execution_options(synchronize_session=False))
        real(db, row, owner)
    monkeypatch.setattr(f.store, 'discard_in_transaction', changed)
    assert f.delete().status_code == 409
    assert f.snapshot() == before


def test_two_concurrent_deletions_emit_one_audit(f):
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda _: f.delete().status_code, range(2)))
    assert codes.count(200) == 1 and all(code in (200, 404, 409) for code in codes)
    f.assert_success()


@pytest.mark.parametrize('mode', ['lease', 'version'])
def test_two_process_change_after_observation_is_not_silently_accepted(f, monkeypatch, mode):
    original = f.store.deletion_identity
    changed = []
    def pause(db, sid):
        observed = original(db, sid)
        if not changed:
            # A genuinely separate interpreter/connection commits after the SELECT
            # and before deletion begins its write transaction.
            child = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--writer',
                                    f.url, sid, str(f.owner), mode], capture_output=True, text=True, timeout=20)
            assert child.returncode == 0, 'synthetic writer did not complete'
            changed.append(f.snapshot())
        return observed
    monkeypatch.setattr(f.store, 'deletion_identity', pause)
    assert f.delete().status_code == 409
    assert f.snapshot() == changed[0]
    monkeypatch.setattr(f.store, 'deletion_identity', original)
    if mode == 'lease':
        with f.sf() as db: token = db.get(P.InterviewSession, f.sid).active_operation
        f.store._release_lease(f.sid, f.owner, token)
    assert f.delete().status_code == 200; f.assert_success()


def test_cross_engine_dependency_is_refused_before_writes(f):
    before = f.snapshot(); other = P.make_engine(f.url)
    try:
        f.sharing._ws = WorkspaceRepository(P.make_session_factory(other))
        assert f.delete().status_code == 503
        assert f.snapshot() == before
    finally: other.dispose()


def test_foreign_runtime_binding_is_not_deleted(f):
    with f.sf() as db:
        db.execute(update(P.Interview).where(P.Interview.id == f.rid).values(source_session_id=f.foreign_sid)); db.commit()
    before = f.snapshot()
    assert f.delete().status_code == 409
    assert f.snapshot() == before


def test_stale_share_verification_cannot_reactivate_deleted_report(f):
    assert f.delete().status_code == 200
    # The upstream verifier may already have run, so test the repository write boundary itself.
    assert f.ws.create_share(owner_user_id=f.owner, workspace_id=f.workspace,
                             resource_type='interview_report', resource_id=str(f.rid), permission='view') is None
    f.assert_success()


@pytest.mark.parametrize('writer', ['runtime_save', 'share'])
def test_racing_save_or_share_cannot_resurrect_deleted_content(f, writer):
    from threading import Barrier

    barrier = Barrier(2)
    def delete():
        barrier.wait(timeout=10)
        return f.delete().status_code
    def write():
        barrier.wait(timeout=10)
        if writer == 'share':
            return f.ws.create_share(owner_user_id=f.owner, workspace_id=f.workspace,
                                     resource_type='interview_report', resource_id=str(f.rid), permission='view')
        try:
            return f.repo.save_interview_from_runtime(f.owner, {}, source_session_id=f.sid)
        except SessionConflictError:
            return 'source_deleted'
    with ThreadPoolExecutor(max_workers=2) as pool:
        deletion, writing = pool.submit(delete), pool.submit(write)
        assert deletion.result(timeout=20) == 200
        writing.result(timeout=20)
    f.assert_success()


def test_lost_ack_with_unavailable_readback_never_claims_success(f, monkeypatch):
    from src.application import history_deletion

    commit = f.sf.class_.commit
    def lost(db):
        commit(db)
        raise RuntimeError('SYNTHETIC_LOST_ACK')
    monkeypatch.setattr(f.sf.class_, 'commit', lost)
    monkeypatch.setattr(history_deletion, '_confirmed_commit', lambda *args: False)
    response = f.delete()
    assert response.status_code == 503 and response.json()['error']['code'] == 'service_unavailable'
    # The commit really happened; there is no retry, rollback or duplicate audit.
    f.assert_success()


if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == '--writer':
    import tests.conftest  # noqa: F401 - retain database guards in the independent process
    url, sid, owner, mode = sys.argv[2:]
    engine = P.make_engine(url); store = DurableInterviewSessionStore(P.make_session_factory(engine))
    try:
        if mode == 'lease': store._claim_lease(sid, int(owner), 'report')
        else:
            with store.mutate(sid, int(owner)): pass
        print(json.dumps({'committed': True}))
    finally: engine.dispose()
