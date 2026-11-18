"""F1 request-time consent binds an opaque report incarnation, including legacy rows."""
from __future__ import annotations

import json
import select as ready
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import func, select, text, update

from src import persistence as P
from src.application import history_service
from src.application.sharing_service import SharingNotFoundError, SharingService
from src.auth_repository import AuditRepository
from src.application.errors import ConflictError
from src.interview.report_generation import EVENT, current_generation
from src.repository import InterviewRepository
from src.workspace_repository import WorkspaceRepository
from tests.test_history_atomic_deletion import f as atomic_fixture
from tests.test_history_idempotency import _completed_session

f = atomic_fixture


def legacy_report(f):
    with f.sf() as db:
        row = P.Interview(user_id=f.owner, configuration={'target_role': 'Synthetic legacy'}, status='completed')
        db.add(row); db.flush()
        db.add(P.Report(interview_id=row.id, report={'summary': 'SYNTHETIC_LEGACY_CONTENT'}))
        db.commit()
        return row.id


def generation(f, rid):
    return f.repo.get_interview(f.owner, rid, include_share_generation=True)['share_generation']


def post(f, rid, token):
    return f.client.post('/api/v1/shares', headers={'X-Fixture-User': str(f.owner)}, json={
        'workspace_id': f.workspace, 'resource_type': 'interview_report', 'resource_id': str(rid),
        'consent': True, 'expected_report_generation': token})


def test_legacy_selection_is_durable_metadata_only_and_concurrent(f):
    rid = legacy_report(f)
    before = f.snapshot()
    # Ordinary repository reads and missing-token shares must not enroll legacy data.
    assert 'share_generation' not in f.repo.get_interview(f.owner, rid)
    assert all('share_generation' not in r for r in f.repo.list_interviews(f.owner))
    assert post(f, rid, None).status_code == 409
    assert post(f, rid, '0' * 32).status_code == 409
    assert f.snapshot() == before
    gate = Barrier(2)
    def select_legacy(_):
        gate.wait(timeout=10)
        return generation(f, rid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        tokens = list(pool.map(select_legacy, range(2)))
    assert len(set(tokens)) == 1 and len(tokens[0]) == 32
    engine = P.make_engine(f.url)
    try:
        restarted = InterviewRepository(P.make_session_factory(engine))
        assert restarted.get_interview(f.owner, rid, include_share_generation=True)['share_generation'] == tokens[0]
    finally:
        engine.dispose()
    after = f.snapshot()
    for table in before:
        if table != 'audit_events':
            assert after[table] == before[table]
    assert set(before['audit_events']).issubset(after['audit_events'])
    assert len(after['audit_events']) == len(before['audit_events']) + 1
    with f.sf() as db:
        event = db.scalar(select(P.AuditEvent).where(P.AuditEvent.target_id == str(rid), P.AuditEvent.event_type == EVENT))
        assert (event.actor_user_id, event.context, event.request_id, event.result) == (f.owner, None, tokens[0], 'success')
    assert post(f, rid, tokens[0]).status_code == 200


def test_idempotent_save_keeps_the_original_generation(f):
    before = f.snapshot()
    token = generation(f, f.rid)
    repeated = f.repo.save_interview_from_runtime(f.owner,
        history_service.build_interview_payload(_completed_session().data), source_session_id=f.sid)
    assert repeated == f.rid and generation(f, f.rid) == token
    assert f.snapshot() == before


def test_selection_api_preserves_owner_and_same_generation(f):
    rid = legacy_report(f)
    before = f.snapshot()
    assert f.client.get(f'/api/v1/history/interviews/{rid}', headers={'X-Fixture-User': str(f.foreign)}).status_code == 404
    assert f.snapshot() == before
    headers = {'X-Fixture-User': str(f.owner)}
    detail = f.client.get(f'/api/v1/history/interviews/{rid}', headers=headers)
    assert detail.status_code == 200
    token = detail.json()['interview']['share_generation']
    listing = f.client.get('/api/v1/history/interviews', headers=headers)
    assert listing.status_code == 200
    assert next(r for r in listing.json()['interviews'] if r['id'] == rid)['share_generation'] == token
    assert post(f, rid, token).status_code == 200


@pytest.mark.parametrize('token', [None, '', 'x' * 32, '0' * 32, 'A' * 32, 123])
def test_missing_malformed_or_wrong_generation_never_creates_a_grant(f, token):
    rid = legacy_report(f)
    actual = generation(f, rid)
    before = f.snapshot()
    response = post(f, rid, token)
    assert response.status_code == (409 if token is None or token == '0' * 32 else 422)
    assert f.snapshot() == before
    assert actual not in response.text and 'SYNTHETIC_LEGACY_CONTENT' not in response.text


def test_generation_of_another_owned_report_cannot_authorize_this_report(f):
    before = f.snapshot()
    assert post(f, f.rid, generation(f, f.keep_rid)).status_code == 409
    assert f.snapshot() == before


@pytest.mark.parametrize('legacy', [False, True])
def test_prelock_request_refuses_reused_id_even_with_identical_timestamps(f, legacy):
    if legacy:
        rid = legacy_report(f)
    else:
        _, rid = f.seed(f.owner, 'last-consented')
    token = generation(f, rid)
    with f.sf() as db:
        old_time = db.get(P.Interview, rid).created_at
    child = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--prelock',
        f.url, str(f.owner), str(f.workspace), str(rid), token], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    def receive():
        assert ready.select([child.stdout], [], [], 20)[0], 'synthetic worker timed out'
        line = child.stdout.readline()
        assert line, 'synthetic worker ended early'
        return json.loads(line)
    try:
        assert receive() == {'selected_request_paused_before_lock': True}
        assert f.delete(report=rid).status_code == 200
        if f.engine.dialect.name == 'postgresql':
            # Test-only allocator reset proves exact numeric reuse on both engines.
            with f.sf() as db:
                db.execute(text("SELECT setval(pg_get_serial_sequence('interviews','id'), :previous, true)"), {'previous': rid - 1})
                db.commit()
        payload = history_service.build_interview_payload(_completed_session().data)
        replacement = f.repo.save_interview(f.owner, payload)
        assert replacement == rid
        with f.sf() as db:
            db.execute(update(P.Interview).where(P.Interview.id == replacement).values(created_at=old_time))
            db.commit()
        fresh = generation(f, replacement)
        assert fresh != token
        before = f.snapshot()
        child.stdin.write('resume\n'); child.stdin.flush()
        assert receive() == {'refused_stale_selection': True}
        assert child.wait(timeout=10) == 0
        assert f.snapshot() == before
        with f.sf() as db:
            assert not db.scalar(select(func.count()).select_from(P.ShareGrant).where(
                P.ShareGrant.resource_id == str(rid), P.ShareGrant.status == 'active'))
            assert current_generation(db, f.owner, rid) == fresh
        with pytest.raises(SharingNotFoundError):
            f.sharing.resolve_shared_resource(user_id=f.foreign, resource_type='interview_report', resource_id=str(rid))
        assert post(f, rid, token).status_code == 409
        assert post(f, rid, fresh).status_code == 200  # new deliberate selection/consent succeeds
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)


def _worker(url, owner, workspace, rid, token):
    import tests.conftest  # noqa: F401 - enforce database isolation in the subprocess
    engine = P.make_engine(url)
    sf = P.make_session_factory(engine)
    repo, ws = InterviewRepository(sf), WorkspaceRepository(sf)
    service = SharingService(workspaces=ws, audit=AuditRepository(sf),
        owner_verifiers={'interview_report': lambda r, u: repo.get_interview(u, int(r)) is not None})
    original = ws.report_share_transaction
    @contextmanager
    def pause(**kwargs):
        print(json.dumps({'selected_request_paused_before_lock': True}), flush=True)
        assert sys.stdin.readline().strip() == 'resume'
        with original(**kwargs) as db:
            yield db
    ws.report_share_transaction = pause
    try:
        try:
            service.share(user_id=int(owner), workspace_id=int(workspace), resource_type='interview_report',
                          resource_id=rid, consent=True, expected_report_generation=token)
        except ConflictError:
            print(json.dumps({'refused_stale_selection': True}), flush=True)
        else:
            print(json.dumps({'refused_stale_selection': False}), flush=True)
    finally:
        engine.dispose()


if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == '--prelock':
    _worker(*sys.argv[2:])
