"""F1: consent locks the exact report; deletion receipts identify their own attempt."""
from __future__ import annotations

import json
import sqlite3
import select as ready
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
import time

import pytest
from sqlalchemy import event, func, select, text, update

from src import persistence as P
from src.application import history_deletion, history_service
from src.application.sharing_service import SharingService
from src.auth_repository import AuditRepository
from src.repository import InterviewRepository
from src.workspace_repository import WorkspaceRepository
from tests.test_history_atomic_deletion import f as atomic_fixture
from tests.test_history_idempotency import _completed_session

f = atomic_fixture  # Reuse the real, parametrized SQLite/PostgreSQL fixture.


def _receive(child):
    assert ready.select([child.stdout], [], [], 20)[0], 'synthetic worker timed out'
    line = child.stdout.readline()
    assert line, 'synthetic worker ended before its observation'
    return json.loads(line)


def _send(child, command):
    child.stdin.write(command + '\n'); child.stdin.flush()


@pytest.mark.parametrize('legacy', [False, True])
def test_report_identity_stays_locked_through_consent_and_commit(f, legacy):
    sid, rid = f.seed(f.owner, 'last-report')
    if legacy:
        with f.sf() as db:
            db.execute(update(P.Interview).where(P.Interview.id == rid).values(source_session_id=None)); db.commit()
        f.store.discard(sid, f.owner)
    child = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--share',
                              f.url, str(f.owner), str(f.workspace), str(rid)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    attempted = Event()
    listening = False
    waiting_pid = []
    def at_lock(connection, cursor, statement, parameters, context, many):
        if statement == 'BEGIN IMMEDIATE' or ('interviews' in statement and 'FOR UPDATE' in statement):
            if f.engine.dialect.name == 'postgresql':
                waiting_pid.append(connection.connection.driver_connection.info.backend_pid)
            attempted.set()
    try:
        assert _receive(child) == {'verified_original_report': True}
        if f.engine.dialect.name == 'sqlite':
            # Verify the physical write lock, not just a paused Python callback.
            with sqlite3.connect(f.url.removeprefix('sqlite:///'), timeout=0) as probe:
                with pytest.raises(sqlite3.OperationalError, match='locked'):
                    probe.execute('BEGIN IMMEDIATE')
        event.listen(f.engine, 'before_cursor_execute', at_lock)
        listening = True
        with ThreadPoolExecutor(max_workers=1) as pool:
            deletion = pool.submit(f.delete, report=rid)
            try:
                assert attempted.wait(10)
                # The writer is paused after verification, with the exact old report
                # still locked. Deletion cannot replace that row under the consent.
                assert not deletion.done()
                if f.engine.dialect.name == 'postgresql':
                    deadline = time.monotonic() + 5
                    while True:
                        with f.sf() as db:
                            waiting = db.scalar(text('SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid'),
                                                {'pid': waiting_pid[-1]})
                        if waiting == 'Lock':
                            break
                        assert time.monotonic() < deadline, 'PostgreSQL did not retain the report lock'
                        time.sleep(0.01)
            finally:
                _send(child, 'commit')
            assert _receive(child) == {'shared_original_report': True}
            assert child.wait(timeout=10) == 0
            assert deletion.result(timeout=20).status_code == 200
        new_sid = f.store.create(f.owner)
        payload = history_service.build_interview_payload(_completed_session().data)
        payload['report']['report']['performance_summary'] = 'UNSHARED_SYNTHETIC_REPORT'
        replacement = f.repo.save_interview_from_runtime(f.owner, payload, source_session_id=new_sid)
        if f.engine.dialect.name == 'sqlite':
            assert replacement == rid, 'must exercise actual SQLite id reuse'
        with f.sf() as db:
            assert not db.scalar(select(func.count()).select_from(P.ShareGrant).where(
                P.ShareGrant.resource_id == str(rid), P.ShareGrant.status == 'active'))
        assert f.sharing.can_view(user_id=f.foreign, resource_type='interview_report', resource_id=str(replacement)) is None
        # A direct writer has no verified, still-open report transaction.
        assert f.ws.create_share(owner_user_id=f.owner, workspace_id=f.workspace,
                                  resource_type='interview_report', resource_id=str(replacement), permission='view') is None
        # A new explicit consent can share the new report normally.
        created = f.sharing.share(user_id=f.owner, workspace_id=f.workspace,
                                  resource_type='interview_report', resource_id=str(replacement), consent=True,
                                  expected_report_generation=f.repo.get_interview(f.owner, replacement, include_share_generation=True)["share_generation"])
        assert created['status'] == 'active'
        assert f.sharing.can_view(user_id=f.foreign, resource_type='interview_report', resource_id=str(replacement)) == f.owner
    finally:
        if listening:
            event.remove(f.engine, 'before_cursor_execute', at_lock)
        if child.poll() is None: child.kill()
        child.wait(timeout=10)


def test_closed_report_transaction_cannot_be_reused(f):
    generation = f.repo.get_interview(f.owner, f.rid, include_share_generation=True)["share_generation"]
    with f.ws.report_share_transaction(owner_user_id=f.owner, resource_id=str(f.rid), expected_report_generation=generation) as transaction:
        assert transaction is not None
        assert f.ws.create_share(owner_user_id=f.owner, workspace_id=f.workspace,
                                 resource_type='interview_report', resource_id=str(f.rid), permission='view',
                                 report_transaction=transaction, expected_report_generation=generation)
    before = f.snapshot()
    assert f.ws.create_share(owner_user_id=f.owner, workspace_id=f.workspace,
                             resource_type='interview_report', resource_id=str(f.rid), permission='view',
                             report_transaction=transaction, expected_report_generation=generation) is None
    # Reopening the Session must not revive its old consent or row lock.
    with transaction.begin():
        assert f.ws.create_share(owner_user_id=f.owner, workspace_id=f.workspace,
                                 resource_type='interview_report', resource_id=str(f.rid), permission='view',
                                 report_transaction=transaction, expected_report_generation=generation) is None
    assert f.snapshot() == before


@pytest.mark.parametrize('alias', ['leading_zero', 'plus', 'whitespace'])
def test_numeric_report_aliases_use_the_canonical_revocable_identity(f, alias):
    rid = {'leading_zero': '000' + str(f.rid), 'plus': '+' + str(f.rid),
           'whitespace': ' ' + str(f.rid) + ' '}[alias]
    result = f.sharing.share(user_id=f.owner, workspace_id=f.workspace,
                             resource_type='interview_report', resource_id=rid, consent=True,
                             expected_report_generation=f.repo.get_interview(f.owner, f.rid, include_share_generation=True)['share_generation'])
    grant = f.ws.get_share(result['share_id'])
    assert grant['resource_id'] == str(f.rid)
    prior_audits = f.snapshot()['audit_events']
    assert len(prior_audits) == len(f.before['audit_events']) + 1
    assert f.delete().status_code == 200
    f.assert_success(prior_audits=prior_audits)


def test_other_attempt_with_reused_audit_id_never_confirms_rollback(f, monkeypatch):
    commit = f.sf.class_.commit
    real_check = history_deletion._confirmed_commit
    first = []
    observed = []
    def precommit_failure(db):
        if not first:
            receipt = db.scalar(select(P.AuditEvent).where(P.AuditEvent.event_type == 'interview.deleted'))
            first.append((receipt.id, receipt.request_id))
            raise RuntimeError('SYNTHETIC_PRECOMMIT_FAILURE')
        return commit(db)
    def competing_request(sf, user, report, source, audit_id, attempt_id):
        assert f.delete().status_code == 200
        with f.sf() as db:
            receipt = db.scalar(select(P.AuditEvent).where(P.AuditEvent.event_type == 'interview.deleted'))
            other_id, other_attempt = receipt.id, receipt.request_id
        assert attempt_id == first[0][1] and other_attempt != attempt_id
        if f.engine.dialect.name == 'sqlite': assert other_id == audit_id
        confirmed = real_check(sf, user, report, source, audit_id, attempt_id)
        observed.append(confirmed)
        return confirmed
    monkeypatch.setattr(f.sf.class_, 'commit', precommit_failure)
    monkeypatch.setattr(history_deletion, '_confirmed_commit', competing_request)
    response = f.delete()
    assert response.status_code == 503 and response.json()['error']['code'] == 'service_unavailable'
    assert observed == [False]
    f.assert_success()


@pytest.mark.parametrize('field,value', [
    ('request_id', None), ('request_id', ''), ('request_id', '0' * 32),
    ('result', 'failure'), ('target_id', '999999'), ('actor_user_id', None),
])
def test_mismatched_or_missing_attempt_evidence_remains_uncertain(f, monkeypatch, field, value):
    commit = f.sf.class_.commit
    def malformed_receipt(db, *, actor_user_id, interview_id, attempt_id):
        # Inject the malformed receipt BEFORE insertion. Existing append-only
        # database protections remain enabled and no committed audit is edited.
        values = dict(event_type='interview.deleted', actor_user_id=actor_user_id,
                      target_type='interview', target_id=str(interview_id), result='success', request_id=attempt_id)
        values[field] = value
        receipt = P.AuditEvent(**values)
        db.add(receipt); db.flush()
        return receipt.id
    def lost_ack(db):
        commit(db)
        raise RuntimeError('SYNTHETIC_LOST_ACK')
    monkeypatch.setattr(f.audit, 'record_interview_deletion_in_transaction', malformed_receipt)
    monkeypatch.setattr(f.sf.class_, 'commit', lost_ack)
    response = f.delete()
    assert response.status_code == 503 and response.json()['error']['code'] == 'service_unavailable'
    assert 'SYNTHETIC_LOST_ACK' not in response.text
    with f.sf() as db:
        assert db.get(P.Interview, f.rid) is None and db.get(P.InterviewSession, f.sid) is None
        assert db.scalar(select(func.count()).select_from(P.AuditEvent)) == len(f.before['audit_events']) + 1
    assert f.delete().status_code == 404


def test_verifier_refusal_releases_report_transaction_without_grant_changes(f):
    f.sharing._verifiers['interview_report'] = lambda *args: False
    before = f.snapshot()
    from src.application.sharing_service import SharingPermissionError
    with pytest.raises(SharingPermissionError):
        f.sharing.share(user_id=f.owner, workspace_id=f.workspace,
                        resource_type='interview_report', resource_id=str(f.rid), consent=True,
                        expected_report_generation=f.repo.get_interview(f.owner, f.rid, include_share_generation=True)['share_generation'])
    assert f.snapshot() == before
    assert f.delete().status_code == 200


def _worker(url, owner, workspace, rid):
    import tests.conftest  # noqa: F401 - keep database isolation in the worker
    engine = P.make_engine(url); sf = P.make_session_factory(engine)
    repo, ws = InterviewRepository(sf), WorkspaceRepository(sf)
    sharing = SharingService(workspaces=ws, audit=AuditRepository(sf),
        owner_verifiers={'interview_report': lambda r, u: repo.get_interview(u, int(r)) is not None})
    generation = repo.get_interview(int(owner), int(rid), include_share_generation=True)["share_generation"]
    original = ws.create_share
    def paused(**kwargs):
        print(json.dumps({'verified_original_report': True}), flush=True)
        assert sys.stdin.readline().strip() == 'commit'
        return original(**kwargs)
    ws.create_share = paused
    try:
        result = sharing.share(user_id=int(owner), workspace_id=int(workspace),
                               resource_type='interview_report', resource_id=rid, consent=True, expected_report_generation=generation)
        print(json.dumps({'shared_original_report': result['status'] == 'active'}), flush=True)
    finally: engine.dispose()


if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == '--share':
    _worker(*sys.argv[2:])
