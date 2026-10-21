"""02A: restart persistence and redeployment persistence for governed knowledge. Every "restart" builds COMPLETELY NEW engine, session factory,
vector-store client, document store, job service, worker and retriever objects over the same on-disk stores (file SQLite, persistent Chroma,
private files); the redeployment test additionally uses a brand-new Python interpreter. Offline: local hashing embedder, fake scanner."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select

from src.persistence import KnowledgeIndexRecord, KnowledgeSource, KnowledgeSourceVersion as V
from tests._knowledge_env_02a import DOC, Process

ROOT = Path(__file__).resolve().parents[1]


def snapshot(p: Process) -> dict:
    with p.sf() as s:
        versions = s.execute(select(V.public_id, V.version, V.state, V.checksum_sha256, V.storage_key, V.chunk_count).order_by(V.id)).all()
        recs = s.execute(select(KnowledgeIndexRecord.version_id, KnowledgeIndexRecord.state, KnowledgeIndexRecord.chunk_count)).all()
        sources = s.scalars(select(KnowledgeSource.public_id)).all()
    files = {r[4]: (Path(p.docs._root) / r[4]).read_bytes() for r in versions}
    return {"sources": sorted(sources), "versions": [tuple(v) for v in versions], "records": sorted(tuple(r) for r in recs), "files": files,
            "chunks": p.store.count(), "evidence": p.evidence()}


def test_restart_keeps_sources_versions_files_index_and_retrieval_intact(tmp_path):
    root = tmp_path / "env"
    first = Process(root)
    r = first.to_active()
    before = snapshot(first)
    assert before["evidence"] and before["chunks"] > 0 and before["records"]
    first.close()
    del first                                                                  # nothing in memory survives

    second = Process(root)                                                     # a restart: all-new objects over the same disk
    try:
        after = snapshot(second)
        assert after == before                                                 # registry, versions, bytes, chunks and candidate-facing provenance
        assert second.state(r["version_public_id"]) == "active"
        ev = after["evidence"]
        assert {e["knowledge_version_id"] for e in ev} == {r["version_public_id"]} and all(e["publisher"] == "Example Framework Body" for e in ev)
        assert all(e["authority_level"] == 2 and e["language"] == "en" and e["title"] == "Product framework" for e in ev)
        rd = second.readiness.readiness()
        assert rd["governed_retrieval_ready"] is True and rd["status"] == "ready"
        assert second.guard.check(fresh=True).serving_allowed
        # the lifecycle continues on the restarted objects: a new version is uploaded, indexed and replaces the old one
        v2 = second.new_version(r["source_public_id"])["version_public_id"]
        second.drain()
        second.index_version(v2)
        assert second.svc.replace(v2, actor_user_id=1)["state"] == "active"
        assert second.state(r["version_public_id"]) == "retired"
        second.drain()
        assert {e["knowledge_version_id"] for e in second.evidence()} == {v2}
    finally:
        second.close()

    third = Process(root)                                                      # and the replacement survives a further restart
    try:
        assert {e["knowledge_version_id"] for e in third.evidence()} == {v2}
        assert third.state(r["version_public_id"]) == "retired" and third.state(v2) == "active"
    finally:
        third.close()


def test_work_queued_before_a_restart_is_completed_by_the_new_worker(tmp_path):
    root = tmp_path / "env"
    a = Process(root)
    r = a.to_review()
    v = r["version_public_id"]
    a.svc.approve(v, actor_user_id=1)
    a.svc.request_index(v, actor_user_id=1)                                    # the index job is queued but never ran
    assert a.state(v) == "indexing"
    a.close()
    b = Process(root)
    try:
        b.drain()
        assert b.state(v) == "indexed"
        b.svc.activate(v, actor_user_id=1)
        assert b.evidence()
    finally:
        b.close()


def test_unapproved_content_is_never_retrievable_across_restarts(tmp_path):
    root = tmp_path / "env"
    a = Process(root)
    a.to_review(title="Unapproved", name="u.txt", data=(DOC + "\n\nUnapproved only.").encode())                  # parsed, awaiting review
    ind = a.to_indexed(title="Indexed not active", name="i.txt", data=(DOC + "\n\nIndexed only.").encode())      # indexed, NOT activated
    assert a.evidence() == []
    a.close()
    b = Process(root)
    try:
        assert b.evidence() == [] and b.state(ind["version_public_id"]) == "indexed"
        assert b.store.count() > 0                                             # the chunks exist physically; the SQL active set is the gate
    finally:
        b.close()


def test_redeployment_a_new_python_process_over_the_same_volumes_serves_the_same_evidence(tmp_path):
    root = tmp_path / "env"
    p = Process(root)
    p.to_active()
    expected = p.evidence()
    expected_chunks = p.store.count()
    p.close()
    code = (f"import sys, json; sys.path.insert(0, {str(ROOT)!r})\n"
            "from pathlib import Path\n"
            "from tests._knowledge_env_02a import Process\n"
            f"q = Process(Path({str(root)!r}))\n"
            "print(json.dumps({'evidence': q.evidence(), 'chunks': q.store.count(), 'ready': q.readiness.readiness()['governed_retrieval_ready'],\n"
            "                  'guard': q.guard.check(fresh=True).serving_allowed}))\n")
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"}
    out = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=240)
    assert out.returncode == 0, out.stderr[-800:]
    got = json.loads(out.stdout.strip().splitlines()[-1])
    assert got["evidence"] == expected and got["chunks"] == expected_chunks and got["ready"] is True and got["guard"] is True
