"""Credential-free CLI arguments; read mounted keys only at execution time.

No dotenv, API factory, provider client, scheduler or account-access service starts.
"""
from __future__ import annotations
from datetime import datetime
import json
import os
from pathlib import Path
import stat
from src.backup_set import crypto, engine as E, erasure as X, qualified as Q


def private_key(name):
    filename=os.environ.get(name+'_FILE')
    if not filename:
        return crypto.key_from_env(name)
    fd=os.open(filename,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        info=os.fstat(fd)
        Q.require(stat.S_ISREG(info.st_mode) and not (info.st_mode & 0o077) and info.st_size<=1024,'private_key_file_refused')
        value=os.read(fd,1025).decode().strip()
    finally:os.close(fd)
    import base64
    try:key=base64.b64decode(value,validate=True)
    except Exception:raise E.SetError('encryption_key_invalid') from None
    Q.require(len(key)==32,'encryption_key_invalid')
    return key


def release():
    path=Path(os.environ['RECOVERY_RELEASE_FILE'])
    from scripts import release_images as R
    facts=R.decode_json(path.read_text())
    Q.require(R.digest(R.canonical(facts))==os.environ['RECOVERY_RELEASE_SHA256'],'recovery_release_anchor_mismatch')
    Q.require(facts['application_sha']==os.environ['APP_GIT_SHA'],'recovery_application_sha_mismatch')
    return facts


def source_from_environment():
    from src.copilot.index_manifest import read_manifest, manifest_file
    from src.knowledge_admin.contracts import RuntimeIdentity, EmbeddingState, database_fingerprint, data_root_identity
    from src.knowledge_admin.policy import COLLECTION
    url=os.environ['DATABASE_URL'];root=Path(os.environ['RECOVERY_INDEX_DIR'])
    m=read_manifest(manifest_file(root,COLLECTION))
    embedding=EmbeddingState() if m is None else EmbeddingState(m.provider,m.model,m.dimensions,m.degraded,m.degradation_reason)
    identity=RuntimeIdentity(database_fingerprint(url),data_root_identity(str(root)),embedding=embedding)
    return E.Source(database_url=url,documents_dir=Path(os.environ['DOCUMENT_STORAGE_DIR']),
                    knowledge_files_dir=Path(os.environ['KNOWLEDGE_STORAGE_DIR']),knowledge_index_dir=root,identity=identity)


def run(a):
    enc=private_key('BACKUP_ENCRYPTION_KEY')
    sig=private_key('BACKUP_SIGNING_KEY') if os.environ.get('BACKUP_SIGNING_KEY') or os.environ.get('BACKUP_SIGNING_KEY_FILE') else None
    facts=release()
    keys=dict(encryption_key=enc,signing_key=sig)
    name=a.qualified_cmd
    if name=='verify':
        m=Q.verify(a.set,anchor=a.manifest_sha256,**keys)
        Q.require(m[Q.QUALIFIED]['release']==facts,'recovery_release_mismatch')
        return {'action':'qualified_verify','ok':True,'manifest_sha256':a.manifest_sha256}
    if name=='transfer':
        m=Q.verify(a.set,anchor=a.manifest_sha256,**keys)
        Q.require(m[Q.QUALIFIED]['release']==facts,'recovery_release_mismatch')
        return Q.transfer(a.set,a.destination,anchor=a.manifest_sha256,execute=a.execute,**keys).to_dict()
    ledger=X.Ledger(os.environ['ERASURE_LEDGER_FILE']);head=Path(os.environ['ERASURE_LEDGER_HEAD_FILE'])
    Q.require(not E._is_inside(head,Path(getattr(a,'set',getattr(a,'out','/nonexistent')))),'erasure_head_must_be_independent')
    history=dict(ledger=ledger,ledger_head=json.loads(head.read_text()),ledger_key=private_key('BACKUP_ERASURE_LEDGER_KEY'))
    if name=='backup':
        source=source_from_environment()
        checkpoint=os.environ.get('AGENT_CHECKPOINT_DATABASE_URL') or source.database_url
        return Q.create(source,out_dir=a.out,checkpoint_database_url=checkpoint,release=facts,execute=a.execute,
                         drained=True,drain_observed_at=datetime.fromisoformat(a.attest_drained_at),**keys,**history).to_dict()
    args=dict(target_root=a.target_root,target_database_url=os.environ['TARGET_DATABASE_URL'],anchor=a.manifest_sha256,
              expected_release=facts,execute=a.execute,**keys,**history)
    if name=='rewrite':return Q.rewrite(a.set,out_dir=a.out,**args).to_dict()
    return Q.restore(a.set,upgrade_to_head=a.upgrade_to_head,**args).to_dict()
