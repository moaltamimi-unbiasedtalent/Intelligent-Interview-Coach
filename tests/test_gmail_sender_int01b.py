"""Synthetic Gmail transport and application integration; no live provider calls."""
import base64
import json
import logging
from email import message_from_bytes

import httpx
import pytest
from sqlalchemy import select

from src.api.dependencies import get_email_sender
from src.mail import GmailEmailSender, NotConfiguredEmailSender, build_email_sender
from src.mail.sender import EmailMessage
from src.persistence import EmailAttempt
from tests.test_email_identity_w12_4c import World as AuthWorld, PW
from tests._workspaces_04b_world import World as WorkspaceWorld


class Tokens:
    def access_token(self, *, timeout):
        assert timeout == 10.0
        return 'synthetic-token-DO-NOT-LOG'


def sender(handler):
    return GmailEmailSender(sender_email='sender@example.test', token_source=Tokens(), transport=httpx.MockTransport(handler))


@pytest.mark.parametrize('response,status,reason', [
    (httpx.Response(200, json={'id': 'synthetic-private-response'}), 'provider_accepted', None),
    (httpx.Response(400), 'failed', 'message_rejected'),
    (httpx.Response(401), 'failed', 'provider_auth_failed'),
    (httpx.Response(403), 'failed', 'provider_auth_failed'),
    (httpx.Response(403, json={'error': {'errors': [{'reason': 'userRateLimitExceeded'}]}}), 'failed', 'rate_limited'),
    (httpx.Response(429), 'failed', 'rate_limited'),
    (httpx.Response(503), 'delivery_unknown', 'delivery_unknown'),
    (httpx.Response(302, headers={'location':'https://example.invalid'}), 'delivery_unknown', 'delivery_unknown'),
    (httpx.ReadTimeout('private error'), 'delivery_unknown', 'delivery_unknown'),
    (httpx.WriteTimeout('private error'), 'delivery_unknown', 'delivery_unknown'),
    (httpx.ConnectError('private error'), 'failed', 'provider_unavailable'),
])
def test_one_submission_and_bounded_outcome(response, status, reason, caplog):
    requests = []
    def handle(request):
        requests.append(request)
        if isinstance(response, Exception): raise response
        return response
    caplog.set_level(logging.DEBUG)
    result = sender(handle).send_detailed(EmailMessage('recipient@example.test','private subject','private body token=canary','password_reset'))
    assert (result.status, result.failure_category, result.provider_message_ref) == (status, reason, None)
    assert len(requests) == 1 and requests[0].url.path == '/gmail/v1/users/me/messages/send'
    mime = message_from_bytes(base64.urlsafe_b64decode(json.loads(requests[0].content)['raw']))
    assert mime['To'] == 'recipient@example.test' and mime['From'] == 'sender@example.test'
    for secret in ('recipient@example.test', 'private subject', 'private body', 'synthetic-token', 'private error', 'synthetic-private-response'):
        assert secret not in caplog.text and secret not in repr(result)


def test_missing_or_broken_token_never_contacts_provider():
    class Missing:
        def access_token(self, *, timeout): raise ValueError('secret canary')
    s = GmailEmailSender(sender_email='sender@example.test', token_source=Missing(), transport=httpx.MockTransport(lambda request: pytest.fail('network called')))
    assert s.send_detailed(EmailMessage('a@example.test','s','b','password_reset')).status == 'not_configured'


@pytest.mark.parametrize('environment', ['production', 'development'])
def test_factory_never_activates_gmail_without_separate_configuration(monkeypatch, environment):
    monkeypatch.setenv('API_ENV', environment)
    monkeypatch.setenv('EMAIL_PROVIDER', 'gmail')
    assert isinstance(build_email_sender(), NotConfiguredEmailSender)


def test_auth_registration_and_reset_persist_gmail_attempts(monkeypatch):
    monkeypatch.setenv('APP_BASE_URL','https://app.example.test')
    requests=[]
    s=sender(lambda r: requests.append(r) or httpx.Response(200, json={'id':'private'}))
    w=AuthWorld(s)
    try:
        assert w.c.post('/api/v1/auth/register',json={'email':'synthetic@example.test','password':PW}).status_code == 201
        assert w.c.post('/api/v1/auth/forgot-password',json={'email':'synthetic@example.test'}).status_code == 200
        rows=w.attempts()
        assert [(x.message_type,x.provider,x.status,x.delivery_state) for x in rows] == [('email_verification','gmail','provider_accepted',None),('password_reset','gmail','provider_accepted',None)]
        assert len(requests)==2
    finally:
        w.close()


@pytest.mark.parametrize('kind', ['workspace_invitation','ownership_transfer'])
def test_workspace_application_sends_and_persists_attempt(kind):
    requests=[]
    s=sender(lambda r: requests.append(r) or httpx.Response(200))
    w=WorkspaceWorld()
    try:
        w.user('alice');w.user('bob');wid=w.workspace('alice');w.join('alice',wid,'bob')
        w.app.dependency_overrides[get_email_sender]=lambda:s
        with w.repo.session_factory() as db:
            before = len(db.scalars(select(EmailAttempt).where(EmailAttempt.message_type == kind)).all())
        result = w.post('alice', f'/workspaces/{wid}/invite', {'email':'new@example.test'}) if kind == 'workspace_invitation' else w.propose('alice',wid,'bob',name='Alpha')
        assert result.status_code == 200 and result.json()['email_delivery'] == 'submitted'
        with w.repo.session_factory() as db:
            rows=db.scalars(select(EmailAttempt).where(EmailAttempt.message_type == kind)).all()
            assert len(rows)==before+1 and rows[-1].provider=='gmail' and rows[-1].status=='provider_accepted' and rows[-1].delivery_state is None
        assert len(requests)==1
    finally:
        w.close()
