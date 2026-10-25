"""Operator runner/profiles: no real keys, private state or service activation."""
import base64
import json
import os
from pathlib import Path
import subprocess
import pytest
from scripts import release_images as R, recovery_images as I
from src.backup_set import engine as E, operator as O


def mounts(tmp_path):
    targets=('/source/documents','/source/knowledge','/source/index','/backup','/destination','/target','/ledger','/anchors','/keys','/release')
    return [dict(type='bind',source=str(tmp_path/str(n)),target=t,read_only=t.startswith('/source/') or t in ('/keys','/anchors','/release'),
                 bind={'create_host_path':False}) for n,t in enumerate(targets)]


@pytest.mark.parametrize('operation',['backup','verify','restore','transfer','rewrite'])
def test_recovery_profile_is_manual_one_shot_and_never_runs_normal_services(tmp_path,operation):
    record={'operator_image_id':'sha256:'+'e'*64,'release':{'synthetic':True}}
    bindings=mounts(tmp_path)
    if operation!='backup':next(m for m in bindings if m['target']=='/backup')['read_only']=True
    p=I.profile(record,operation,tmp_path/'operator.env',bindings,network_name='synthetic-recovery-test')
    assert set(p['services'])=={'recovery'}
    s=p['services']['recovery']
    assert s['profiles']==['recovery'] and s['restart']=='no' and s['read_only'] is True
    assert s['image']==record['operator_image_id'] and s['user']=='10001:10001'
    assert s['command'][-1]=='--help' and '--execute' not in s['command']
    assert s['environment']['AI_BUDGET_KILL']=='true' and 'DATABASE_URL' not in s['environment']
    assert s['cap_drop']==['ALL'] and 'ports' not in s and 'depends_on' not in s


@pytest.mark.parametrize('problem',['writable-source','socket','overlap','auto-create','missing'])
def test_recovery_profile_refuses_unsafe_or_incomplete_mounts(tmp_path,problem):
    bindings=mounts(tmp_path)
    if problem=='writable-source':bindings[0]['read_only']=False
    elif problem=='socket':bindings[0]['target']='/var/run/docker.sock'
    elif problem=='overlap':bindings[1]['source']=bindings[0]['source']+'/nested'
    elif problem=='auto-create':bindings[0]['bind']={'create_host_path':True}
    else:bindings.pop(0)
    with pytest.raises(R.ReleaseError):I.profile({'operator_image_id':'sha256:'+'e'*64,'release':{}},'backup',tmp_path/'private.env',bindings,network_name='synthetic-recovery-test')


def test_key_file_permissions_and_symlinks_refuse_without_key_output(tmp_path,monkeypatch):
    path=tmp_path/'key';path.write_bytes(base64.b64encode(b's'*32));path.chmod(0o600)
    monkeypatch.setenv('BACKUP_ENCRYPTION_KEY_FILE',str(path))
    assert O.private_key('BACKUP_ENCRYPTION_KEY')==b's'*32
    path.chmod(0o644)
    with pytest.raises(E.SetError,match='private_key_file_refused'):O.private_key('BACKUP_ENCRYPTION_KEY')
    link=tmp_path/'link';link.symlink_to(path);monkeypatch.setenv('BACKUP_ENCRYPTION_KEY_FILE',str(link))
    with pytest.raises(OSError):O.private_key('BACKUP_ENCRYPTION_KEY')


def test_release_binding_refuses_wrong_code_or_anchor(tmp_path,monkeypatch):
    path=tmp_path/'release.json';facts={'application_sha':'a'*40};path.write_text(json.dumps(facts))
    monkeypatch.setenv('RECOVERY_RELEASE_FILE',str(path));monkeypatch.setenv('RECOVERY_RELEASE_SHA256',R.digest(R.canonical(facts)))
    monkeypatch.setenv('APP_GIT_SHA','b'*40)
    with pytest.raises(E.SetError,match='recovery_application_sha_mismatch'):O.release()
    monkeypatch.setenv('APP_GIT_SHA','a'*40);assert O.release()==facts
    monkeypatch.setenv('RECOVERY_RELEASE_SHA256','f'*64)
    with pytest.raises(E.SetError,match='recovery_release_anchor_mismatch'):O.release()


def test_cli_failures_never_echo_credentials_or_private_paths(capsys,monkeypatch):
    from scripts.backup_set import main
    monkeypatch.setenv('BACKUP_ENCRYPTION_KEY','synthetic-invalid-key')
    assert main(['qualified','verify','--set','/private/synthetic-candidate','--manifest-sha256','f'*64])==1
    output=capsys.readouterr().out
    assert 'synthetic-invalid-key' not in output and 'synthetic-candidate' not in output and '"ok": false' in output


def test_actual_built_recovery_image_and_compose_resolution(tmp_path):
    if os.environ.get('RUN_RECOVERY_IMAGE_TESTS')!='1':pytest.skip('explicit actually-built operator image qualification required')
    release_dir=Path(os.environ['RELEASE_TEST_BUNDLE']);runner_dir=Path(os.environ['RECOVERY_TEST_BUNDLE'])
    manifest=R.decode_json((release_dir/'release.json').read_text());anchor=(release_dir/'release.sha256').read_text().strip()
    R.validate_manifest(manifest,manifest['application_sha'],anchor)
    record=R.decode_json((runner_dir/'recovery.json').read_text());runner_anchor=(runner_dir/'recovery.sha256').read_text().strip()
    I.validate(record,runner_anchor,manifest,anchor)
    env=tmp_path/'operator.env';env.write_text('PYTHON_DOTENV_DISABLED=1\n');env.chmod(0o600)
    config=I.profile(record,'backup',env,mounts(tmp_path),network_name='synthetic-recovery-test')
    path=tmp_path/'compose.json';path.write_text(json.dumps(config))
    resolved=json.loads(R.run(['docker','compose','-f',str(path),'--profile','recovery','config','--format','json']))
    service=resolved['services']['recovery']
    assert service['image']==record['operator_image_id'] and service['read_only'] and service['pull_policy']=='never'
    assert service['profiles']==['recovery'] and service['command'][-1]=='--help'
    assert resolved['networks']['recovery_database']['external'] is True
    image=record['operator_image_id']
    command=['docker','run','--rm','--pull','never','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',image]
    assert b'qualified' in subprocess.check_output([*command,'python','scripts/backup_set.py','--help'])
    proof=R.run([*command,'python','-c',"from pathlib import Path; from src.backup_set.admission import RECOVERY_POLICY_VERSION; from src.llm.budget.governor import HOSTED_POLICY_VERSION; from src.agent.run_control import RunControlStore; from langgraph.checkpoint.postgres import PostgresSaver; assert RECOVERY_POLICY_VERSION==1 and HOSTED_POLICY_VERSION==2 and Path('scripts/migrate.sh').is_file(); print('verified')"])
    assert proof.strip()==b'verified'

    # Linux CI only: the isolated test PostgreSQL service is reached over the
    # job's loopback port. No Docker socket or source/private volume is mounted.
    release_file=runner_dir/'recovery-release.json'
    result=R.run(['docker','run','--rm','--pull','never','--network','host','--read-only','--cap-drop','ALL',
                  '--security-opt','no-new-privileges','--tmpfs','/tmp:rw,nosuid,noexec,size=536870912',
                  '--mount','type=bind,src='+str(release_file)+',dst=/release.json,readonly',
                  '-e','PYTHON_DOTENV_DISABLED=1','-e','P5B_PG_ADMIN_URL='+os.environ['P5B_PG_ADMIN_URL'],
                  '-e','RECOVERY_RELEASE_FILE=/release.json',image,'python','scripts/qualify_recovery.py','--execute-disposable'],timeout=600)
    evidence=json.loads(result)
    assert evidence['ok'] and evidence['database_hold'] and evidence['erasure']['accounts_erased']==1
    assert evidence['production_rto_rpo_approved'] is False
    (tmp_path/'synthetic-image-recovery.json').write_text(json.dumps(evidence))


@pytest.mark.parametrize('network',[None,'host','bridge','unsafe/network'])
def test_operator_database_network_must_be_explicit_reviewed_and_external(tmp_path,network):
    with pytest.raises(R.ReleaseError,match='reviewed_recovery_network_required'):
        I.profile({'operator_image_id':'sha256:'+'e'*64,'release':{}},'backup',tmp_path/'private.env',mounts(tmp_path),network_name=network)
