"""Workspace submission evidence through the real dependency factories, using synthetic senders."""
from __future__ import annotations

import logging

import pytest
from sqlalchemy import select

from src import persistence as P
from src.api.dependencies import get_email_sender
from src.mail.sender import SendResult
from src.mail.service import EmailAttemptRepository, EmailService
from tests._workspaces_04b_world import World


class FakeSender:
    def __init__(self, outcome):
        self.outcome = outcome
        self.messages = []

    def send_detailed(self, message):
        self.messages.append(message)
        if self.outcome == 'exception':
            raise RuntimeError('sensitive synthetic provider error')
        if self.outcome == 'rejected':
            return SendResult('failed', 'synthetic', 'message_rejected')
        if self.outcome == 'captured':
            return SendResult('captured', 'synthetic')
        if self.outcome == 'not_configured':
            return SendResult('not_configured', 'synthetic', 'provider_not_configured')
        if self.outcome == 'unknown':
            return SendResult('delivery_unknown', 'synthetic', 'delivery_unknown')
        return SendResult('provider_accepted', 'synthetic')

    def send(self, message):
        return self.send_detailed(message).accepted


@pytest.fixture
def world():
    w = World()
    try:
        w.user('alice')
        w.user('bob')
        wid = w.workspace('alice')
        w.join('alice', wid, 'bob')
        yield w, wid
    finally:
        w.close()


def _attempts(w, kind):
    with w.repo.session_factory() as s:
        return [(r.message_type, r.provider, r.status, r.failure_category, r.locale, r.request_id, r.user_id, r.delivery_state)
                for r in s.scalars(select(P.EmailAttempt).where(P.EmailAttempt.message_type == kind).order_by(P.EmailAttempt.id)).all()]


@pytest.mark.parametrize('kind', ['workspace_invitation', 'ownership_transfer'])
@pytest.mark.parametrize('outcome,status,category', [
    ('accepted', 'provider_accepted', None),
    ('captured', 'captured', None),
    ('not_configured', 'not_configured', 'provider_not_configured'),
    ('unknown', 'delivery_unknown', 'delivery_unknown'),
    ('rejected', 'failed', 'message_rejected'),
    ('exception', 'failed', 'provider_unavailable'),
])
def test_one_safe_attempt_per_authorized_send(world, kind, outcome, status, category, caplog):
    w, wid = world
    fake = FakeSender(outcome)
    w.app.dependency_overrides[get_email_sender] = lambda: fake
    before = _attempts(w, kind)
    caplog.set_level(logging.INFO)
    if kind == 'workspace_invitation':
        response = w.post('alice', f'/workspaces/{wid}/invite', {'email':'new-person@example.test'})
        private = 'new-person@example.test'
    else:
        response = w.propose('alice', wid, 'bob', name='Alpha')
        private = w.u['bob']['email']
    assert response.status_code == 200
    assert response.json()['email_delivery'] == ('submitted' if outcome in ('accepted', 'captured') else 'not_submitted')
    assert len(fake.messages) == 1
    after = _attempts(w, kind)
    assert len(after) == len(before) + 1
    assert after[-1][:5] == (kind, 'unknown' if outcome == 'exception' else 'synthetic', status, category, 'en')
    assert after[-1][-1] is None  # Provider acceptance is not verified delivery.
    assert private not in repr(after) and private not in caplog.text
    assert fake.messages[0].subject not in repr(after) and fake.messages[0].body not in repr(after)
    assert fake.messages[0].subject not in caplog.text and fake.messages[0].body not in caplog.text
    assert 'sensitive synthetic provider error' not in caplog.text


@pytest.mark.parametrize('kind', ['workspace_invitation', 'ownership_transfer'])
def test_attempt_storage_failure_does_not_change_business_result(world, kind, monkeypatch, caplog):
    w, wid = world
    fake = FakeSender('accepted')
    w.app.dependency_overrides[get_email_sender] = lambda: fake
    original = EmailAttemptRepository.record
    def storage_fails(self, **kwargs):
        self._sf = lambda: (_ for _ in ()).throw(RuntimeError('private database details'))
        return original(self, **kwargs)
    monkeypatch.setattr(EmailAttemptRepository, 'record', storage_fails)
    before = _attempts(w, kind)
    if kind == 'workspace_invitation':
        response = w.post('alice', f'/workspaces/{wid}/invite', {'email':'failed-write@example.test'})
    else:
        response = w.propose('alice', wid, 'bob', name='Alpha')
    assert response.status_code == 200 and response.json()['email_delivery'] == 'submitted'
    assert len(fake.messages) == 1 and _attempts(w, kind) == before
    assert 'email attempt record failed' in caplog.text
    assert 'private database details' not in caplog.text and 'failed-write@example.test' not in caplog.text


def test_unauthorized_user_cannot_cause_a_send(world):
    w, wid = world
    fake = FakeSender('accepted')
    w.app.dependency_overrides[get_email_sender] = lambda: fake
    before = _attempts(w, 'workspace_invitation')
    response = w.post('bob', f'/workspaces/{wid}/invite', {'email':'other@example.test'})
    assert response.status_code == 403
    assert not fake.messages and _attempts(w, 'workspace_invitation') == before


@pytest.mark.parametrize('kind', ['workspace_invitation', 'ownership_transfer'])
def test_existing_email_service_is_not_wrapped_or_double_recorded(world, kind):
    w, wid = world
    fake = FakeSender('accepted')
    wrapped = EmailService(fake, EmailAttemptRepository(w.repo.session_factory))
    w.app.dependency_overrides[get_email_sender] = lambda: wrapped
    before = _attempts(w, kind)
    if kind == 'workspace_invitation':
        response = w.post('alice', f'/workspaces/{wid}/invite', {'email':'existing-service@example.test'})
    else:
        response = w.propose('alice', wid, 'bob', name='Alpha')
    assert response.status_code == 200 and response.json()['email_delivery'] == 'submitted'
    assert len(fake.messages) == 1 and len(_attempts(w, kind)) == len(before) + 1
