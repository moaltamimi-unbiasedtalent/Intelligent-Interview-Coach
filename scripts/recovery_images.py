"""Narrow, offline operator derivative of a verified immutable release.

No publication, deployment, data mounting or execution is done by build/verify.
The generated Compose profile is plan-only and disabled during ordinary startup.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
import uuid
from scripts import release_images as R


def facts(manifest, anchor):
    source = manifest['source']
    R.require(source.get('recovery_policy_version') == 1 and source.get('budget_policy_version') == 2, 'recovery_policy_incapable_image')
    return dict(application_sha=manifest['application_sha'], manifest_sha256=anchor, budget_policy_version=2, recovery_policy_version=1,
                migration_head=source['migration_chain'][-1], prompt_assets_sha256=R.digest(R.canonical(source['prompt_files'])),
                language_activation_sha256=source['language_activation_sha256'])


def inspect_runner(image, manifest, anchor):
    R.require(isinstance(image,str) and R.DIGEST.fullmatch(image), 'runner_image_invalid')
    info = json.loads(R.run(['docker','image','inspect',image]))[0]
    config = info['Config'];labels=config.get('Labels') or {}; env=dict(v.split('=',1) for v in config.get('Env',[]) if '=' in v)
    parent=json.loads(R.run(['docker','image','inspect',manifest['images']['application']['image_id']]))[0]
    layers=parent['RootFS']['Layers']
    R.require(layers and info['RootFS']['Layers'][:len(layers)]==layers,'runner_not_derived_from_application')
    R.require(config.get('Cmd')==['python','scripts/backup_set.py','qualified','--help'] and
              env.get('APP_BUILD_TIME')==manifest['build_started_at'] and labels.get('org.opencontainers.image.created')==manifest['build_started_at'], 'runner_command_mismatch')
    R.require(info['Id']==image and config.get('User')=='appuser' and config.get('WorkingDir')=='/app' and not config.get('Entrypoint'), 'runner_security_mismatch')
    R.require(labels.get('io.ask4mo.operator')=='recovery-v1' and labels.get('io.ask4mo.application.image')==manifest['images']['application']['image_id'], 'runner_parent_mismatch')
    R.require(labels.get('org.opencontainers.image.revision')==manifest['application_sha'] and labels.get('io.ask4mo.source.sha256')==R.digest(R.canonical(manifest['source'])), 'runner_source_mismatch')
    R.require(env.get('APP_GIT_SHA')==manifest['application_sha'] and not any(env.get(k) for k in ('DATABASE_URL','TARGET_DATABASE_URL','BACKUP_ENCRYPTION_KEY','BACKUP_SIGNING_KEY','SECRET_STORE_MASTER_KEY','OPENROUTER_API_KEY','BACKUP_ERASURE_LEDGER_KEY')), 'runner_runtime_secret')
    command=['docker','run','--rm','-i','--pull','never','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',image]
    proof=json.loads(R.run([*command,'python','-c',R.API_PROBE],input=R.canonical(list(manifest['source']['api_files']))))
    R.require(proof.pop('files')==manifest['source']['api_files'] and proof['uid']==10001, 'runner_contents_mismatch')
    R.require(proof['dependencies']==manifest['images']['application']['contents']['dependencies'] and proof['runtime']==manifest['images']['application']['contents']['runtime'], 'runner_dependencies_mismatch')
    versions=[]
    for binary in ('pg_dump','pg_restore'):
        version=R.run([*command,binary,'--version']).decode().strip()
        R.require('PostgreSQL) 16.' in version, 'runner_pg16_required');versions.append(version)
    return dict(version=1, release=facts(manifest,anchor), application_image_id=manifest['images']['application']['image_id'],
                operator_image_id=image, platform=info['Os']+'/'+info['Architecture'], postgres_clients=versions,
                qualification='image contents and clients only; recovery drills required separately')


def validate(record, record_anchor, manifest, anchor, *, images=True):
    R.require(R.digest(R.canonical(record))==record_anchor, 'runner_anchor_mismatch')
    R.keys(record,'version release application_image_id operator_image_id platform postgres_clients qualification')
    R.require(record['version']==1 and record['release']==facts(manifest,anchor) and record['application_image_id']==manifest['images']['application']['image_id'], 'runner_release_mismatch')
    R.require(record['platform']==manifest['images']['application']['platform'], 'runner_platform_mismatch')
    if images:
        R.require(inspect_runner(record['operator_image_id'],manifest,anchor)==record, 'runner_record_mismatch')
    return record


def build(manifest, sha, anchor, out):
    R.validate_manifest(manifest,sha,anchor)
    output=R.new_directory(out); tag='ask4mo-recovery:'+sha+'-'+uuid.uuid4().hex[:8]
    base_tag='ask4mo-recovery-base:'+uuid.uuid4().hex
    R.run(['docker','image','tag',manifest['images']['application']['image_id'],base_tag])
    with R.committed_source(sha) as root:
        arguments=['docker','build','--file',str(root/'deploy/Dockerfile.recovery'),'--tag',tag,
                   '--build-arg','API_IMAGE='+base_tag,
                   '--build-arg','APPLICATION_IMAGE_ID='+manifest['images']['application']['image_id'],str(root)]
        # Only a committed, secret-free context and public image identities enter
        # this build. Retain stderr as well as stdout on failure for qualification.
        with (output/'recovery-build.log').open('wb') as log:
            built=subprocess.run(arguments,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
        R.require(built.returncode==0,'recovery_image_build_failed')
    image=json.loads(R.run(['docker','image','inspect',tag]))[0]['Id']
    record=inspect_runner(image,manifest,anchor)
    R.write_json(output/'recovery.json',record)
    digest=R.digest(R.canonical(record));(output/'recovery.sha256').write_text(digest+'\n')
    R.write_json(output/'recovery-release.json',facts(manifest,anchor))
    return dict(operator_image_id=image, runner_sha256=digest)


def profile(record, operation, env_file, mounts, *, network_name=None):
    # Paths are operator review input, not secret values. No Docker socket,
    # automatic migration, network service or normal-startup dependency allowed.
    R.require(operation in ('backup','verify','restore','transfer','rewrite'), 'recovery_operation_invalid')
    R.require(Path(env_file).is_absolute(), 'private_env_absolute_required')
    targets={'/source/documents','/source/knowledge','/source/index','/backup','/destination','/target','/ledger','/anchors','/keys','/release'}
    R.require(isinstance(mounts,list) and len({m.get('target') for m in mounts})==len(mounts), 'recovery_mounts_invalid')
    for mount in mounts:
        R.keys(mount,'type source target read_only bind')
        R.require(not str(mount['source']).endswith(('.sock','/docker.sock')), 'recovery_socket_mount_refused')
        R.require(mount['type']=='bind' and Path(mount['source']).is_absolute() and mount['target'] in targets and type(mount['read_only']) is bool and mount['bind']=={'create_host_path':False}, 'recovery_mount_invalid')
        if mount['target'].startswith('/source/') or mount['target'] in ('/keys','/anchors','/release') or (mount['target']=='/backup' and operation!='backup'):
            R.require(mount['read_only'], 'recovery_source_must_be_read_only')
    present={m['target'] for m in mounts}
    R.require({'/backup','/keys','/release'}<=present,'recovery_mounts_incomplete')
    if operation in ('backup','restore','rewrite'):R.require({'/ledger','/anchors'}<=present,'recovery_mounts_incomplete')
    if operation=='backup':R.require({'/source/documents','/source/knowledge','/source/index'}<=present,'recovery_mounts_incomplete')
    if operation in ('restore','rewrite'):R.require('/target' in present,'recovery_mounts_incomplete')
    if operation in ('transfer','rewrite'):R.require('/destination' in present,'recovery_mounts_incomplete')
    for i,m in enumerate(mounts):
        for other in mounts[i+1:]:
            a,b=Path(m['source']).resolve(),Path(other['source']).resolve()
            R.require(not a.is_relative_to(b) and not b.is_relative_to(a),'recovery_mounts_overlap')
    config = dict(name='ask4mo-recovery',services={'recovery':dict(image=record['operator_image_id'],pull_policy='never',profiles=['recovery'],
        restart='no',user='10001:10001',read_only=True,cap_drop=['ALL'],security_opt=['no-new-privileges:true'],
        tmpfs=['/tmp:rw,nosuid,noexec,size=536870912'],env_file=[str(env_file)],
        environment={'PYTHON_DOTENV_DISABLED':'1','ASK4MO_PROVIDER_MODE':'offline','AI_BUDGET_KILL':'true',
                     'RECOVERY_RELEASE_FILE':'/release/recovery-release.json','RECOVERY_RELEASE_SHA256':R.digest(R.canonical(record['release'])),
                     'BACKUP_ENCRYPTION_KEY_FILE':'/keys/encryption','BACKUP_ERASURE_LEDGER_KEY_FILE':'/keys/erasure',
                     'ERASURE_LEDGER_FILE':'/ledger/history.jsonl','ERASURE_LEDGER_HEAD_FILE':'/anchors/head.json',
                     'DOCUMENT_STORAGE_DIR':'/source/documents','KNOWLEDGE_STORAGE_DIR':'/source/knowledge','RECOVERY_INDEX_DIR':'/source/index'},
        volumes=mounts,command=['python','scripts/backup_set.py','qualified',operation,'--help'])})
    service=config['services']['recovery']
    if operation in ('backup','restore','rewrite'):
        import re
        R.require(isinstance(network_name,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',network_name)
                  and network_name not in ('host','bridge','none'), 'reviewed_recovery_network_required')
        config['networks']={'recovery_database':{'external':True,'name':network_name}}
        service['networks']=['recovery_database']
    else:
        service['network_mode']='none'
    return config


def dispatch(args, manifest):
    if args.command=='build-recovery':return build(manifest,args.expected_sha,args.manifest_sha256,args.out)
    R.validate_manifest(manifest,args.expected_sha,args.manifest_sha256)
    record=R.decode_json(Path(args.runner).read_text());validate(record,args.runner_sha256,manifest,args.manifest_sha256)
    if args.command=='verify-recovery':return {'verified':True,'operator_image_id':record['operator_image_id']}
    config=profile(record,args.operation,args.env_file,R.decode_json(Path(args.mounts).read_text()),network_name=args.network)
    R.write_json(args.out,config) # JSON is valid Compose YAML; never starts a container.
    return {'profile_prepared':True,'execution':'explicit operator command required; default is help'}
