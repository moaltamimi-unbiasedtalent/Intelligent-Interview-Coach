"""Mandatory CI real Redis qualification. Opt-in locally; synthetic data only.

Owns one digest-pinned container and network. Never connects to TEST_REDIS_URL,
a private .env, hosted Redis, candidate databases, mail or AI providers.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import uuid

import pytest

from src.api import rate_limit as R

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'redis:8.2.9-alpine@sha256:5f2e6a105b2a8cc721911d5d29aadb032c25fe55b43e829e3d03413753ff47c2'
pytestmark = pytest.mark.skipif(os.environ.get('RUN_DISPOSABLE_REDIS_TESTS') != '1', reason='explicit disposable Redis opt-in required')


class SyntheticRedis(dict):
    def __repr__(self):
        return '<disposable synthetic Redis fixture>'


def docker(*args):
    p = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, 'disposable Docker operation failed'  # never print credentials/config
    return p.stdout.strip()


@pytest.fixture(scope='module')
def real(tmp_path_factory):
    import redis  # mandatory when opted in: missing package is an error, never a skip
    directory = tmp_path_factory.mktemp('redis-task04')
    suffix = uuid.uuid4().hex[:12]
    name, network = 'ask4mo-redis-test-' + suffix, 'ask4mo-redis-net-' + suffix
    password = secrets.token_urlsafe(32)
    credential = directory / 'password'
    credential.write_text(password)
    credential.chmod(0o444)  # synthetic disposable credential, readable by non-root UID 999
    namespace = 'ask4mo:rl:test' + suffix + ':'
    # Add an operator identity ONLY to the disposable copy, for TTL/ACL inspection
    # and legacy 05D cleanup. Production script has no such identity/permissions.
    script = (ROOT / 'deploy/scripts/redis-start.sh').read_text().replace('unset password',
        '''printf 'user testoperator on >%s ~* +@all\\n' "$password" >> /tmp/ask4mo-redis.acl\nunset password''')
    start = directory / 'start.sh'
    start.write_text(script)
    start.chmod(0o444)
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        host_port = reservation.getsockname()[1]
    docker('network', 'create', network)  # test-only loopback access; production profile has no published port
    try:
        docker('run', '-d', '--name', name, '--network', network, '--user', '999:1000', '--read-only',
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp:rw,mode=1777', '--tmpfs', '/data:rw,uid=999,gid=1000,mode=0700',
               '-p', f'127.0.0.1:{host_port}:6379', '-v', f'{credential}:/run/secrets/redis_password:ro', '-v', f'{start}:/start.sh:ro',
               '-e', 'RATE_LIMIT_NAMESPACE=' + namespace, '--entrypoint', '/bin/sh', IMAGE, '/start.sh')
        info = json.loads(docker('inspect', name))[0]
        for _ in range(30):
            if info['State']['Running'] and '6379/tcp' in info['NetworkSettings']['Ports']:
                break
            time.sleep(0.1)
            info = json.loads(docker('inspect', name))[0]
        if not info['State']['Running'] or '6379/tcp' not in info['NetworkSettings']['Ports']:
            logs = docker('logs', name).replace(password, '[redacted]')
            pytest.fail('disposable startup: ' + json.dumps({'state': info['State'], 'ports': info['NetworkSettings']['Ports'], 'binding': info['HostConfig']['PortBindings']}) + '; ' + logs[-1200:])
        port = info['NetworkSettings']['Ports']['6379/tcp'][0]['HostPort']
        def client(user='limiter', supplied=password):
            return redis.Redis(host='127.0.0.1', port=int(port), username=user, password=supplied, socket_timeout=0.3,
                               socket_connect_timeout=0.3, retry=redis.retry.Retry(redis.backoff.NoBackoff(), 0), protocol=2)
        admin = client('testoperator')
        for _ in range(50):
            try:
                if admin.ping():
                    break
            except redis.RedisError:
                time.sleep(0.1)
        else:
            pytest.fail('disposable Redis did not become ready')
        assert admin.info()['redis_version'] == '8.2.9'
        yield SyntheticRedis({'name': name, 'network': network, 'client': client, 'admin': admin, 'port': int(port), 'password': password,
               'namespace': namespace, 'directory': directory, 'credential': credential, 'start': start})
    finally:
        docker('rm', '-f', name)
        docker('network', 'rm', network)


def limiter(real, tag, *, user='limiter', prefix=None, clock=time.time):
    client=R.make_redis_client(f"redis://{user}@127.0.0.1:{real['port']}/0",password=real['password'])
    return R.RedisRateLimiter(client, prefix=prefix or real['namespace'] + tag + ':', key_secret='synthetic-key-' * 4, clock=clock)


def test_real_concurrent_replicas_share_a_global_ceiling(real):
    a, b = limiter(real, 'threads'), limiter(real, 'threads')
    policy = R.RateLimitPolicy('p', 20, 60, 'user')
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda n: (a if n % 2 else b).hit('b', 'user:1', policy).allowed, range(120)))
    assert sum(results) == 20
    assert not a.degraded and not b.degraded and a.local_fallbacks==b.local_fallbacks==0
    assert a.hit('b', 'user:2', policy).allowed


WORKER = r'''
import concurrent.futures,json,os
os.environ['PYTHON_DOTENV_DISABLED']='1'
os.environ['ASK4MO_PROVIDER_MODE']='offline'
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api import rate_limit as R
c=R.make_redis_client('redis://limiter@127.0.0.1:'+os.environ['SYNTHETIC_REDIS_PORT']+'/0',password=os.environ['SYNTHETIC_REDIS_PASSWORD'])
lim=R.RedisRateLimiter(c,prefix=os.environ['SYNTHETIC_REDIS_NAMESPACE'],key_secret='same-synthetic-key'*3)
app=FastAPI()
@app.get('/protected')
def protected():
 R.enforce('auth_login_ip','203.0.113.1',limiter=lim)
 return {'ok':True}
with TestClient(app) as client:
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  responses=list(pool.map(lambda _:client.get('/protected'),range(20)))
 assert all(r.status_code in (200,429) for r in responses)
 assert all(int(r.headers['Retry-After'])>0 for r in responses if r.status_code==429)
 print(json.dumps({'allowed':sum(r.status_code==200 for r in responses),'degraded':lim.degraded,'local_fallbacks':lim.local_fallbacks}))
'''


def test_two_independent_fastapi_processes_share_the_existing_auth_ceiling(real):
    env = dict(os.environ, SYNTHETIC_REDIS_PORT=str(real['port']), SYNTHETIC_REDIS_PASSWORD=real['password'],
               SYNTHETIC_REDIS_NAMESPACE=real['namespace'] + 'processes:')
    processes = [subprocess.Popen([sys.executable, '-c', WORKER], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    replies = [p.communicate(timeout=60) for p in processes]
    assert all(p.returncode == 0 for p in processes), 'synthetic application process failed'
    values = [json.loads(out) for out, _err in replies]
    assert sum(v['allowed'] for v in values) == R.POLICIES['auth_login_ip'].limit == 20
    assert not any(v['degraded'] or v['local_fallbacks'] for v in values)


def test_server_clock_is_authoritative_and_windows_expire(real):
    a = limiter(real, 'clock', clock=lambda: time.time() - 86400)
    b = limiter(real, 'clock', clock=lambda: time.time() + 86400)
    policy = R.RateLimitPolicy('p', 1, 1, 'user')
    assert a.hit('b', 'u', policy).allowed
    result = b.hit('b', 'u', policy)
    assert not result.allowed and 1 <= result.retry_after <= 2
    assert 0 < real['admin'].ttl(a.store_key('b', 'u')) <= 2
    time.sleep(2.2)
    assert not real['admin'].exists(a.store_key('b', 'u'))
    assert b.hit('b', 'u', policy).allowed


def test_namespaces_identities_private_keys_and_acl_isolation(real):
    import redis
    a, b = limiter(real, 'keys'), limiter(real, 'other')
    policy = R.RateLimitPolicy('p', 1, 30, 'user')
    assert a.hit('b', 'user:1', policy).allowed and not a.hit('b', 'user:1', policy).allowed
    assert a.hit('b', 'user:2', policy).allowed and b.hit('b', 'user:1', policy).allowed
    keys = real['admin'].keys(real['namespace'] + 'keys:*')
    assert len(keys) == 2 and all(b'user:' not in k and b'@' not in k for k in keys)
    c = real['client']()
    with pytest.raises(redis.exceptions.NoPermissionError):
        c.eval('return redis.call("ZCARD", KEYS[1])', 1, 'another-application:key')
    with pytest.raises(redis.exceptions.NoPermissionError):
        c.flushdb()
    with pytest.raises(redis.exceptions.NoPermissionError):
        c.scan()
    outside = limiter(real, 'keys', prefix='outside:')
    assert not outside.hit('b', 'u', R.RateLimitPolicy('deny', 1, 30, 'user', 'deny')).allowed
    assert outside.degraded


def test_missing_and_wrong_credentials_are_never_active(real):
    for password in ('', 'wrong-synthetic-password'):
        client = real['client'](supplied=password)
        lim = R.RedisRateLimiter(client, prefix=real['namespace']+'auth:')
        R.reset_rate_limiter(lim)
        status = R.limiter_status(probe=True)
        assert status['configured'] and status['reachable'] is False and not status['effectively_distributed']
        assert not lim.hit('b', 'u', R.RateLimitPolicy('s', 1, 10, 'user', 'deny')).allowed


def test_connection_loss_local_deny_and_recovery(real):
    from fastapi import HTTPException
    local = limiter(real, 'outage')
    policy = R.RateLimitPolicy('p', 2, 30, 'user')
    assert local.hit('b', 'u', policy).allowed
    docker('stop', '-t', '0', real['name'])
    try:
        assert [local.hit('b', 'u', policy).allowed for _ in range(3)] == [True, True, False]
        strict = R.RateLimitPolicy('strict', 1, 30, 'user', 'deny')
        refused = local.hit('s', 'u', strict)
        assert not refused.allowed and refused.store_failure_denied and refused.retry_after == 5
        R.reset_rate_limiter(local)
        assert R.limiter_status()['state'] == 'fail_closed'
        # Same HTTP seam as protected routes, no policy activated in production.
        original = R.POLICIES.get('synthetic_deny')
        try:
            R.POLICIES['synthetic_deny'] = strict
            with pytest.raises(HTTPException) as exc:
                R.enforce('synthetic_deny', 'u', limiter=local)
            assert exc.value.status_code == 503 and exc.value.headers['Retry-After'] == '5'
        finally:
            if original is None: R.POLICIES.pop('synthetic_deny')
            else: R.POLICIES['synthetic_deny'] = original
    finally:
        docker('start', real['name'])
    for _ in range(50):
        result = local.hit('b', 'after-recovery', policy)
        if not local.degraded:
            break
        time.sleep(0.1)
    assert result.allowed and not local.degraded and local.recoveries == 1
    assert R.limiter_status()['state'] == 'recovered_shared'
    # Ephemeral server restart resets shared counters: explicitly qualify it.
    assert local.hit('b', 'u', policy).allowed


def test_paused_store_times_out_and_reconnects_without_automatic_retry(real):
    lim = limiter(real, 'timeout')
    assert lim.hit('b', 'u', R.RateLimitPolicy('p', 1, 20, 'user')).allowed
    docker('pause', real['name'])
    try:
        start = time.monotonic()
        result = lim.hit('b', 'u', R.RateLimitPolicy('p', 1, 20, 'user', 'deny'))
        assert not result.allowed and result.store_failure_denied
        assert time.monotonic() - start < 2  # production command timeout; retries disabled
    finally:
        docker('unpause', real['name'])
    assert lim.hit('b', 'fresh', R.RateLimitPolicy('p', 1, 20, 'user')).allowed
    assert not lim.degraded


def test_existing_05d_live_suite_executes_against_only_the_disposable_server(real):
    url = f"redis://testoperator:{real['password']}@127.0.0.1:{real['port']}/0"
    env = dict(os.environ, TEST_REDIS_URL=url)
    log = real['directory'] / 'legacy-05d.log'
    with log.open('w') as output:
        result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-o', 'addopts=', '-p', 'no:cacheprovider', 'tests/test_redis_limiter_live_05d.py'],
                                cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT, timeout=120)
    assert result.returncode == 0 and '3 passed' in log.read_text() and 'skipped' not in log.read_text()


def test_actual_auth_login_and_recovery_are_uniform_with_real_redis(real):
    from fastapi.testclient import TestClient
    from tests._auth_factories import build_auth_app, register
    app, _repo, mail = build_auth_app()
    R.reset_rate_limiter(limiter(real, 'actual-auth'))
    with TestClient(app) as client:
        assert register(client, 'known@example.invalid', 'correcthorsebattery').status_code == 201
        known = client.post('/api/v1/auth/login', json={'email':'known@example.invalid','password':'wrong-password'})
        unknown = client.post('/api/v1/auth/login', json={'email':'unknown@example.invalid','password':'wrong-password'})
        assert known.status_code == unknown.status_code == 401
        assert known.json()['error']['message'] == unknown.json()['error']['message']
        known = client.post('/api/v1/auth/forgot-password', json={'email':'known@example.invalid'})
        unknown = client.post('/api/v1/auth/forgot-password', json={'email':'unknown@example.invalid'})
        assert known.status_code == unknown.status_code == 200
        assert known.json()['message'] == unknown.json()['message']
        # Account limiter is applied before lookup, with the same ceiling.
        for _ in range(7):
            a = client.post('/api/v1/auth/login', json={'email':'known@example.invalid','password':'wrong-password'})
            b = client.post('/api/v1/auth/login', json={'email':'unknown@example.invalid','password':'wrong-password'})
            assert a.status_code == b.status_code == 401
        for address in ('known@example.invalid','unknown@example.invalid'):
            response = client.post('/api/v1/auth/login', json={'email':address,'password':'wrong-password'},headers={'Origin':'http://localhost:3000'})
            assert response.status_code == 429 and int(response.headers['Retry-After']) >= 1
            assert 'retry-after' in response.headers['Access-Control-Expose-Headers'].lower()
    assert not R.limiter_status()['degraded']
    assert mail is not None  # in-memory email capture only; no live email


def test_actual_internal_network_has_no_published_redis_port(real):
    import yaml
    project='ask4mo-private-redis-'+uuid.uuid4().hex[:10]
    directory=real['directory']/'private-compose'
    directory.mkdir()
    script=directory/'redis-start.sh'
    script.write_bytes((ROOT/'deploy/scripts/redis-start.sh').read_bytes())
    script.chmod(0o444)
    profile=yaml.safe_load((ROOT/'deploy/redis-internal.yml').read_text())
    profile['services']['redis']['volumes']=[f'{script}:/opt/ask4mo/redis-start.sh:ro']
    profile['services']['redis']['environment']={'RATE_LIMIT_NAMESPACE':real['namespace']}
    profile['secrets']={'redis_password':{'file':str(real['credential'])}}
    path=directory/'compose.yml'
    path.write_text(yaml.safe_dump(profile))
    command=('compose','--project-name',project,'-f',str(path))
    try:
        docker(*command,'up','-d','--no-build','--pull','never','redis')
        name=docker(*command,'ps','-q','redis')
        for _ in range(100):
            info=json.loads(docker('inspect',name))[0]
            if info['State'].get('Health',{}).get('Status')=='healthy':break
            time.sleep(.2)
        assert info['State']['Health']['Status']=='healthy'  # exact escaped Compose healthcheck actually executes
        assert not info['HostConfig']['PortBindings'] and not any(info['NetworkSettings']['Ports'].values())
        assert info['Config']['User']=='999:1000' and info['HostConfig']['ReadonlyRootfs']
        network=next(iter(info['NetworkSettings']['Networks']))
        assert json.loads(docker('network','inspect',network))[0]['Internal'] is True
    finally:
        docker(*command,'down','--volumes','--remove-orphans')  # only this unique, owned Redis test project


def test_required_shared_readiness_refuses_outage_and_reports_recovery(real,monkeypatch):
    from fastapi.testclient import TestClient
    from tests._auth_factories import build_auth_app
    from src.application import hosted_readiness as hr
    app,repo,_mail=build_auth_app()
    monkeypatch.setenv('RATE_LIMIT_SHARED_REQUIRED','true')
    monkeypatch.setattr('src.api.dependencies.get_repository',lambda request:repo)
    monkeypatch.setattr(hr,'is_hosted',lambda:True)
    monkeypatch.setattr(hr,'data_root_writable',lambda:True)
    monkeypatch.setattr(hr,'worker_status',lambda _sf:'healthy')
    monkeypatch.setattr(hr,'scanner_status',lambda:'disabled')
    lim=limiter(real,'readiness')
    R.reset_rate_limiter(lim)
    with TestClient(app) as client:
        before=client.get('/api/v1/ready')
        assert before.status_code==200 and before.json()['dependencies']['rate_limiter']=='shared'
        docker('stop','-t','0',real['name'])
        try:
            lim.hit('b','u',R.RateLimitPolicy('local',1,30,'user'))
            outage=client.get('/api/v1/ready')
            assert outage.status_code==503
            assert outage.headers['X-Rate-Limit-State']=='degraded_local' and real['password'] not in outage.text
            assert set(outage.json())=={'error'}  # existing safe envelope preserved
        finally:
            docker('start',real['name'])
        for _ in range(50):
            lim.hit('b','fresh',R.RateLimitPolicy('local',100,30,'user'))
            if not lim.degraded:break
            time.sleep(.1)
        after=client.get('/api/v1/ready')
        assert after.status_code==200 and after.json()['dependencies']['rate_limiter']=='recovered_shared'


@pytest.mark.parametrize('topology',['internal','managed'])
@pytest.mark.parametrize('mode',['promote','rollback'])
def test_real_compose_optional_topology_is_resolved_and_safety_checked(real,tmp_path,topology,mode):
    import copy
    import yaml
    from scripts import release_images as I, release_redis as RR
    base=yaml.safe_load((ROOT/'deploy/docker-compose.staging.yml').read_text())
    head=I.migration_chain(ROOT)[-1]
    manifest={'application_sha':'a'*40,'build_started_at':I.timestamp(),'public_api_base_url':'https://api.staging.example.com/api/v1',
              'images':{'application':{'image_id':'sha256:'+'a'*64},'web':{'image_id':'sha256:'+'b'*64}},
              'source':{'budget_policy_version':1,'migration_chain':[head],'compatible_schema_revisions':[head],
                        'deployment_files':{'deploy/scripts/redis-start.sh':I.file_hash(ROOT/'deploy/scripts/redis-start.sh')}}}
    url=f'sqlite:///{tmp_path / "test.db"}'
    state={'version':1,'observed_at':I.timestamp(),'schema_revision':head,'unsettled_agent_runs':0,'active_jobs':0,'drained':True,'database_identity_sha256':I.database_identity(url)}
    env=tmp_path/'synthetic.env'
    env.write_text('DATABASE_URL='+url+'\nPOSTGRES_PASSWORD=synthetic\nRATE_LIMIT_KEY_SECRET='+'test-key-'*8+'\nREDIS_URL=rediss://limiter:'+'test-password-'*4+'@managed.invalid:6379/0\n')
    password=tmp_path/'password'
    password.write_text('synthetic-password-'*3)
    caddy=tmp_path/'Caddyfile'
    caddy.write_bytes((ROOT/'deploy/Caddyfile').read_bytes())
    (tmp_path/'redis-start.sh').write_bytes((ROOT/'deploy/scripts/redis-start.sh').read_bytes())
    profile=I.profile_for(manifest,base,state,mode,env,caddy)
    profile=RR.apply(profile,ROOT,tmp_path,topology=topology,namespace=real['namespace'],password_file=str(password) if topology=='internal' else None)
    plan={'redis_topology':topology,'redis_namespace':real['namespace'],'redis_password_file':str(password) if topology=='internal' else None}
    path=tmp_path/'compose.yml'
    path.write_text(yaml.safe_dump(profile))
    resolved=json.loads(I.run(['docker','compose','--env-file',str(env),'-f',str(path),'config','--format','json']))
    RR.verify(resolved,plan,manifest,tmp_path)
    assert ('migrate' in resolved['services'])==(mode=='promote')
    if mode=='promote':
        for name in ('api','worker'):
            assert resolved['services'][name]['depends_on']['migrate']['condition']=='service_completed_successfully'
    else:
        assert all('migrate' not in resolved['services'][name]['depends_on'] for name in ('api','worker'))
    assert resolved['services']['api']['image']==resolved['services']['worker']['image']
    if topology=='internal':
        changed=copy.deepcopy(resolved)
        changed['services']['redis']['ports']=[{'target':6379,'published':'6379','protocol':'tcp'}]
        with pytest.raises(ValueError):RR.verify(changed,plan,manifest,tmp_path)
    for key,value in [('RATE_LIMIT_NAMESPACE','ask4mo:rl:wrong:'),('RATE_LIMIT_KEY_SECRET','different-key-'*4),('REDIS_URL','rediss://limiter:'+'other-password-'*4+'@other.invalid:6379/0')]:
        changed=copy.deepcopy(resolved)
        changed['services']['worker']['environment'][key]=value
        with pytest.raises(ValueError):RR.verify(changed,plan,manifest,tmp_path)


def test_real_production_client_builder_uses_bounded_connections_and_private_settings(real,monkeypatch):
    monkeypatch.setenv('RATE_LIMIT_BACKEND','redis')
    monkeypatch.setenv('REDIS_URL',f"redis://limiter@127.0.0.1:{real['port']}/0")
    monkeypatch.setenv('REDIS_PASSWORD_FILE',str(real['credential']))
    monkeypatch.setenv('RATE_LIMIT_KEY_SECRET','synthetic-shared-key-'*3)
    monkeypatch.setenv('RATE_LIMIT_NAMESPACE',real['namespace']+'builder:')
    lim=R.build_rate_limiter()
    R.reset_rate_limiter(lim)
    assert isinstance(lim,R.RedisRateLimiter) and not R.shared_store_active()
    options=lim._client.connection_pool.connection_kwargs
    assert options['socket_timeout']==options['socket_connect_timeout']==1.0
    import redis
    assert isinstance(lim._client.connection_pool,redis.BlockingConnectionPool)
    assert lim._client.connection_pool.timeout==1.0
    assert options['protocol']==2 and lim._client.connection_pool.max_connections==16
    assert options['retry'].get_retries()==0
    assert lim.hit('b','u',R.RateLimitPolicy('builder',1,30,'user')).allowed
    assert R.shared_store_active()


def test_production_connection_pool_keeps_a_shared_ceiling_during_a_concurrent_burst(real):
    import threading
    client=R.make_redis_client(f"redis://limiter@127.0.0.1:{real['port']}/0",password=real['password'])
    lim=R.RedisRateLimiter(client,prefix=real['namespace']+'production-burst:',key_secret='same-shared-test-key'*3)
    policy=R.RateLimitPolicy('burst',20,30,'user')
    gate=threading.Barrier(64)
    def hit(_):
        gate.wait(timeout=20)
        return lim.hit('b','user:1',policy).allowed
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as executor:
        outcomes=list(executor.map(hit,range(64)))
    assert lim.local_fallbacks==0 and not lim.degraded
    assert sum(outcomes)==20
