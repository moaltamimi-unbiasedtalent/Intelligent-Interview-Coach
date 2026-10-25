#!/usr/bin/env python3
"""Explicit disposable PG16 drill inside the actually built operator image.

Only the fixed local synthetic test account/database is accepted. Creates and
removes only its own fresh databases; no provider, deployment or live keys.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from src.backup_set import engine as E, erasure as X, qualified as Q  # noqa: E402
from src.backup_set.fixture import build_synthetic_environment  # noqa: E402
from src.backup_set.rollback import _seed_agent_run_controls  # noqa: E402


def run():
    url=make_url(os.environ['P5B_PG_ADMIN_URL'])
    Q.require(url.get_backend_name()=='postgresql' and url.host in ('127.0.0.1','localhost') and url.database=='p5b_test'
              and url.username=='disposable' and url.password=='synthetic-test-only' and not url.query,'explicit_disposable_database_required')
    names=['p5b_recovery_image_source_'+uuid.uuid4().hex[:10],'p5b_recovery_image_restore_'+uuid.uuid4().hex[:10]]
    admin=create_engine(url,isolation_level='AUTOCOMMIT');made=[]
    try:
        for name in names:
            with admin.connect() as c:c.execute(text('CREATE DATABASE '+E._check_ident(name)))
            made.append(name)
        urls=[url.set(database=name).render_as_string(hide_password=False) for name in names]
        with tempfile.TemporaryDirectory(prefix='ask4mo-image-recovery-') as work:
            root=Path(work);source=build_synthetic_environment(root/'source',use_alembic=True,database_url=urls[0])
            _seed_agent_run_controls(urls[0])
            from langgraph.checkpoint.postgres import PostgresSaver
            from langgraph.checkpoint.base import empty_checkpoint
            with PostgresSaver.from_conn_string(urls[0].replace('postgresql+psycopg://','postgresql://')) as saver:
                saver.setup();cp=empty_checkpoint()
                saver.put({'configurable':{'thread_id':'rollback-protected-run','checkpoint_ns':''}},cp,
                          {'source':'input','step':0,'writes':{},'parents':{}},{})
            ledger=X.Ledger(root/'independent-ledger.jsonl');ledger.path.touch()
            release=json.loads(Path(os.environ['RECOVERY_RELEASE_FILE']).read_text())
            Q.require(release['application_sha']==os.environ['APP_GIT_SHA'],'recovery_application_sha_mismatch')
            # Synthetic fixture keys only. This command never generates operator keys.
            key=b'i'*32;ledger_key=b'e'*32
            backup=Q.create(source,out_dir=root/'sealed',checkpoint_database_url=urls[0],release=release,ledger=ledger,
                            ledger_head=X.signed_head(ledger,ledger_key),ledger_key=ledger_key,encryption_key=key,
                            execute=True,drained=True,drain_observed_at=datetime.now(timezone.utc))
            X.record_deletion(ledger,1,datetime.now(timezone.utc))
            restored=Q.restore(root/'sealed',target_root=root/'target',target_database_url=urls[1],anchor=E.manifest_digest(root/'sealed'),
                               ledger=ledger,ledger_head=X.signed_head(ledger,ledger_key),ledger_key=ledger_key,encryption_key=key,
                               expected_release=release,execute=True)
            Q.require(backup.ok and restored.ok,'image_recovery_drill_failed')
            return dict(ok=True,kind='synthetic_actual_operator_image',application_sha=release['application_sha'],
                        backup_seconds=backup.details['duration_seconds'],restore_seconds=restored.details['duration_seconds'],
                        stored_bytes=backup.details['stored_bytes'],erasure=restored.details['erasure'],
                        database_hold=True,production_rto_rpo_approved=False)
    finally:
        for name in reversed(made):
            with admin.connect() as c:
                c.execute(text('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name AND pid!=pg_backend_pid()'),{'name':name})
                c.execute(text('DROP DATABASE '+E._check_ident(name)))
        admin.dispose()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute-disposable',required=True,action='store_true');parser.parse_args()
    try:print(json.dumps(run(),sort_keys=True))
    except Exception:print(json.dumps({'ok':False,'code':'disposable_image_recovery_failed'}));sys.exit(1)
