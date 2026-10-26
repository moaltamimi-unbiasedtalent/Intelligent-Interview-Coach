#!/usr/bin/env python3
"""Task 07: opt-in disposable connected stack, using verified release images.

No deploy command, private dotenv fallback, registry push or broad Docker cleanup.
The local capacity guard runs before any resource creation. Evidence is structured
and secret-free; only resources bearing this campaign's unique label are removed.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time
import uuid
import yaml
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts import release_images as R, recovery_images as I  # noqa: E402

LABEL='io.ask4mo.integration.campaign'
APP='app.staging.example.com'
API='api.staging.example.com'
PG='postgres:16@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97'
SAFE_FILES=('summary.json','safe-logs.json','browser-summary.json','service-evidence.json')


class CampaignError(Exception):
    pass


def require(ok, code):
    if not ok:raise CampaignError(code)


def command(args, *, data=None, timeout=120, check=True, env=None):
    p=subprocess.run([str(a) for a in args],input=data,capture_output=True,timeout=timeout,env=env)
    if check:require(p.returncode==0,'campaign_command_failed')
    return p


def capacity():
    # The already present PG image runs a read-only df probe: no volume, network,
    # key, source checkout or application environment is mounted.
    p=command(['docker','run','--rm','--pull','never','--network','none','--read-only','--entrypoint','df',PG,'-Pk','/'])
    return int(p.stdout.decode().splitlines()[-1].split()[3])*1024


def local_caddy(source):
    # Preserve the real staging routing/security headers. Only ACME is replaced
    # by an isolated internal test CA; no public domain/DNS challenge is used.
    source=source.replace('email {$ACME_EMAIL}','auto_https disable_redirects')
    for domain in ('{$APP_DOMAIN}','{$API_DOMAIN}'):
        source=source.replace(domain+' {',domain+' {\n\ttls internal',1)
    return source


def topology(manifest, record, directory, campaign):
    require(re.fullmatch(r'[a-f0-9]{16}',campaign) is not None,'campaign_identity_invalid')
    require(manifest['public_api_base_url']=='https://'+API+'/api/v1','reserved_test_origin_required')
    d=Path(directory).resolve();project='ask4mo-campaign-'+campaign
    state=dict(version=1,observed_at=R.timestamp(),schema_revision='base',unsettled_agent_runs=0,active_jobs=0,
               drained=True,database_identity_sha256='d'*64,recovery_pending=False)
    base=yaml.safe_load((ROOT/'deploy/docker-compose.staging.yml').read_text())
    p=R.profile_for(manifest,base,state,'promote',d/'private'/'runtime.env',d/'Caddyfile')
    from scripts.release_redis import apply
    p=apply(p,ROOT,d,topology='internal',namespace='ask4mo:rl:campaign'+campaign+':',password_file=d/'private'/'redis-password')
    p['name']=project
    p['networks'].setdefault('default',{})['internal']=True
    p['volumes']['campaign-control']={}
    images=json.loads((ROOT/'deploy/integration-images.json').read_text())['images']
    arch=manifest['images']['application']['platform'].split('/')[-1]
    p['services']['db']['image']=PG
    p['services']['db']['environment']={'POSTGRES_USER':'disposable','POSTGRES_PASSWORD':'synthetic-test-only',
                                        'POSTGRES_DB':'p5b_recovery_campaign_'+campaign}
    p['services']['db'].pop('env_file',None)
    p['services']['db']['healthcheck']['test']=['CMD-SHELL','pg_isready -U disposable -d p5b_recovery_campaign_'+campaign]
    p['services']['clamav'].update(image=images['clamav']['digests'][arch],entrypoint=['clamd','--foreground=true','--config-file=/campaign/clamd.conf'],
        volumes=[dict(type='bind',source=str(d/'clamd.conf'),target='/campaign/clamd.conf',read_only=True),
                 dict(type='bind',source=str(d/'signatures'),target='/campaign/signatures',read_only=True)],
        tmpfs=['/tmp:rw,nosuid,noexec,size=67108864'],read_only=True,
        healthcheck={'test':['CMD','clamdscan','--ping=1','--config-file=/campaign/clamd.conf'],'interval':'3s','timeout':'3s','retries':30})
    p['services']['caddy']['image']=images['caddy']['digests'][arch]
    p['services']['caddy']['ports']=['127.0.0.1:443:443']
    p['services']['caddy']['environment'].update(APP_DOMAIN=APP,API_DOMAIN=API)
    # The stock web image has Node's HTTP client; curl is not an application
    # dependency. Check it without installing anything or changing the image.
    p['services']['web']['healthcheck']['test']=['CMD','node','-e',"require('http').get('http://127.0.0.1:3000/',r=>process.exit(r.statusCode<500?0:1)).on('error',()=>process.exit(1))"]
    for name in ('api','worker'):
        s=p['services'][name]
        s['volumes'].append('campaign-control:/campaign')
        s['environment'].update(ASK4MO_DISPOSABLE_CAMPAIGN=campaign,PYTHON_DOTENV_DISABLED='1',
            ASK4MO_PROVIDER_MODE='offline',AI_BUDGET_MODE='enforce',AI_BUDGET_CLASS='production',AI_BUDGET_CONFIG_PATH='',
            EMAIL_PROVIDER='memory',TRUST_PROXY='true',MALWARE_SCAN_REQUIRED='true',AGENT_COACH_ENABLED='true',
            DOCUMENT_STORAGE_DIR='/data/documents',CLAMAV_CONNECT_TIMEOUT_SECONDS='1',CLAMAV_SCAN_TIMEOUT_SECONDS='5')
        s['restart']='no'
    p['services']['api']['command']=['python','scripts/integration/runtime.py','serve']
    p['services']['api_b']=copy.deepcopy(p['services']['api'])
    p['services']['worker_b']=copy.deepcopy(p['services']['worker'])
    p['services']['probe']=copy.deepcopy(p['services']['api'])
    probe=p['services']['probe'];probe.pop('healthcheck',None);probe['command']=['python','scripts/integration/probe.py','seed']
    probe['image']=record['operator_image_id'];probe['profiles']=['tools'];probe.pop('depends_on',None)
    probe['volumes'].append(dict(type='bind',source=str(d/'private'/'release-facts.json'),target='/release-facts.json',read_only=True))
    probe['environment']['RECOVERY_RELEASE_FILE']='/release-facts.json'
    for name,s in p['services'].items():
        s.setdefault('labels',{})[LABEL]=campaign
        s['restart']='no'
        s.setdefault('pull_policy','if_not_present')
        if name in ('api','api_b','worker','worker_b','probe'):
            if s.get('healthcheck'):s['healthcheck'].update(interval='4s',start_period='10s',retries=20)
    for volumes in (p['volumes'],p['networks']):
        for name,spec in volumes.items():
            if spec is None:spec=volumes[name]={}
            spec.setdefault('labels',{})[LABEL]=campaign
    return p


class Campaign:
    def __init__(self,args):
        self.args=args;self.directory=Path(args.out).resolve();self.id=uuid.uuid4().hex[:16]
        self.project='ask4mo-campaign-'+self.id;self.items=[];self.created=False;self.started=time.monotonic()
        self.summary={'version':1,'kind':'disposable_connected_stack','campaign':self.id,'source_sha':args.expected_sha,
            'started_at':datetime.now(timezone.utc).isoformat(),'items':self.items,'production_or_language_approval':False}
        self.env={k:v for k,v in os.environ.items() if k not in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy')}
    def save(self):
        self.summary['duration_seconds']=round(time.monotonic()-self.started,3)
        self.summary['counts']={s:sum(i['status']==s for i in self.items) for s in ('PASS','FAIL','SKIP','NOT RUN')}
        self.summary['result']='FAIL' if any(i['status']=='FAIL' for i in self.items) else 'PARTIAL_EXTERNAL_DEPENDENCIES' if any(i['status']=='NOT RUN' for i in self.items) else 'PASS'
        (self.directory/'summary.json').write_text(json.dumps(self.summary,indent=2,sort_keys=True)+'\n')
    def check(self,name,fn):
        before=time.monotonic()
        try:
            facts=fn() or {};self.items.append({'id':name,'status':'PASS','facts':facts})
            return True
        except Exception as error:
            code=str(error) if isinstance(error,CampaignError) else type(error).__name__
            self.items.append({'id':name,'status':'FAIL','code':code})
            return False
        finally:
            self.items[-1]['seconds']=round(time.monotonic()-before,3);self.save()
    def compose(self,*args,timeout=120,check=True):
        return command(['docker','compose','--project-name',self.project,'--env-file',self.directory/'private'/'runtime.env',
                        '-f',self.directory/'compose.json',*args],timeout=timeout,check=check,env=self.env)
    def probe(self,action,*,service=None,timeout=120):
        if service:
            p=self.compose('exec','-T',service,'python','scripts/integration/probe.py',action,timeout=timeout)
        else:p=self.compose('run','--rm','--no-deps',*(['--user','0:0'] if action=='seed' else []),'probe','python','scripts/integration/probe.py',action,timeout=timeout)
        # The helper emits one safe JSON object; driver exceptions never escape.
        lines=p.stdout.decode().splitlines();result=json.loads(lines[-1]);require(result.get('ok') is True,'integration_probe_failed_'+action)
        return result
    def request(self,path,method='GET',payload=None,*,cookies='candidate',origin=None,timeout=15):
        require(path.startswith('/api/') and '://' not in path,'internal_request_path_required')
        jar=self.directory/'private'/('cookies-'+cookies)
        argv=['curl','--silent','--show-error','--insecure','--noproxy','*','--resolve',API+':443:127.0.0.1',
              '--max-time',str(timeout),'-X',method,'-b',jar,'-c',jar,'-H','Content-Type: application/json','-w','\n%{http_code}',
              'https://'+API+path]
        if origin:argv+=['-H','Origin: '+origin]
        if payload is not None:argv+=['--data-binary','@-']
        p=command(argv,data=json.dumps(payload).encode() if payload is not None else None,check=False,timeout=timeout+2,env=self.env)
        require(p.returncode==0,'edge_request_failed')
        content,code=p.stdout.decode().rsplit('\n',1)
        try:body=json.loads(content)
        except ValueError:body={}
        return int(code),body
    def wait_ready(self,timeout=120):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            try:
                if self.request('/api/v1/ready')[0]==200:return
            except Exception:pass
            time.sleep(1)
        raise CampaignError('connected_stack_not_ready')
    def setup(self):
        require(not self.directory.exists(),'campaign_output_exists');self.directory.mkdir(parents=True,mode=0o700)
        (self.directory/'private').mkdir(mode=0o700)
        free=capacity();self.summary['docker_available_bytes_before']=free
        require(free>=8*1024**3,'insufficient_docker_capacity')
        with socket.socket() as s:
            try:s.bind(('127.0.0.1',443))
            except OSError:raise CampaignError('loopback_tls_port_occupied') from None
        m=R.decode_json(Path(self.args.manifest).read_text());R.validate_manifest(m,self.args.expected_sha,self.args.manifest_sha256)
        record=R.decode_json(Path(self.args.runner).read_text());I.validate(record,self.args.runner_sha256,m,self.args.manifest_sha256)
        self.manifest=m
        self.summary.update(images={k:v['image_id'] for k,v in m['images'].items()},operator_image=record['operator_image_id'],
                            release_manifest_sha256=self.args.manifest_sha256,operator_manifest_sha256=self.args.runner_sha256)
        private=self.directory/'private'
        password='synthetic-campaign-password-123!'
        env=dict(DATABASE_URL='postgresql+psycopg://disposable:synthetic-test-only@db:5432/p5b_recovery_campaign_'+self.id,
            AGENT_CHECKPOINT_DATABASE_URL='postgresql+psycopg://disposable:synthetic-test-only@db:5432/p5b_recovery_campaign_'+self.id,
            API_ENV='staging',FRONTEND_ORIGINS='https://'+APP,APP_BASE_URL='https://'+APP,DOCUMENT_STORAGE_DIR='/data/documents',
            COPILOT_DATA_DIR='/data/knowledge',RATE_LIMIT_KEY_SECRET=secrets.token_hex(32),SESSION_SECRET=secrets.token_hex(32),
            PYTHON_DOTENV_DISABLED='1',ASK4MO_PROVIDER_MODE='offline',EMAIL_PROVIDER='memory',
            CAMPAIGN_PASSWORD=password,ASK4MO_DISPOSABLE_CAMPAIGN=self.id)
        (private/'runtime.env').write_text(''.join(k+'='+v+'\n' for k,v in env.items()));(private/'runtime.env').chmod(0o600)
        (private/'redis-password').write_text(secrets.token_urlsafe(32));(private/'redis-password').chmod(0o444) # disposable UID999 input only
        (private/'release-facts.json').write_text(json.dumps(I.facts(m,self.args.manifest_sha256)));(private/'release-facts.json').chmod(0o644)
        (self.directory/'redis-start.sh').write_bytes((ROOT/'deploy/scripts/redis-start.sh').read_bytes())
        (self.directory/'Caddyfile').write_text(local_caddy((ROOT/'deploy/Caddyfile').read_text()))
        (self.directory/'signatures').mkdir()
        from src.documents.file_security import EICAR
        (self.directory/'signatures'/'campaign.hdb').write_text(hashlib.md5(EICAR).hexdigest()+':'+str(len(EICAR))+':Ask4Mo.Disposable.Eicar\n')
        (self.directory/'clamd.conf').write_text('Foreground yes\nUser clamav\nTCPSocket 3310\nTCPAddr 0.0.0.0\nDatabaseDirectory /campaign/signatures\nTemporaryDirectory /tmp\nPidFile /tmp/campaign.pid\nLogTime yes\nMaxThreads 2\nStreamMaxLength 25M\nConcurrentDatabaseReload no\n')
        config=topology(m,record,self.directory,self.id)
        (self.directory/'compose.json').write_text(json.dumps(config,indent=2))
        resolved=json.loads(self.compose('config','--format','json').stdout)
        require(all(not s.get('privileged') and not s.get('build') for s in resolved['services'].values()),'unverified_build_or_privilege')
        require(resolved['services']['caddy']['ports'][0]['host_ip']=='127.0.0.1','public_binding_refused')
        self.summary['topology']={'services':sorted(config['services']),'network_internal':True,'tls':'isolated internal CA; no ACME',
                                  'scanner_definitions':'offline EICAR fixture only; freshness/coverage NOT qualified'}
        return {'available_bytes':free,'services':len(config['services'])}
    def startup(self):
        self.created=True
        self.compose('up','-d','--wait','db','redis','clamav',timeout=180)
        self.compose('run','--rm','migrate',timeout=180)
        seed=self.probe('seed')
        self.compose('up','-d','--wait','api','api_b','worker','worker_b','web','caddy',timeout=180)
        self.wait_ready();return seed
    def restart(self):
        before=self.probe('state')
        self.compose('restart','api','api_b','worker','worker_b',timeout=90);self.wait_ready()
        after=self.probe('state')
        require(before['schema']==after['schema'] and before['schema']=='0048_agent_run_controls','restart_migration_changed')
        return {'schema_unchanged':True,'source_revision':after['schema']}
    def fault(self,service,action):
        self.compose('stop',service,timeout=40)
        try:result=self.probe(action,timeout=90)
        finally:self.compose('start',service,timeout=60)
        if service in ('db','redis'):self.wait_ready()
        return result
    def browser(self):
        # Fetch only synthetic fixture credentials privately; never echo them or
        # upload a storageState/trace containing cookies or credentials.
        p=self.compose('exec','-T','api','cat','/campaign/private/credentials.json')
        target=self.directory/'private'/'browser.json';target.write_bytes(p.stdout);target.chmod(0o600)
        env={**self.env,'BASE_URL':'https://'+APP,'CAMPAIGN_ID':self.id,'CAMPAIGN_CREDENTIALS_FILE':str(target),
             'CAMPAIGN_BROWSER_REPORT':str(self.directory/'browser-summary.json'),'CAMPAIGN_PRIVATE_RESULTS':str(self.directory/'private'/'browser-results'),'CI':'true'}
        result=command(['npx','playwright','test','--config','playwright.integration.config.ts'],timeout=300,check=False,env=env)
        # Commands run from the frontend without modifying cwd in this process.
        require(result.returncode==0,'connected_browser_journey_failed')
        return json.loads((self.directory/'browser-summary.json').read_text())
    def collect(self):
        if not self.created:return
        safe={}
        for service in ('db','redis','api','api_b','worker','worker_b','clamav','web','caddy'):
            p=self.compose('logs','--no-color','--tail','250',service,check=False)
            data=p.stdout.decode(errors='replace');lines=data.splitlines()
            safe[service]={'line_count':len(lines),'sha256':hashlib.sha256(p.stdout).hexdigest(),
                'observed_events':[label for label,pattern in [('started',r'started|startup complete|ready to'),('stopped',r'shutdown|stopped'),
                ('error',r'ERROR|Error|failed'),('healthy',r'healthy|accept connections')] if re.search(pattern,data,re.I)]}
        (self.directory/'safe-logs.json').write_text(json.dumps(safe,indent=2))
        p=self.compose('ps','--all','--format','json',check=False)
        rows=[]
        for line in p.stdout.decode().splitlines():
            try:j=json.loads(line);rows.extend(j if isinstance(j,list) else [j])
            except ValueError:continue
        facts=[{k:r.get(k) for k in ('Service','State','Health','ExitCode')} for r in rows]
        (self.directory/'service-evidence.json').write_text(json.dumps(facts,indent=2))
    def cleanup(self):
        if not self.created:return
        ids=command(['docker','ps','-aq','--filter','label=com.docker.compose.project='+self.project]).stdout.decode().split()
        for identity in ids:
            info=json.loads(command(['docker','inspect',identity]).stdout)[0]
            require(info['Config']['Labels'].get(LABEL)==self.id,'cleanup_ownership_refused')
        for kind,subcommand in [('volume','ls'),('network','ls')]:
            owned=command(['docker',kind,subcommand,'-q','--filter','label=com.docker.compose.project='+self.project]).stdout.decode().split()
            for identity in owned:
                info=json.loads(command(['docker',kind,'inspect',identity]).stdout)[0]
                require((info.get('Labels') or {}).get(LABEL)==self.id,'cleanup_ownership_refused')
        self.compose('down','--volumes','--remove-orphans',timeout=90)
        self.summary['cleanup']='only this campaign project containers/networks/volumes'
    def run(self):
        try:
            ready=self.check('prerequisites_and_verified_images',self.setup)
            if not ready:return 2
            if not self.args.execute_disposable:
                self.items.append({'id':'execution','status':'NOT RUN','code':'explicit_execute_required'});return 0
            ready=self.check('connected_startup_and_one_shot_migration',self.startup)
            if ready:
                self.check('private_roots_schema_and_service_identity',lambda:self.probe('identity'))
                self.check('sessions_ownership_profiles_documents_admin',lambda:self.probe('http'))
                self.check('worker_jobs_and_shared_state',lambda:self.probe('jobs'))
                self.check('agent_sse_reconnect_cancellation_hitl',lambda:self.probe('agent',timeout=120))
                self.check('monetary_limits_unknown_and_kill',lambda:self.probe('budget'))
                self.check('real_scanner_clean_eicar_and_manifest',lambda:self.probe('scanner'))
                # Preserve the actual Caddy policy. A failed UI hydration is a
                # mandatory failure, not an excuse to relax CSP or mock the API.
                prior=Path.cwd()
                try:os.chdir(ROOT/'frontend');self.check('connected_browser_journeys',self.browser)
                finally:os.chdir(prior)
                self.check('api_worker_restart_without_migration',self.restart)
                for service,action in [('db','db_down'),('redis','redis_down'),('clamav','scanner_down')]:
                    self.check('fault_'+service,lambda s=service,a=action:self.fault(s,a))
                self.check('dependencies_recovered',lambda:self.probe('recovered'))
                self.items.extend([{'id':name,'status':'NOT RUN','code':'connected_fault_driver_pending'} for name in
                    ('migration_failure_blocks_dependents','private_volume_inaccessible_refuses','api_process_loss_preserves_unsettled_usage','encrypted_recovery_transfer_erasure_hold')])
                self.items.extend([{'id':name,'status':'NOT RUN','code':'owner_or_hosted_qualification_required'} for name in
                    ('new_hosted_language_registration_and_interviews','live_ai_quality_and_embeddings','real_email_oidc','hosted_tls_and_signature_freshness','release_recovery_hold')])
            else:self.items.append({'id':'connected_scenarios','status':'NOT RUN','code':'startup_failed'})
        finally:
            if self.directory.exists():
                if self.created:self.check('safe_evidence_capture',self.collect);self.check('owned_resource_cleanup',self.cleanup)
                self.save()
        return 1 if any(i['status']=='FAIL' for i in self.items) else 0


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('manifest','manifest-sha256','runner','runner-sha256','expected-sha','out'):p.add_argument('--'+flag,required=True)
    p.add_argument('--execute-disposable',action='store_true');a=p.parse_args(argv)
    try:
        code=Campaign(a).run();print(json.dumps({'campaign_exit':code,'evidence_files':list(SAFE_FILES)}));return code
    except Exception:print(json.dumps({'campaign_exit':1,'code':'campaign_refused'}));return 1


if __name__=='__main__':raise SystemExit(main())
