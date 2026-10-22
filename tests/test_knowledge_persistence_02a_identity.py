"""02A part 1: one runtime configuration, environment identity, the serving guard, safe diagnostics and lifecycle (replace, retire, reindex).
Offline and deterministic. The invariant under test: an environment that cannot serve governed knowledge NEVER silently looks like an empty
knowledge base, and UNAPPROVED knowledge never reaches candidate retrieval."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import select

from src.copilot.embeddings import LocalHashEmbedder
from src.knowledge_admin import policy as P
from src.knowledge_admin.config import resolve_knowledge_runtime_config
from src.knowledge_admin.contracts import identities_compatible
from src.knowledge_admin.environment import (
    KnowledgeServingRefused, build_identity, compare_worker, parse_worker_id, worker_id_for,
)
from src.knowledge_admin.service import KnowledgeConflict
from src.persistence import Job, KnowledgeSourceVersion as V
from tests._knowledge_env_02a import DOC, QUERY, FakeSemanticEmbedder, Process, hosted_temp, runtime_config

ROOT = Path(__file__).resolve().parents[1]
ABS_PATH = re.compile(r"(/Users/|/Volumes/|/private/|/tmp/|/var/folders/|[A-Za-z]:\\\\)")


@pytest.fixture()
def proc(tmp_path):
    p = Process(tmp_path / "env")
    yield p
    p.close()


# ===================================================================== one runtime configuration
def test_runtime_config_derives_from_existing_sources_and_never_serialises_secrets_or_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_DATA_DIR", str(tmp_path / "kdata"))
    monkeypatch.delenv("KNOWLEDGE_STORAGE_DIR", raising=False)
    monkeypatch.setenv("API_ENV", "staging")
    cfg = resolve_knowledge_runtime_config(type("A", (), {"database_url": "postgresql+psycopg://admin:S3cr3tPw@db.internal:5432/ask4mo?sslmode=require"})(),
                                           type("C", (), {"chroma_persist_dir": str(tmp_path / "kdata" / "chroma")})())
    assert cfg.environment == "staging" and cfg.hosted
    assert cfg.data_root == str((tmp_path / "kdata").resolve())
    assert Path(cfg.private_files_dir) == (tmp_path / "kdata").resolve() / "knowledge_private"      # on the data volume, not /tmp
    assert cfg.governed_collection == P.COLLECTION and len(cfg.collection_ids) == 2
    blob = json.dumps(cfg.to_safe_dict()) + repr(cfg)
    assert "S3cr3tPw" not in blob and "admin" not in blob and "db.internal" not in blob and not ABS_PATH.search(blob)
    assert cfg.database_identity().kind == "postgresql"


def test_private_files_no_longer_default_to_the_system_temp_directory(tmp_path, monkeypatch):
    """Pre-02A the default was $TMPDIR/ask4mo_knowledge: uploaded sources vanished with the container."""
    monkeypatch.setenv("COPILOT_DATA_DIR", str(tmp_path / "kdata"))
    monkeypatch.delenv("KNOWLEDGE_STORAGE_DIR", raising=False)
    from src.knowledge_admin.wiring import build_knowledge_doc_store

    store = build_knowledge_doc_store()
    assert "ask4mo_knowledge" not in str(store._root) and Path(store._root) == (tmp_path / "kdata" / "knowledge_private").resolve()
    monkeypatch.setenv("KNOWLEDGE_STORAGE_DIR", str(tmp_path / "explicit"))
    assert Path(build_knowledge_doc_store()._root) == (tmp_path / "explicit").resolve()      # the operator override still wins


def test_api_and_worker_resolve_the_same_configuration_from_the_same_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_DATA_DIR", str(tmp_path / "shared"))
    a = resolve_knowledge_runtime_config()
    b = resolve_knowledge_runtime_config()
    assert a == b and a.data_root_identity() == b.data_root_identity() and a.private_files_dir == b.private_files_dir


# ===================================================================== worker identity record (job_workers heartbeat)
def test_worker_id_carries_only_short_fingerprints_and_fits_the_column(proc):
    ident = build_identity(proc.runtime_cfg, proc.config)
    wid = worker_id_for(ident, rand="abcdef")
    assert len(wid) <= 40 and parse_worker_id(wid) is not None
    assert str(proc.root) not in wid and not ABS_PATH.search(wid)
    assert parse_worker_id("legacy-uuid-1234") is None and parse_worker_id(None) is None
    assert compare_worker(ident, wid).compatible
    assert compare_worker(ident, "legacy-uuid-1234") is None                       # unrecorded, not a match


def test_identity_compare_reports_the_precise_field_and_unknown_never_matches(tmp_path):
    base = runtime_config(tmp_path / "a")
    ident = build_identity(base, Process(tmp_path / "a").config)
    other_root = build_identity(runtime_config(tmp_path / "a", data_root=tmp_path / "elsewhere"), Process(tmp_path / "a").config)
    rep = compare_worker(ident, worker_id_for(other_root))
    assert not rep.compatible and [m.field for m in rep.mismatches] == ["data_root.short_hash"]
    other_db = type(base)(**{**base.__dict__, "database_url": "postgresql://u:p@otherhost:5432/other"})
    rep = compare_worker(ident, worker_id_for(build_identity(other_db, Process(tmp_path / "a").config)))
    assert not rep.compatible and "database.fingerprint" in [m.field for m in rep.mismatches]
    no_embedding = build_identity(base, None)                                        # embedding unknown on the worker side
    rep = compare_worker(ident, worker_id_for(no_embedding))
    assert not rep.compatible and "embedding" in [m.field for m in rep.mismatches]
    # 02K full-identity comparison agrees on the same inputs (the contract is the reference)
    assert not identities_compatible(ident, other_root).compatible


# ===================================================================== guard: identity mismatch refusal
def test_hosted_identity_mismatch_refuses_governed_retrieval_and_uploads_with_a_precise_reason(tmp_path, monkeypatch):
    hosted_temp(monkeypatch)
    p = Process(tmp_path / "env", environment="staging", worker_data_root=tmp_path / "a-different-data-root")
    try:
        p.worker.run_once()                                               # the worker records ITS identity through the heartbeat
        report = p.guard.check(fresh=True)
        assert not report.serving_allowed and report.worker_identity == "mismatch"
        assert [f.code for f in report.blocking] == ["identity_mismatch"] and report.blocking[0].fields == ("data_root.short_hash",)
        with pytest.raises(KnowledgeServingRefused) as e:
            p.retriever.retrieve(QUERY)
        assert e.value.codes == ["identity_mismatch"]
        with pytest.raises(KnowledgeServingRefused):
            p.upload()
        with p.sf() as s:                                                 # nothing was stored for the refused upload
            assert s.scalar(select(V.id)) is None
        assert not list((tmp_path / "env" / "private").iterdir())
    finally:
        p.close()


def test_development_reports_the_same_findings_as_a_warning_and_keeps_working(tmp_path):
    p = Process(tmp_path / "env", environment="development", worker_data_root=tmp_path / "a-different-data-root")
    try:
        p.worker.run_once()
        report = p.guard.check(fresh=True)
        assert report.worker_identity == "mismatch" and report.serving_allowed and not report.enforced      # labelled warning, not a refusal
        assert report.to_dict()["mode"] == "development_warning"
        assert p.upload()["version"] == 1 and p.retriever.retrieve(QUERY) == []
    finally:
        p.close()


def test_matching_worker_hosted_serves_normally(tmp_path, monkeypatch):
    hosted_temp(monkeypatch)
    p = Process(tmp_path / "env", environment="staging")
    try:
        p.worker.run_once()
        r = p.to_active()
        report = p.guard.check(fresh=True)
        assert report.worker_identity == "match" and report.serving_allowed, report.to_dict()
        assert report.findings == ()                                       # hosted, PostgreSQL identity, matching worker: nothing to report
        assert p.evidence() and all(e["knowledge_version_id"] == r["version_public_id"] for e in p.evidence())
    finally:
        p.close()


def test_hosted_sqlite_demonstration_database_is_refused_but_development_is_not(tmp_path, monkeypatch):
    """K9: a hosted UI must never silently sit on a local demonstration database (an empty one would look like 'no sources')."""
    hosted_temp(monkeypatch)
    p = Process(tmp_path / "env", environment="production", hosted_sqlite=True)
    try:
        p.worker.run_once()
        report = p.guard.check(fresh=True)
        assert [f.code for f in report.blocking] == ["database_is_sqlite"] and not report.serving_allowed
        with pytest.raises(KnowledgeServingRefused):
            p.retriever.retrieve(QUERY)
        r = p.readiness.readiness()
        assert r["status"] == "configuration_error" and r["governed_retrieval_ready"] is False and r["source_count"] == 0   # counts are the registry's, never invented
    finally:
        p.close()
    d = Process(tmp_path / "dev", environment="development")
    try:
        assert "database_is_sqlite" not in [f.code for f in d.guard.check(fresh=True).findings]
    finally:
        d.close()


def test_hosted_without_any_worker_is_reported_but_not_a_block_by_itself(tmp_path, monkeypatch):
    hosted_temp(monkeypatch)
    p = Process(tmp_path / "env", environment="staging")
    try:
        report = p.guard.check(fresh=True)
        assert report.worker_identity == "no_worker" and report.serving_allowed
        assert "worker_not_seen" in [f.code for f in report.findings]
    finally:
        p.close()


# ===================================================================== guard: empty collection refusal
def test_hosted_empty_governed_collection_is_refused_not_served_as_empty(tmp_path, monkeypatch):
    hosted_temp(monkeypatch)
    p = Process(tmp_path / "env", environment="staging")
    try:
        p.worker.run_once()
        p.to_active()
        assert p.guard.check(fresh=True).serving_allowed
        # the same registry, a NEW (empty) persistent collection: exactly what an unmounted index volume or a wrong data root looks like
        empty = type(p.store)(FakeSemanticEmbedder(), persist_dir=str(tmp_path / "other-index"), collection_name=P.COLLECTION)
        p.store = empty
        p.retriever.store = empty
        report = p.guard.check(fresh=True)
        assert [f.code for f in report.blocking] == ["governed_collection_empty"] and not report.serving_allowed
        with pytest.raises(KnowledgeServingRefused) as e:
            p.retriever.retrieve(QUERY)
        assert e.value.codes == ["governed_collection_empty"]
        r = p.readiness.readiness()
        assert r["governed_retrieval_ready"] is False and r["status"] != "ready"
        assert r["status"] in ("collection_missing", "configuration_error")
    finally:
        p.close()


def test_development_empty_collection_warns_clearly(tmp_path):
    p = Process(tmp_path / "env")
    try:
        p.to_active()
        p.store = type(p.store)(LocalHashEmbedder(), persist_dir=str(tmp_path / "other-index"), collection_name=P.COLLECTION)
        p.retriever.store = p.store
        report = p.guard.check(fresh=True)
        assert "governed_collection_empty" in [f.code for f in report.findings] and report.serving_allowed
        assert p.retriever.retrieve(QUERY) == []                          # still serves in development, with the warning visible in diagnostics
        env = p.readiness.readiness()["environment"]
        assert env["guard"]["mode"] == "development_warning"
    finally:
        p.close()


def test_hosted_missing_private_files_all_missing_blocks_uploads_partial_only_warns(tmp_path, monkeypatch):
    hosted_temp(monkeypatch)
    p = Process(tmp_path / "env", environment="staging")
    try:
        p.worker.run_once()
        p.to_active()
        p.to_active(title="Second source", name="b.txt", data=(DOC + "\n\nSecond.").encode())
        keys = [r[0] for r in p.sf().execute(select(V.storage_key)).all()]
        (tmp_path / "env" / "private" / keys[0]).unlink()                 # one file lost: warn
        rep = p.guard.check(fresh=True)
        assert rep.serving_allowed and "private_files_missing" in [f.code for f in rep.findings]
        (tmp_path / "env" / "private" / keys[1]).unlink()                 # all lost (volume not mounted): block
        rep = p.guard.check(fresh=True)
        assert not rep.serving_allowed and "private_files_all_missing" in [f.code for f in rep.blocking]
    finally:
        p.close()


def test_hosted_placement_problems_block(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))     # everything under tmp_path now counts as temporary
    p = Process(tmp_path / "env", environment="production")
    try:
        p.worker.run_once()
        codes = {f.code for f in p.guard.check(fresh=True).blocking}
        assert {"index_in_temp_directory", "data_root_in_temp_directory"} <= codes
        with pytest.raises(KnowledgeServingRefused):
            p.upload()
    finally:
        p.close()


def test_unrecognised_environment_name_fails_closed(tmp_path):
    from src.knowledge_admin.config import normalise_environment

    assert normalise_environment("prod-ish") == "unknown" and runtime_config(tmp_path, environment="unknown").hosted
    assert normalise_environment("PRODUCTION") == "production" and normalise_environment(None) == "development" and normalise_environment("local") == "development"


# ===================================================================== safe diagnostics
def test_readiness_environment_block_is_safe_and_backward_compatible(tmp_path, monkeypatch):
    hosted_temp(monkeypatch)
    p = Process(tmp_path / "env", environment="staging")
    try:
        p.worker.run_once()
        p.to_active()
        r = p.readiness.readiness()
        for legacy in ("status", "message", "candidate_retrieval_ready", "governed_retrieval_ready", "store", "curated_corpus", "worker", "collection"):
            assert legacy in r                                                   # every pre-02A field is still present
        env = r["environment"]
        assert env["environment"] == "staging" and env["database"]["kind"] == "postgresql" and len(env["database"]["fingerprint"]) == 64
        assert env["data_root"]["label"] == "knowledge-data-root" and len(env["data_root"]["short_hash"]) == 12
        cols = {c["collection_id"]: c for c in env["collections"]}
        assert cols[P.COLLECTION]["role"] == "governed" and cols[P.COLLECTION]["chunk_count"] > 0 and cols[P.COLLECTION]["persistent"]
        assert env["manifest"]["source_version_count"] == 1 and env["manifest"]["checksum"] and env["manifest"]["embedding_fields_known"] is False
        assert env["worker_identity"] == {"status": "match", "mismatched_fields": [], "workers_checked": 1}
        assert env["last_indexing"]["result"] == "succeeded"
        blob = json.dumps(r)
        assert str(tmp_path) not in blob and not ABS_PATH.search(blob) and "sqlite:///" not in blob and "password" not in blob.lower()
        assert set(r["views"]) == {"curated", "governed"} and r["views"]["curated"]["admin_managed"] is False and r["views"]["governed"]["admin_managed"] is True
        assert r["views"]["governed"]["active_source_count"] == 1
    finally:
        p.close()


def test_hosted_guard_block_is_visible_in_readiness_never_ready(tmp_path, monkeypatch):
    hosted_temp(monkeypatch)
    p = Process(tmp_path / "env", environment="staging", worker_data_root=tmp_path / "x")
    try:
        p.to_active()                      # the worker's first heartbeat (during the drain) is what reveals the mismatch
        r = p.readiness.readiness()
        assert r["status"] == "configuration_error" and r["governed_retrieval_ready"] is False and "refusing" in r["message"]
        assert r["environment"]["guard"]["serving_allowed"] is False
    finally:
        p.close()


# ===================================================================== lifecycle: replace, retire, reindex
def test_replace_new_version_supersedes_and_is_idempotent(proc):
    first = proc.to_active()
    v1 = first["version_public_id"]
    v2 = proc.new_version(first["source_public_id"])["version_public_id"]
    proc.drain()
    proc.index_version(v2)
    assert proc.state(v2) == "indexed"
    out = proc.svc.replace(v2, actor_user_id=1)
    assert out["state"] == "active" and proc.state(v1) == "retired"
    again = proc.svc.replace(v2, actor_user_id=1)                              # replay: no-op
    assert again["state"] == "active"
    with proc.sf() as s:
        assert len(s.scalars(select(V).where(V.state == "active")).all()) == 1
    proc.drain()                                                               # the predecessor's vectors are removed by a job
    ev = proc.evidence()
    assert ev and {e["knowledge_version_id"] for e in ev} == {v2}
    removes = proc.sf().scalars(select(Job).where(Job.job_type == P.JOB_REMOVE)).all()
    assert len(removes) == 1                                                   # deduplicated by its idempotency key


def test_replace_refuses_without_a_predecessor_and_for_non_indexed_versions(proc):
    r = proc.to_indexed()
    with pytest.raises(KnowledgeConflict, match="no active version"):
        proc.svc.replace(r["version_public_id"], actor_user_id=1)
    rr = proc.to_review(title="Another", name="c.txt", data=(DOC + "\n\nOther").encode())
    with pytest.raises(KnowledgeConflict):
        proc.svc.replace(rr["version_public_id"], actor_user_id=1)


def test_retire_is_idempotent_and_removal_job_is_not_duplicated(proc):
    v = proc.to_active()["version_public_id"]
    proc.svc.retire(v, actor_user_id=1)
    assert proc.evidence() == []                                               # excluded IMMEDIATELY, before any removal job ran
    again = proc.svc.retire(v, actor_user_id=1)
    assert again["state"] == "retired"
    proc.drain()
    proc.svc.retire(v, actor_user_id=1)
    assert len(proc.sf().scalars(select(Job).where(Job.job_type == P.JOB_REMOVE)).all()) == 1
    assert proc.store.count() == 0


def test_reindex_rebuilds_a_lost_collection_idempotently_without_changing_state(tmp_path):
    p = Process(tmp_path / "env")
    try:
        v = p.to_active()["version_public_id"]
        before = p.store.count()
        p.store.reset()                                                        # the collection is lost; the registry still says built
        assert p.store.count() == 0 and p.evidence() == []
        p.svc.request_reindex(v, actor_user_id=1)
        p.drain()
        assert p.store.count() == before and p.state(v) == "active"           # state unchanged; deterministic chunks restored
        assert p.evidence()
        n = p.store.count()
        p.svc.request_reindex(v, actor_user_id=1)                              # replay on a healthy collection: no duplicates
        p.drain()
        assert p.store.count() == n
        jobs = p.sf().scalars(select(Job).where(Job.job_type == P.JOB_REINDEX)).all()
        assert len(jobs) == 2 and all(set(j.payload_json) == {"version_id"} for j in jobs)         # id-only payload; a later request is a new job
    finally:
        p.close()


def test_reindex_request_before_completion_is_deduplicated_and_replay_of_the_handler_is_safe(proc):
    from types import SimpleNamespace
    from src.knowledge_admin.runtime import run_reindex

    v = proc.to_active()["version_public_id"]
    proc.svc.request_reindex(v, actor_user_id=1)
    proc.svc.request_reindex(v, actor_user_id=1)
    assert len(proc.sf().scalars(select(Job).where(Job.job_type == P.JOB_REINDEX)).all()) == 1
    n = proc.store.count()
    ctx = SimpleNamespace(attempt=1, max_attempts=3, services=SimpleNamespace(knowledge=proc.krt))
    run_reindex(v, ctx)
    run_reindex(v, ctx)                                                        # a lease-expiry replay
    assert proc.store.count() == n


def test_reindex_never_exposes_unapproved_or_retired_content(proc):
    rv = proc.to_review()["version_public_id"]
    with pytest.raises(KnowledgeConflict):
        proc.svc.request_reindex(rv, actor_user_id=1)                          # not approved: refused
    iv = proc.to_indexed(title="Indexed only", name="i.txt", data=(DOC + "\n\nIndexed only.").encode())["version_public_id"]
    proc.svc.request_reindex(iv, actor_user_id=1)                              # allowed for an indexed version...
    proc.drain()
    assert proc.evidence() == []                                               # ...but indexed is NOT active: still invisible to candidates
    av = proc.to_active(title="Active", name="a.txt", data=(DOC + "\n\nActive.").encode())["version_public_id"]
    proc.svc.retire(av, actor_user_id=1)
    with pytest.raises(KnowledgeConflict):
        proc.svc.request_reindex(av, actor_user_id=1)                          # retired: refused, and a stale replay is a no-op
    from types import SimpleNamespace
    from src.knowledge_admin.runtime import run_reindex
    n = proc.store.count()
    run_reindex(av, SimpleNamespace(attempt=1, max_attempts=3, services=SimpleNamespace(knowledge=proc.krt)))
    assert proc.store.count() == n


def test_reindex_with_a_tampered_or_missing_file_is_a_permanent_failure_not_a_silent_success(proc):
    from types import SimpleNamespace
    from src.jobs.registry import PermanentJobError
    from src.knowledge_admin.runtime import run_reindex

    v = proc.to_active()["version_public_id"]
    with proc.sf() as s:
        key = s.scalar(select(V.storage_key).where(V.public_id == v))
    (Path(proc.docs._root) / key).write_bytes(b"tampered bytes")
    with pytest.raises(PermanentJobError):
        run_reindex(v, SimpleNamespace(attempt=1, max_attempts=3, services=SimpleNamespace(knowledge=proc.krt)))


def test_lifecycle_actions_are_audited_with_canonical_names_and_no_content():
    from src.application import admin_audit as A

    assert A.ADMIN_KNOWLEDGE_VERSION_REPLACED in A.ADMIN_EVENT_NAMES and A.ADMIN_KNOWLEDGE_REINDEX_REQUESTED in A.ADMIN_EVENT_NAMES


# ===================================================================== HTTP: admin readiness response and permissions
def test_http_readiness_carries_the_environment_block_and_no_secrets_or_paths(tmp_path):
    from src.api import dependencies as D
    from tests.test_admin_foundation_w10_1 import Env

    env = Env()
    p = Process(tmp_path / "env")
    try:
        p.worker.run_once()
        p.to_active()
        env.app.dependency_overrides[D.get_knowledge_readiness_service] = lambda: p.readiness
        ck = env.user("knowledge_admin")[1]
        body = env.c.get("/api/v1/admin/knowledge/readiness", cookies=ck)
        assert body.status_code == 200
        data = body.json()
        assert data["environment"]["worker_identity"]["status"] == "match" and set(data["views"]) == {"curated", "governed"}
        text = body.text
        assert str(tmp_path) not in text and not ABS_PATH.search(text) and "sqlite:///" not in text
        assert env.c.get("/api/v1/admin/knowledge/readiness", cookies=env.user("support_operator")[1]).status_code == 403
        assert env.c.get("/api/v1/admin/knowledge/readiness", cookies=env.user("user")[1]).status_code == 403
    finally:
        env.close()
        p.close()


def test_http_lifecycle_routes_use_the_existing_permissions(tmp_path):
    from src.api import dependencies as D
    from tests.test_admin_foundation_w10_1 import Env

    env = Env()
    p = Process(tmp_path / "env")
    try:
        v = p.to_active()["version_public_id"]
        env.app.dependency_overrides[D.get_knowledge_admin_service] = lambda: p.svc
        kb, ops, user = env.user("knowledge_admin")[1], env.user("operations_admin")[1], env.user("user")[1]
        for path in ("reindex", "replace"):
            assert env.c.post(f"/api/v1/admin/knowledge/versions/{v}/{path}", cookies=user).status_code == 403
            assert env.c.post(f"/api/v1/admin/knowledge/versions/{v}/{path}", cookies=ops).status_code == 403
        assert env.c.post(f"/api/v1/admin/knowledge/versions/{v}/reindex", cookies=kb).status_code == 200
        assert env.c.post(f"/api/v1/admin/knowledge/versions/{v}/replace", cookies=kb).status_code == 200      # already active: idempotent no-op
        from src.persistence import AuditEvent
        with p.sf() as s:
            events = {e for e in s.scalars(select(AuditEvent.event_type)).all()}
        assert "admin.knowledge_reindex_requested" in events
    finally:
        env.close()
        p.close()


def test_http_governed_upload_refused_with_503_and_safe_reason_when_the_guard_blocks(tmp_path, monkeypatch):
    from src.api import dependencies as D
    from tests.test_admin_foundation_w10_1 import Env

    env = Env()                         # build the app first: it needs a real temp directory
    hosted_temp(monkeypatch)
    p = Process(tmp_path / "env", environment="staging", worker_data_root=tmp_path / "x")
    try:
        p.worker.run_once()
        env.app.dependency_overrides[D.get_knowledge_admin_service] = lambda: p.svc
        ck = env.user("knowledge_admin")[1]
        r = env.c.post("/api/v1/admin/knowledge/sources", cookies=ck, data={"title": "T", "language": "en", "authority_level": "2", "publisher": "P",
                       "provenance_note": "n", "licence_class": "public_official"}, files={"file": ("a.txt", DOC.encode(), "text/plain")})
        assert r.status_code == 503 and "identity_mismatch" in r.text
        assert str(tmp_path) not in r.text
    finally:
        env.close()
        p.close()


# ===================================================================== static boundaries
def test_no_forbidden_files_were_touched_and_no_migration_in_part_one():
    names = subprocess.run(["git", "diff", "--name-only", "origin/feat/02k-knowledge-contract"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    for banned in ("src/agent/", "src/copilot/security/", "src/copilot/embeddings.py", "src/documents/file_security.py", ".github/workflows/ci.yml",
                   "deploy/docker-compose.staging.yml", "frontend/components/admin/AdminShell.tsx", "frontend/lib/admin/capabilities.ts",
                   "docs/production/execution/RELEASE_READINESS_TRACKER.md", "src/knowledge_admin/contracts.py"):
        assert not [n for n in names if n.startswith(banned)], banned
