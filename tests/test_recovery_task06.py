"""Task 06: synthetic data/keys only, isolated PostgreSQL 16, no provider or cloud."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import base64
import json
import os
import struct
import subprocess

import pytest
from sqlalchemy import select, text

from src.backup_set import crypto, engine as E, erasure as X, qualified as Q
from src.backup_set.admission import pending
from src.backup_set.fixture import build_synthetic_environment
from src.persistence import (AIUsageFact, AgentRunControl, AiBudgetControl, AiBudgetEntry, PreparationRun, User,
                             make_engine, make_session_factory)

# TEST FIXTURES ONLY: never operator keys, approvals, receipts or production limits.
KEY = b'b' * 32
LEDGER_KEY = b'l' * 32
MASTER = base64.b64encode(b'm' * 32).decode()
RELEASE = dict(application_sha='a'*40, manifest_sha256='b'*64, budget_policy_version=2, recovery_policy_version=1,
               migration_head='0048_agent_run_controls', prompt_assets_sha256='c'*64, language_activation_sha256='d'*64)


@pytest.fixture
def environment(tmp_path):
    if not os.environ.get('P5B_PG_ADMIN_URL'):
        pytest.skip('explicit isolated PostgreSQL 16 not configured')
    from tests.test_pg_05b import _create_db, _drop_db, _skip_reason
    assert _skip_reason() is None
    made=[]; engines=[]
    def database(label):
        name,url=_create_db('p5b_recovery_'+label);made.append(name)
        return url
    url=database('source')
    source=build_synthetic_environment(tmp_path/'source',use_alembic=True,database_url=url)
    engine=make_engine(url);engines.append(engine);sf=make_session_factory(engine)
    with sf() as s:
        users=list(s.scalars(select(User).order_by(User.id)))
        for user in users[:2]:
            rid='synthetic-recovery-run-'+str(user.id)
            s.add(PreparationRun(run_id=rid,owner_user_id=user.id))
            s.add(AgentRunControl(run_id=rid,owner_user_id=user.id,status='cancelled' if user.id == 2 else 'failed',settled=False,deadline_epoch=0))
            s.add(AIUsageFact(usage_key=rid,user_id=user.id,workflow='agent',operation='agent_run',model_calls=1,
                              input_tokens=11,output_tokens=None,total_tokens=None,cost_usd_micros=None,
                              cost_source='unavailable',token_coverage='partial',cost_coverage='unknown'))
        s.add_all([AiBudgetControl(scope_key='global',held_micro_usd=0,requests=0,killed=False),
                   AiBudgetControl(scope_key='class:production',held_micro_usd=200,requests=1,killed=False),
                   AiBudgetControl(scope_key='cat:production:agent',held_micro_usd=200,requests=1,killed=False)])
        s.add(AiBudgetEntry(created_ts=1,budget_class='production',category='agent',operation='agent',model='synthetic-only',
                            endpoint='chat',fingerprint='f'*64,state='unknown',reserved_micro_usd=200))
        s.commit()
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.checkpoint.base import empty_checkpoint
    with PostgresSaver.from_conn_string(url.replace('postgresql+psycopg://','postgresql://')) as saver:
        saver.setup()
        for uid in (1,2):
            cp=empty_checkpoint();cp['channel_values']={'user_id':str(uid),'synthetic_fixture':True}
            cp['channel_versions']={'user_id':'1','synthetic_fixture':'1'}
            saver.put({'configurable':{'thread_id':'synthetic-recovery-run-'+str(uid),'checkpoint_ns':''}},cp,
                      {'source':'input','step':0,'writes':{},'parents':{}},cp['channel_versions'])
    from src.secret_store import EncryptedDatabaseSecretStore
    EncryptedDatabaseSecretStore(sf,master_key=MASTER).set('OPENROUTER_API_KEY','synthetic-not-a-provider-credential',actor_user_id=None)
    ledger=X.Ledger(tmp_path/'independent-ledger'/'history.jsonl');ledger.path.parent.mkdir();ledger.path.touch()
    from types import SimpleNamespace
    env=SimpleNamespace(source=source,url=url,sf=sf,engine=engine,ledger=ledger,root=tmp_path,database=database)
    try:
        yield env
    finally:
        for e in engines:e.dispose()
        for name in reversed(made):_drop_db(name)


def backup(env,out=None,**kw):
    args=dict(out_dir=out or env.root/'set',checkpoint_database_url=env.url,release=RELEASE,ledger=env.ledger,
              ledger_head=X.signed_head(env.ledger,LEDGER_KEY),ledger_key=LEDGER_KEY,encryption_key=KEY,execute=True,
              drained=True,drain_observed_at=datetime.now(timezone.utc))
    args.update(kw)
    return Q.create(env.source,**args)


def restore(env,set_dir=None,**kw):
    source=set_dir or env.root/'set'
    args=dict(target_root=env.root/'restored',target_database_url=env.database('restore'),anchor=E.manifest_digest(source),
              ledger=env.ledger,ledger_head=X.signed_head(env.ledger,LEDGER_KEY),ledger_key=LEDGER_KEY,encryption_key=KEY,
              expected_release=RELEASE,execute=True)
    args.update(kw)
    return Q.restore(source,**args),args


def test_real_postgresql_encrypted_roundtrip_and_historical_accounting_hold(environment):
    e=environment
    before=[Q.file_tree(p) for p in (e.source.documents_dir,e.source.knowledge_files_dir,e.source.knowledge_index_dir)]
    r=backup(e);assert r.ok,r.codes
    m=E.load_manifest(e.root/'set')
    assert m['qualified_recovery']['checkpoint_placement']=='shared_public_database'
    assert m['retrieval_probe']['protected_file']=='evidence/retrieval-probe.json'
    assert 'Prioritisation frameworks' not in (e.root/'set'/'manifest.json').read_text()
    assert before==[Q.file_tree(p) for p in (e.source.documents_dir,e.source.knowledge_files_dir,e.source.knowledge_index_dir)]
    result,args=restore(e);assert result.ok,result.codes
    if os.environ.get('RECOVERY_TEST_EVIDENCE_DIR'):
        path=__import__('pathlib').Path(os.environ['RECOVERY_TEST_EVIDENCE_DIR']);path.mkdir(parents=True,exist_ok=True)
        (path/'synthetic-recovery.json').write_text(json.dumps(dict(kind='local_synthetic_postgresql16_working_tree',
            backup_seconds=r.details['duration_seconds'],restore_seconds=result.details['duration_seconds'],
            stored_bytes=r.details['stored_bytes'],postgres_client=r.details['postgres_client'],
            source_tables=m['database']['tables'],source_rows=sum(m['database']['row_counts'].values()),
            schema_revision=m['database']['schema_revision'],unknown_reservation_micro_usd=200,
            checkpoints=2,usage_facts=2,private_documents=4,knowledge_chunks=4,
            production_rto_rpo_approved=False),sort_keys=True))
    target=make_engine(args['target_database_url']);sf=make_session_factory(target)
    try:
        assert pending(sf)
        with sf() as s:
            assert s.scalar(select(AiBudgetControl.killed).where(AiBudgetControl.scope_key=='global')) is True
            assert s.scalar(select(AiBudgetEntry.reserved_micro_usd))==200
            assert s.scalar(select(AiBudgetEntry.committed_micro_usd))==0
            assert s.scalar(select(AIUsageFact.input_tokens).limit(1))==11
            assert s.scalar(select(AIUsageFact.output_tokens).limit(1)) is None
            assert s.execute(text('SELECT COUNT(*) FROM checkpoints')).scalar()==2
            with pytest.raises(Exception):
                s.execute(text("UPDATE audit_events SET action='tampered'"));s.commit()
        from src.llm.budget.ledger import DbBudgetLedger
        from src.llm.budget.errors import BudgetError
        with pytest.raises(BudgetError) as err:DbBudgetLedger(sf).resume()
        assert err.value.reason=='recovery_reconciliation_required'
        from src.agent.run_control import RunAdmissionConflict,RunControlStore
        with pytest.raises(RunAdmissionConflict):RunControlStore(sf).claim('synthetic-recovery-run-1','1',required=True)
        from src.secret_store import EncryptedDatabaseSecretStore
        assert EncryptedDatabaseSecretStore(sf,master_key=MASTER).get_for_runtime('OPENROUTER_API_KEY').get_secret_value()=='synthetic-not-a-provider-credential'
        assert (e.root/'restored'/'RECOVERY_VERIFIED.json').is_file()
    finally:target.dispose()


@pytest.mark.parametrize('problem',['separate-checkpoint','missing-docs','missing-knowledge','missing-index','no-drain','stale-drain'])
def test_incomplete_or_unfrozen_sources_are_refused(environment,problem):
    e=environment
    if problem=='separate-checkpoint':kw={'checkpoint_database_url':e.database('other')}
    elif problem=='no-drain':kw={'drained':False}
    elif problem=='stale-drain':kw={'drain_observed_at':datetime.now(timezone.utc)-timedelta(hours=1)}
    else:
        key={'missing-docs':'documents_dir','missing-knowledge':'knowledge_files_dir','missing-index':'knowledge_index_dir'}[problem]
        e.source=replace(e.source,**{key:e.root/'missing'})
        kw={}
    with pytest.raises(E.SetError):backup(e,**kw)
    assert not (e.root/'set'/'manifest.json').exists()


@pytest.mark.parametrize('problem',['wrong-key','no-key','corrupt-file','corrupt-manifest','inconsistent','unlisted','wrong-release'])
def test_corrupt_wrong_key_or_mismatched_recovery_is_never_promoted(environment,problem):
    e=environment;backup(e)
    if problem=='wrong-key':kw={'encryption_key':b'w'*32}
    elif problem=='no-key':kw={'encryption_key':None}
    elif problem=='wrong-release':kw={'expected_release':{**RELEASE,'application_sha':'e'*40}}
    else:
        m=E.load_manifest(e.root/'set')
        if problem=='corrupt-file':
            p=e.root/'set'/m['files'][m['database']['file']]['stored'];p.write_bytes(p.read_bytes()+b'tampered')
        elif problem=='unlisted':(e.root/'set'/'unexpected').write_bytes(b'synthetic')
        else:
            m['consistency']['consistent']=False if problem=='inconsistent' else True
            m['database']['tables']+=1
            (e.root/'set'/'manifest.json').write_text(json.dumps(m))
        kw={}
    with pytest.raises((E.SetError,crypto.CryptoError,TypeError)):restore(e,**kw)
    assert not (e.root/'restored'/'RECOVERY_VERIFIED.json').exists()


@pytest.mark.parametrize('problem',['missing','truncated','tampered','forged-prefix'])
def test_independent_erasure_history_cannot_be_dropped_or_rewritten(environment,problem):
    e=environment;backup(e)
    X.record_deletion(e.ledger,1,datetime.now(timezone.utc))
    trusted=X.signed_head(e.ledger,LEDGER_KEY)
    lines=e.ledger.path.read_text().splitlines()
    if problem=='missing':e.ledger.path.unlink()
    elif problem=='truncated':e.ledger.path.write_text(lines[0]+'\n')
    elif problem=='tampered':e.ledger.path.write_text(e.ledger.path.read_text().replace('"user_id": 1','"user_id": 2'))
    else:
        entries=[json.loads(l) for l in lines]
        entries[-1]['user_id']=2
        entries[-1]['entry_hash']=X.Ledger._hash(entries[-1]['prev_hash'],entries[-1])
        e.ledger.path.write_text('\n'.join(json.dumps(x) for x in entries)+'\n')
    with pytest.raises(X.ErasureError):restore(e,ledger_head=trusted)
    assert not (e.root/'restored').exists()


@pytest.mark.parametrize('when',['before','after'])
def test_deleted_account_is_not_resurrected_and_nonidentifying_money_survives(environment,when):
    e=environment
    if when=='before':
        from src.application.account_deletion_service import AccountDeletionService
        from src.documents.storage import LocalDocumentStore
        from src.privacy.preparation import PreparationRunIndex
        svc=AccountDeletionService(e.sf,document_store=LocalDocumentStore(str(e.source.documents_dir)),
                                   agent_service=X._PostgresCheckpointPurger(e.url),preparation_index=PreparationRunIndex(e.sf))
        svc.delete_account(1)
        X.record_deletion(e.ledger,1,datetime.now(timezone.utc))
    backup(e)
    if when=='after':X.record_deletion(e.ledger,1,datetime.now(timezone.utc))
    outcome,args=restore(e);assert outcome.ok
    engine=make_engine(args['target_database_url'])
    try:
        with engine.connect() as c:
            assert c.execute(text('SELECT COUNT(*) FROM users WHERE id=1')).scalar()==0
            assert c.execute(text("SELECT COUNT(*) FROM checkpoints WHERE thread_id='synthetic-recovery-run-1'")).scalar()==0
            assert c.execute(text('SELECT COUNT(*) FROM preparation_runs WHERE owner_user_id=1')).scalar()==0
            assert c.execute(text('SELECT COUNT(*) FROM ai_usage_facts WHERE user_id=1')).scalar()==0
            assert c.execute(text("SELECT held_micro_usd FROM ai_budget_controls WHERE scope_key='class:production'")).scalar()==200
            assert c.execute(text('SELECT COUNT(*) FROM ai_budget_entries')).scalar()==1
            assert c.execute(text('SELECT COUNT(*) FROM users WHERE id=2')).scalar()==1
        assert len(list((e.root/'restored'/'documents').iterdir()))==2
    finally:engine.dispose()


def test_verified_independent_transfer_and_no_overwrites(environment):
    e=environment;backup(e)
    out=e.root/'independent-destination'/'set'
    r=Q.transfer(e.root/'set',out,anchor=E.manifest_digest(e.root/'set'),encryption_key=KEY,execute=True)
    assert r.ok and r.details['verified']
    with pytest.raises(E.SetError):backup(e)
    with pytest.raises(E.SetError):Q.transfer(e.root/'set',out,anchor=E.manifest_digest(e.root/'set'),encryption_key=KEY,execute=True)
    restored,args=restore(e,set_dir=out);assert restored.ok
    with pytest.raises(E.SetError):restore(e,target_root=e.root/'again',target_database_url=args['target_database_url'])
    assert E.verify_set(e.root/'set',encryption_key=KEY,require_signature=True).ok


def test_partial_file_restore_failure_leaves_target_quarantined(environment,monkeypatch):
    e=environment;backup(e)
    original=E._materialise
    def fail(base,manifest,logical,*args,**kw):
        if logical.startswith('documents/'):raise E.SetError('synthetic_file_failure')
        return original(base,manifest,logical,*args,**kw)
    monkeypatch.setattr(E,'_materialise',fail)
    url=e.database('restore')
    with pytest.raises(E.SetError):restore(e,target_database_url=url)
    engine=make_engine(url)
    try:assert pending(make_session_factory(engine))
    finally:engine.dispose()
    assert (e.root/'restored'/'RECOVERY_PENDING.json').exists() and not (e.root/'restored'/'RECOVERY_VERIFIED.json').exists()
    assert E.verify_set(e.root/'set',encryption_key=KEY,require_signature=True).ok


def test_legacy_restore_cannot_use_force_in_hosted_mode():
    result=subprocess.run(['bash','deploy/scripts/restore.sh'],env={**os.environ,'API_ENV':'staging','FORCE':'1'},capture_output=True,text=True)
    assert result.returncode!=0 and 'legacy destructive restore' in result.stderr


def test_sealed_oversized_chunk_is_refused_without_allocation(tmp_path):
    p=tmp_path/'bad';p.write_bytes(crypto.MAGIC+b'0'*8+struct.pack('>I',2**32-1))
    with pytest.raises(crypto.CryptoError):list(crypto.open_sealed(p,KEY,set_id='synthetic',logical='synthetic'))


def test_postgresql_erasure_rewrite_produces_new_sealed_set_and_retains_original(environment):
    e=environment;backup(e);original=E.manifest_digest(e.root/'set')
    X.record_deletion(e.ledger,1,datetime.now(timezone.utc))
    result=Q.rewrite(e.root/'set',out_dir=e.root/'rewritten',target_root=e.root/'rewrite-scratch',
        target_database_url=e.database('rewrite_restore'),anchor=original,ledger=e.ledger,
        ledger_head=X.signed_head(e.ledger,LEDGER_KEY),ledger_key=LEDGER_KEY,encryption_key=KEY,
        expected_release=RELEASE,execute=True)
    assert result.ok and result.details['original_destroyed'] is False
    assert E.manifest_digest(e.root/'set')==original
    assert E.load_manifest(e.root/'rewritten')['rewrites']['erased_user_ids']==[1]
    restored,args=restore(e,set_dir=e.root/'rewritten',target_root=e.root/'rewritten-restore')
    assert restored.ok
    engine=make_engine(args['target_database_url'])
    try:
        with engine.connect() as c:
            assert c.execute(text('SELECT count(*) FROM users WHERE id=1')).scalar()==0
            assert c.execute(text('SELECT count(*) FROM checkpoints')).scalar()==1
        assert Q.money_fingerprint(args['target_database_url'])==Q.money_fingerprint(e.url)
    finally:engine.dispose()


def test_database_outage_refuses_without_publishing_a_set(environment):
    e=environment
    from sqlalchemy.engine import make_url
    url=make_url(e.url).set(port=1).update_query_dict({'connect_timeout':'1'}).render_as_string(hide_password=False)
    e.source=replace(e.source,database_url=url)
    with pytest.raises(Exception):backup(e,checkpoint_database_url=url)
    assert not (e.root/'set'/'manifest.json').exists()


def test_dry_run_never_creates_targets_or_changes_source(environment):
    e=environment
    before=X.signed_head(e.ledger,LEDGER_KEY)
    result=backup(e,execute=False)
    assert result.ok and not (e.root/'set').exists() and X.signed_head(e.ledger,LEDGER_KEY)==before
    backup(e)
    result,args=restore(e,execute=False)
    assert result.ok and not (e.root/'restored').exists()
    assert not pending(make_session_factory(make_engine(args['target_database_url'])))


def test_recovery_quarantine_blocks_private_api_and_queued_worker_jobs(environment):
    e=environment;backup(e);_,args=restore(e)
    engine=make_engine(args['target_database_url']);sf=make_session_factory(engine)
    try:
        from src.jobs.service import JobService
        from tests.test_pg_05b import _job_types
        jobs=JobService(sf,_job_types())
        jobs.enqueue('t',{'n':'synthetic'})
        assert jobs.claim('synthetic-worker') is None
        from src.api import dependencies as D
        from types import SimpleNamespace
        from fastapi import HTTPException
        from unittest.mock import patch
        with patch.object(D,'_shared',return_value=SimpleNamespace(session_factory=sf)):
            with pytest.raises(HTTPException) as error:D.get_repository(SimpleNamespace())
        assert error.value.status_code==503 and error.value.detail['code']=='recovery_reconciliation_required'
    finally:engine.dispose()


def test_controlled_older_revision_upgrade_requires_explicit_flag_on_new_target(environment):
    e=environment
    old_url=e.database('old_source')
    e.source=build_synthetic_environment(e.root/'older',use_alembic=True,database_url=old_url,
                                        migration_revision='0047_workspace_ownership_transfers')
    e.url=old_url
    backup(e)
    with pytest.raises(E.SetError,match='controlled_upgrade_required'):restore(e)
    result,args=restore(e,upgrade_to_head=True)
    assert result.ok and E.schema_revision(old_url)=='0047_workspace_ownership_transfers'
    assert E.schema_revision(args['target_database_url'])=='0048_agent_run_controls'
    assert pending(make_session_factory(make_engine(args['target_database_url'])))


def test_new_deletion_during_reapply_invalidates_receipt_and_keeps_hold(environment,monkeypatch):
    e=environment;backup(e)
    original=X.reapply_postgresql
    def concurrent(*args,**kw):
        result=original(*args,**kw)
        X.record_deletion(e.ledger,2,datetime.now(timezone.utc))
        return result
    monkeypatch.setattr(X,'reapply_postgresql',concurrent)
    with pytest.raises(E.SetError,match='recovery_failed_target_quarantined'):restore(e)
    assert not (e.root/'restored'/'RECOVERY_VERIFIED.json').exists()


def test_exact_operator_cli_roundtrip_uses_only_explicit_private_environment(environment,monkeypatch,capsys):
    from scripts.backup_set import main
    from scripts import release_images as R
    e=environment
    release=e.root/'reviewed-release.json';release.write_text(json.dumps(RELEASE))
    head=e.root/'current-head.json';head.write_text(json.dumps(X.signed_head(e.ledger,LEDGER_KEY)))
    values=dict(RECOVERY_RELEASE_FILE=str(release),RECOVERY_RELEASE_SHA256=R.digest(R.canonical(RELEASE)),APP_GIT_SHA=RELEASE['application_sha'],
        DATABASE_URL=e.url,AGENT_CHECKPOINT_DATABASE_URL=e.url,DOCUMENT_STORAGE_DIR=str(e.source.documents_dir),
        KNOWLEDGE_STORAGE_DIR=str(e.source.knowledge_files_dir),RECOVERY_INDEX_DIR=str(e.source.knowledge_index_dir),
        ERASURE_LEDGER_FILE=str(e.ledger.path),ERASURE_LEDGER_HEAD_FILE=str(head),
        BACKUP_ENCRYPTION_KEY=base64.b64encode(KEY).decode(),BACKUP_ERASURE_LEDGER_KEY=base64.b64encode(LEDGER_KEY).decode())
    for key,value in values.items():monkeypatch.setenv(key,value)
    assert main(['qualified','backup','--out',str(e.root/'cli-set'),'--attest-drained-at',datetime.now(timezone.utc).isoformat(),'--execute'])==0
    result=json.loads(capsys.readouterr().out);head.write_text(json.dumps(result['details']['erasure_head']))
    monkeypatch.setenv('TARGET_DATABASE_URL',e.database('cli_restore'))
    assert main(['qualified','restore','--set',str(e.root/'cli-set'),'--manifest-sha256',E.manifest_digest(e.root/'cli-set'),
                 '--target-root',str(e.root/'cli-target'),'--execute'])==0
    output=capsys.readouterr().out
    assert json.loads(output)['details']['recovery_hold'] is True
    assert e.url not in output and 'synthetic-not-a-provider-credential' not in output and base64.b64encode(KEY).decode() not in output
