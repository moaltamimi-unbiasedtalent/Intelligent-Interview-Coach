"""Private in-container synthetic probes. Never imported by ordinary application startup."""
from __future__ import annotations
import http.client
import json
import os
from pathlib import Path
import re
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.integration.runtime import boundary, control, agent  # noqa: E402


def require(ok,code):
    if not ok:raise RuntimeError(code)


def factory():
    boundary()
    from src.persistence import make_engine,make_session_factory
    return make_session_factory(make_engine(os.environ['DATABASE_URL']))


def credentials():return json.loads(Path('/campaign/private/credentials.json').read_text())


def http(path,method='GET',payload=None,*,cookie='',host='api',raw=False):
    require(host in ('api','api_b','api_held'),'campaign_http_host_refused')
    require(path.startswith('/api/') and '://' not in path,'campaign_http_path_refused')
    conn=http.client.HTTPConnection(host,8000,timeout=35)
    data=json.dumps(payload) if payload is not None else None
    conn.request(method,path,data,{'Content-Type':'application/json','Cookie':cookie,'Origin':'https://app.staging.example.com'})
    response=conn.getresponse();body=response.read();headers=dict(response.getheaders());status=response.status;conn.close()
    if not raw:
        try:body=json.loads(body)
        except ValueError:body={}
    return status,body,headers


def login(who='alice',host='api'):
    c=credentials()[who]
    status,_,headers=http('/api/v1/auth/login','POST',{'email':c['email'],'password':c['password']},host=host)
    require(status==200,'synthetic_login_failed')
    cookie=headers.get('set-cookie',headers.get('Set-Cookie','')).split(';')[0]
    require(cookie.startswith('ask4mo_session='),'session_cookie_missing')
    return cookie


def seed():
    # This one-shot initializer owns ONLY the freshly created labelled control
    # volume. Drop root permanently BEFORE importing application repositories.
    boundary()
    if os.getuid()==0:
        root=Path('/campaign');require(not any(root.iterdir()),'fresh_control_volume_required')
        root.chmod(0o700);os.chown(root,10001,10001)
        os.setgroups([]);os.setgid(10001);os.setuid(10001)
    require(os.getuid()==10001,'non_root_fixture_required')
    from src.application.auth_service import AuthenticationService,AuthConfig
    from src.auth_repository import AccountRepository,SessionRepository,TokenRepository,AuditRepository
    from src.mail import MemoryEmailSender
    from src.invitations import repository as IR
    from src.application import admin_audit as A
    from src.persistence import User
    sf=factory();accounts=AccountRepository(sf);mail=MemoryEmailSender()
    svc=AuthenticationService(accounts=accounts,sessions=SessionRepository(sf),auth_tokens=TokenRepository(sf),audit=AuditRepository(sf),email=mail,config=AuthConfig.from_env())
    out={}
    for who in ('alice','bob','admin'):
        code=IR.new_code();audit=A.build_audit(event_type=A.ADMIN_INVITATION_ISSUED,actor_user_id=None,request_id=None,target_type='invitation',origin='cli')
        IR.InvitationRepository(sf).issue(code_hash=IR.hash_code(code),ttl_days=1,email=None,issued_by_user_id=None,audit=audit)
        email=who+'@example.invalid';password=os.environ['CAMPAIGN_PASSWORD']
        require(svc.register(email=email,password=password,display_name='Synthetic '+who,locale='en',invitation_code=code,require_invitation=True).created,'fixture_registration_failed')
        token=re.search(r'token=([^\s&]+)',mail.sent[-1].body).group(1)
        require(svc.verify_email(token=token),'fixture_verification_failed')
        account=accounts.find_by_email(email);accounts.complete_onboarding(account.user_id)
        out[who]={'email':email,'password':password,'user_id':account.user_id}
        if who=='admin':
            with sf() as s:s.get(User,account.user_id).platform_role='platform_admin';s.commit()
    control(mode='plain')
    from src.agent.models import AgentRunRequest
    result=agent().run(AgentRunRequest(goal='Synthetic existing-run fixture',user_id=str(out['alice']['user_id']),enable_current_market_research=False))
    require(result.status=='completed','scripted_agent_seed_failed')
    out['run_id']=result.run_id
    p=Path('/campaign/private');p.mkdir(mode=0o700);file=p/'credentials.json';file.write_text(json.dumps(out));file.chmod(0o600)
    return {'synthetic_accounts':3,'mail':'memory_capture_only','existing_run_fixture':True,'language_activation_overridden':False}


def state():
    from sqlalchemy import text
    with factory()() as s:
        heads=s.execute(text('select version_num from alembic_version')).scalars().all()
    require(heads==['0048_agent_run_controls'],'unexpected_schema')
    return {'schema':heads[0]}


def identity():
    require(os.getuid()==10001,'non_root_required')
    for root in ('/data/documents','/data/knowledge'):
        path=Path(root)/'.campaign-write-test';path.write_text('synthetic');path.unlink()
    from src.agent.run_control import RunControlStore
    from src.llm.budget.governor import HOSTED_POLICY_VERSION
    require(HOSTED_POLICY_VERSION==2 and RunControlStore is not None,'durable_controls_missing')
    return {**state(),'uid':os.getuid(),'private_roots_writable':True,'migration_helper_present':Path('scripts/migrate.sh').is_file()}


def http_checks():
    cookie=login();other=login('bob',host='api_b');admin=login('admin')
    require(http('/api/v1/auth/me',cookie=cookie)[0]==200,'session_missing')
    require(http('/api/v1/auth/me',cookie=cookie,host='api_b')[0]==200,'cross_instance_session_missing')
    require(http('/api/v1/auth/me',cookie='ask4mo_session=expired-synthetic')[0]==401,'expired_session_accepted')
    require(http('/api/v1/admin/home',cookie=other)[0]==403,'candidate_admin_access')
    require(http('/api/v1/admin/home',cookie=admin)[0]==200,'admin_visibility_failed')
    rid=credentials()['run_id']
    require(http('/api/v1/agent/runs/'+rid,cookie=other)[0]==404,'run_owner_isolation_failed')
    status,body,_=http('/api/v1/agent/run','POST',{'goal':'Synthetic refused new activity'},cookie=cookie)
    require(status==503 and 'language_not_activated' in json.dumps(body),'language_gate_not_closed')
    status,_,_=http('/api/v1/auth/register','POST',{'email':'new@example.invalid','password':os.environ['CAMPAIGN_PASSWORD'],'locale':'en'})
    require(status in (403,503),'hosted_registration_not_refused')
    require(http('/api/v1/auth/logout','POST',cookie=other)[0]==200,'logout_failed')
    require(http('/api/v1/auth/me',cookie=other)[0]==401,'logout_not_persisted')
    return {'checks':9,'shared_sessions':True,'ownership':True,'new_language_activity':'refused','admin':'metadata_only'}


def jobs():
    from src.jobs.service import JobService
    from src.persistence import Job
    from sqlalchemy import select
    sf=factory();svc=JobService(sf)
    one,created=svc.enqueue('diagnostic_noop',{'label':'campaign'},idempotency_key='campaign-noop')
    require(created,'fresh_job_required')
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        with sf() as s:row=s.scalar(select(Job).where(Job.public_id==one['public_id']));status=row.state;attempts=row.attempts
        if status=='succeeded':break
        time.sleep(.25)
    require(status=='succeeded' and attempts==1,'worker_single_claim_failed')
    return {'real_worker_job':'succeeded','attempts':attempts,'workers':2}


def agent_checks():
    cookie=login();rid=credentials()['run_id'];before=control()['calls'];path='/api/v1/agent/runs/'+rid+'/events'
    for host in ('api','api_b'):
        status,data,_=http(path,cookie=cookie,host=host,raw=True)
        require(status==200 and b'event:' in data and b'result' in data,'sse_result_missing')
        require(not any(x in data for x in (b'system_prompt',b'chain_of_thought',b'provider_api_key')),'private_sse_event')
    require(control()['calls']==before,'reconnection_executed_model')
    status,body,_=http('/api/v1/agent/runs/'+rid,cookie=cookie)
    require(status==200 and body['status']=='completed','completed_state_missing')
    return {'real_graph_pg_checkpoint':True,'sse_reads':2,'model_calls_on_reconnect':0,'usage':body.get('usage')}


def budget():
    # Direct typed ledger fixture: never installs an OPEN governor or creates an
    # owner approval record. Both real application processes remain CLOSED.
    from src.llm.budget.config import BudgetConfig,ClassBudget,Ceiling,Limits
    from src.llm.budget.ledger import DbBudgetLedger
    from src.llm.budget.errors import BudgetError
    cfg=BudgetConfig(classes={'production':ClassBudget(Ceiling(1000,900),100,{'agent':Ceiling(1000,900)})},limits=Limits(100,100,1,0,10),pricing={},approval_marker=None,total=Ceiling(1000,900),total_max_requests=100)
    sf=factory();ledger=DbBudgetLedger(sf)
    def reserve(fp):return ledger.reserve(cfg,budget_class='production',category='agent',operation='agent',model='synthetic',endpoint='chat',fingerprint=fp,worst_case=600)
    reservation=reserve('campaign-first');ledger.settle(reservation,outcome='unknown')
    for fp in ('campaign-retry','campaign-second'):
        try:reserve(fp)
        except BudgetError:pass
        else:raise RuntimeError('spend_cap_bypassed')
    before=ledger.snapshot(cfg,'production');after=DbBudgetLedger(factory()).snapshot(cfg,'production')
    require(before==after,'durable_spend_changed')
    ledger.kill('synthetic_campaign')
    require(DbBudgetLedger(factory()).killed(),'kill_not_durable')
    return {'typed_ledger_fixture':True,'unknown_reservation_preserved':True,'retry_cap_refused':True,'restart_snapshot_equal':True,'kill_persisted':True,'owner_approval_created':False}


def scanner():
    from src.documents.file_security import ClamAvScanner,EICAR
    scan=ClamAvScanner(host='clamav',port=3310,connect_timeout=1,scan_timeout=5)
    clean=scan.scan(b'Synthetic harmless text.','synthetic.txt');infected=scan.scan(EICAR,'eicar.txt')
    require(clean.clean and not infected.clean and infected.status=='infected','real_clamd_scan_failed')
    return {'clean':clean.status,'eicar':infected.status,'scanner':'real_clamd','definitions':'offline_eicar_only','freshness_qualified':False}


def outage(kind):
    if kind=='db_down':require(http('/api/v1/ready')[0]==503,'database_outage_not_refused')
    elif kind=='redis_down':
        status,body,_=http('/api/v1/ready');require(status==503,'shared_required_outage_not_refused')
        require('rate_limiter' in json.dumps(body),'redis_outage_not_visible')
    else:
        from src.documents.file_security import ClamAvScanner,FileScanUnavailable
        try:ClamAvScanner(host='clamav',port=3310,connect_timeout=1,scan_timeout=2).scan(b'Synthetic','synthetic.txt')
        except FileScanUnavailable:pass
        else:raise RuntimeError('scanner_outage_permissive')
    return {'injected':kind,'refused':True}


def recovered():
    require(http('/api/v1/ready')[0]==200,'readiness_not_recovered')
    return scanner()


ACTIONS={'seed':seed,'state':state,'identity':identity,'http':http_checks,'jobs':jobs,'agent':agent_checks,'budget':budget,'scanner':scanner,'recovered':recovered}


def main():
    try:
        boundary();action=sys.argv[1]
        facts=outage(action) if action in ('db_down','redis_down','scanner_down') else ACTIONS[action]()
        print(json.dumps({'ok':True,**facts},sort_keys=True));return 0
    except Exception as e:
        # Exception text can contain connection strings, SQL or private payloads.
        print(json.dumps({'ok':False,'code':type(e).__name__}));return 1


if __name__=='__main__':raise SystemExit(main())
