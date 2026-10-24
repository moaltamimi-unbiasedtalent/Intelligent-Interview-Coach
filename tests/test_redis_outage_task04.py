"""Configuration, privacy and outage observations; no external stores/providers."""
import json
import sys

import pytest
from fastapi import HTTPException

from src.api import rate_limit as R
from tests._fake_redis import FakeRedis


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    for key in list(__import__('os').environ):
        if key.startswith(('RATE_LIMIT_', 'REDIS_')):
            monkeypatch.delenv(key, raising=False)
    yield
    R.reset_rate_limiter(R.InMemoryRateLimiter())


def secure(monkeypatch):
    monkeypatch.setenv('API_ENV', 'staging')
    monkeypatch.setenv('RATE_LIMIT_BACKEND', 'redis')
    monkeypatch.setenv('RATE_LIMIT_NAMESPACE', 'ask4mo:rl:staging:v1:')
    monkeypatch.setenv('RATE_LIMIT_KEY_SECRET', 'test-key-' * 8)
    monkeypatch.setenv('REDIS_URL', 'rediss://limiter:' + 'x' * 40 + '@redis.invalid:6379/0')
    monkeypatch.setattr('importlib.util.find_spec', lambda *_a, **_k: object())


@pytest.mark.parametrize('field,value', [('REDIS_URL', ''), ('RATE_LIMIT_KEY_SECRET', ''), ('RATE_LIMIT_NAMESPACE', ''),
    ('REDIS_URL', 'redis://limiter:' + 'x'*40 + '@public.invalid/0'), ('REDIS_URL', 'rediss://public.invalid/0'),
    ('REDIS_URL', 'rediss://limiter:secret@host/0?socket_timeout=0'), ('RATE_LIMIT_BACKEND', 'in_memory')])
def test_hosted_unsafe_selection_refuses_without_a_secret_projection(monkeypatch, field, value):
    secure(monkeypatch)
    monkeypatch.setenv(field, value)
    assert R.redis_configuration_errors(hosted=True)
    with pytest.raises(R.RateLimitConfigurationError) as exc:
        R.build_rate_limiter()
    assert 'secret' not in str(exc.value) and 'redis.invalid' not in str(exc.value)


def test_missing_dependency_and_failed_construction_cannot_fall_back_in_hosted(monkeypatch):
    secure(monkeypatch)
    monkeypatch.setitem(sys.modules, 'redis', None)
    with pytest.raises(R.RateLimitConfigurationError):
        R.build_rate_limiter()
    monkeypatch.delitem(sys.modules, 'redis')
    def fail(*_a, **_kw):
        raise ValueError('private-URL-and-password')
    monkeypatch.setattr(R, 'make_redis_client', fail)
    with pytest.raises(R.RateLimitConfigurationError, match='^shared_rate_limit_configuration_invalid$'):
        R.build_rate_limiter()


def test_required_shared_cannot_be_replaced_by_dev_memory(monkeypatch):
    monkeypatch.setenv('RATE_LIMIT_SHARED_REQUIRED', 'true')
    with pytest.raises(R.RateLimitConfigurationError):
        R.build_rate_limiter()


def test_missing_password_file_refuses_without_exposing_its_path(monkeypatch):
    secure(monkeypatch)
    monkeypatch.setenv('REDIS_PASSWORD_FILE', '/no/private/secret/file')
    with pytest.raises(R.RateLimitConfigurationError) as exc:
        R.build_rate_limiter()
    assert '/no/' not in str(exc.value)


def test_private_keys_separate_identities_buckets_namespaces_and_secrets():
    store = FakeRedis()
    a = R.RedisRateLimiter(store, key_secret='a'*32)
    b = R.RedisRateLimiter(store, prefix='ask4mo:rl:other:', key_secret='a'*32)
    c = R.RedisRateLimiter(store, key_secret='b'*32)
    keys = [a.store_key('b', key) for key in ['user:1', 'user:2', '203.0.113.2', 'somebody@example.invalid']]
    keys += [b.store_key('b', 'user:1'), c.store_key('b', 'user:1'), a.store_key('other', 'user:1')]
    assert len(set(keys)) == 7
    assert all(len(k.rsplit(':', 1)[-1]) == 64 for k in keys)
    assert all('user:' not in k and '203.0' not in k and '@' not in k for k in keys)


def test_status_reports_unverified_local_deny_and_recovery_without_identifiers(caplog):
    store = FakeRedis()
    lim = R.RedisRateLimiter(store)
    R.reset_rate_limiter(lim)
    assert R.limiter_status()['state'] == 'configured_unverified'
    assert not R.shared_store_active()
    local = R.RateLimitPolicy('l', 1, 30, 'user')
    deny = R.RateLimitPolicy('d', 1, 30, 'user', 'deny')
    assert lim.hit('b', 'private@example.invalid', local).allowed
    assert R.limiter_status()['state'] == 'shared' and R.shared_store_active()
    store.fail = ConnectionError('private@example.invalid/credential')
    assert lim.hit('b', 'private@example.invalid', local).allowed
    assert R.limiter_status()['state'] == 'degraded_local' and not R.shared_store_active()
    assert not lim.hit('b', 'private@example.invalid', deny).allowed
    assert R.limiter_status()['state'] == 'fail_closed'
    store.fail = None
    assert lim.hit('b', 'another', local).allowed
    status = R.limiter_status()
    assert status['state'] == 'recovered_shared' and status['recoveries'] == 1
    assert status['local_fallbacks'] == status['fail_closed_refusals'] == 1
    assert 'private@' not in json.dumps(status) + caplog.text


def test_fail_closed_http_is_503_and_limit_http_is_429(monkeypatch):
    store = FakeRedis()
    lim = R.RedisRateLimiter(store)
    monkeypatch.setitem(R.POLICIES, 'test_strict', R.RateLimitPolicy('test_strict', 1, 30, 'user', 'deny'))
    R.enforce('test_strict', 'u', limiter=lim)
    with pytest.raises(HTTPException) as exc:
        R.enforce('test_strict', 'u', limiter=lim)
    assert exc.value.status_code == 429 and int(exc.value.headers['Retry-After']) >= 1
    store.fail = OSError('secret')
    with pytest.raises(HTTPException) as exc:
        R.enforce('test_strict', 'u', limiter=lim)
    assert exc.value.status_code == 503 and exc.value.headers['Retry-After'] == '5'
    assert 'secret' not in str(exc.value.detail)


def test_fallback_bounds_memory_without_evicting_live_counters():
    now = [0]
    lim = R.InMemoryRateLimiter(clock=lambda: now[0], max_keys=2)
    policy = R.RateLimitPolicy('p', 1, 10, 'ip')
    assert lim.hit('p', 'a', policy).allowed and lim.hit('p', 'b', policy).allowed
    assert not lim.hit('p', 'c', policy).allowed
    assert not lim.hit('p', 'a', policy).allowed
    now[0] = 11
    assert lim.hit('p', 'c', policy).allowed


def test_policies_are_unchanged_and_invalid_failure_modes_refuse():
    assert len(R.POLICIES) == 37 and {p.on_store_failure for p in R.POLICIES.values()} == {'local'}
    with pytest.raises(ValueError):
        R.RateLimitPolicy('bad', 1, 10, 'user', 'unlimited')


def test_safe_http_headers_are_allowlisted_without_forwarding_arbitrary_values():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.api.exception_handlers import register_exception_handlers
    app=FastAPI()
    register_exception_handlers(app)
    @app.get('/safe')
    def safe():
        raise HTTPException(429,'Safe message',headers={'Retry-After':'5','X-Private':'secret-sentinel'})
    @app.get('/bad')
    def bad():
        raise HTTPException(429,'Safe message',headers={'Retry-After':'secret-sentinel','X-Rate-Limit-State':'secret-sentinel'})
    with TestClient(app) as client:
        response=client.get('/safe')
        assert response.headers['Retry-After']=='5' and 'X-Private' not in response.headers
        response=client.get('/bad')
        assert 'Retry-After' not in response.headers and 'X-Rate-Limit-State' not in response.headers


def test_a_separately_constructed_client_cannot_misreport_the_installed_limiter():
    R.reset_rate_limiter(R.InMemoryRateLimiter())
    uninstalled=R.RedisRateLimiter(FakeRedis())
    assert uninstalled.hit('b','synthetic',R.RateLimitPolicy('p',1,10,'user')).allowed
    assert not R.shared_store_active() and R.limiter_status()['backend']=='in_memory'
    R.reset_rate_limiter(uninstalled)
    assert R.shared_store_active() and R.limiter_status()['effectively_distributed']


def test_required_shared_refuses_a_secret_source_shadowing_the_reviewed_profile(monkeypatch):
    from src.core import secrets
    secure(monkeypatch)
    monkeypatch.setenv('RATE_LIMIT_SHARED_REQUIRED','true')
    monkeypatch.setattr(secrets,'read_setting',lambda name:'rediss://hidden-store.invalid/0' if name=='REDIS_URL' else 'k'*40)
    assert R.redis_configuration_errors(hosted=True)
    with pytest.raises(R.RateLimitConfigurationError,match='^shared_rate_limit_configuration_invalid$'):
        R.build_rate_limiter()


def test_late_limiter_configuration_refusal_is_safe_503_not_an_internal_500():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.api.exception_handlers import register_exception_handlers
    app=FastAPI()
    register_exception_handlers(app)
    @app.get('/protected')
    def protected():
        raise R.RateLimitConfigurationError('private-runtime-source-detail')
    with TestClient(app) as client:
        response=client.get('/protected')
        assert response.status_code==503 and response.json()['error']['code']=='protection_unavailable'
        assert 'private-runtime-source-detail' not in response.text


@pytest.mark.parametrize('mutation', ['unpinned','wrong_version','base','other_extra','celery','sentry-sdk','prometheus-client','hvac','stripe_unpinned','malformed'])
def test_infrastructure_guard_refuses_every_unapproved_dependency_shape(mutation):
    from pathlib import Path
    from scripts.eval_admin_foundation import infrastructure_dependencies_allowed
    text=(Path(__file__).resolve().parents[1]/'pyproject.toml').read_text()
    assert infrastructure_dependencies_allowed(text)
    if mutation=='unpinned': text=text.replace('redis==8.1.0','redis>=8')
    elif mutation=='wrong_version': text=text.replace('redis==8.1.0','redis==8.0.0')
    elif mutation=='base': text=text.replace('dependencies = [','dependencies = ["redis==8.1.0",',1)
    elif mutation=='other_extra': text=text.replace('dev = [','dev = ["redis==8.1.0",',1)
    elif mutation=='stripe_unpinned': text=text.replace('stripe>=16,<17','stripe>=16')
    elif mutation=='malformed': text+='\nnot valid toml!'
    else: text=text.replace('dependencies = [',f'dependencies = ["{mutation}==1.0",',1)
    assert not infrastructure_dependencies_allowed(text)
