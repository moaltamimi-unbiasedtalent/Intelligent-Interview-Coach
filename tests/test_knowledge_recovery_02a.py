"""02A part 2: backup, verification and restore of governed knowledge, and the restore-in-a-separate-environment drill. Every restore goes into a NEW temp
environment; the source is only read. Offline: file SQLite, persistent Chroma under tmp_path, local hashing embedder, no provider or network call."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import select

from src.copilot.embeddings import LocalHashEmbedder
from src.copilot.vectorstore import ChromaStore
from src.knowledge_admin import policy as P
from src.knowledge_admin.environment import build_identity
from src.knowledge_admin.recovery import create_backup, restore_backup, verify_backup
from src.persistence import KnowledgeIndexRecord, KnowledgeSource, KnowledgeSourceVersion as V, User, init_db, make_engine, make_session_factory
from tests._knowledge_env_02a import DOC, META, Process

ROOT = Path(__file__).resolve().parents[1]
ABS_PATH = re.compile(r"(/Users/|/Volumes/|/private/|/tmp/|/var/folders/)")


def backup(p: Process, out: Path, **kw):
    ident = build_identity(p.runtime_cfg, p.config, stores={P.COLLECTION: p.store})
    return create_backup(p.sf, p.docs, p.store, out_dir=out, chroma_dir=p.root / "chroma", identity=ident, **kw)


def restore(bk: Path, root: Path, *, operator=True, **kw):
    """Restore into a NEW environment laid out like a Process (kb.db, private/, chroma/), without constructing a Process first (that would create index files).
    ``operator`` creates ONE deactivated, credential-less account in the target to be the explicit restorer of record for approval evidence."""
    root.mkdir(parents=True, exist_ok=True)
    engine = make_engine(f"sqlite:///{root / 'kb.db'}")
    init_db(engine)
    sf = make_session_factory(engine)
    fallback = None
    if operator:
        with sf() as s:
            if s.scalar(select(User.id).where(User.provider == "restore-drill")) is None:
                s.add(User(id=9001, subject="restore-operator", provider="restore-drill", status="deactivated"))
                s.commit()
            fallback = s.scalar(select(User.id).where(User.provider == "restore-drill"))
    rep = restore_backup(bk, session_factory=sf, files_dir=root / "private", index_dir=root / "chroma", fallback_user_id=fallback,
                         open_store=lambda: ChromaStore(LocalHashEmbedder(), persist_dir=str(root / "chroma"), collection_name=P.COLLECTION), **kw)
    return rep, sf, engine


def tree_hash(path: Path) -> dict:
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(path.rglob("*")) if p.is_file()} if path.exists() else {}


@pytest.fixture()
def src(tmp_path):
    p = Process(tmp_path / "source", environment="development")
    r = p.to_active()
    r2 = p.to_active(title="Second framework", name="two.txt", data=(DOC + "\n\nA second, separate source about negotiation.").encode(), language="en")
    v3 = p.new_version(r["source_public_id"])["version_public_id"]       # a retained, never-activated newer version
    p.drain()
    p.worker.run_once()
    yield p, r, r2, v3
    p.close()


# ===================================================================== backup
def test_backup_is_a_dry_run_by_default_and_writes_nothing(src, tmp_path):
    p, *_ = src
    out = tmp_path / "bk"
    rep = backup(p, out)
    assert rep.executed is False and rep.ok and rep.counts["knowledge_source_versions"] == 3 and rep.counts["private_files"] == 3
    assert not out.exists()                                              # nothing written


def test_backup_execute_writes_a_verifiable_manifest_with_checksums_and_no_paths_or_secrets(src, tmp_path):
    p, *_ = src
    out = tmp_path / "bk"
    rep = backup(p, out, execute=True)
    assert rep.ok and rep.details["consistent"] is True
    m = json.loads((out / "manifest.json").read_text())
    assert m["format"] == 1 and len(m["files"]) == 3 and all(len(h) == 64 for h in m["files"].values()) and m["index_files"]
    im = m["index_manifest"]
    assert im["collection_id"] == P.COLLECTION and len(im["checksum"]) == 64 and len(im["source_version_ids"]) == 2     # two indexed+active versions
    assert im["provider"] == "local" and im["compatibility_hash"] is None                                              # embedding fields never invented
    assert m["counts"]["chunks"] == p.store.count()
    blob = (out / "manifest.json").read_text() + json.dumps(rep.to_dict())
    assert not ABS_PATH.search(blob) and str(tmp_path) not in blob and "sqlite:///" not in blob
    assert verify_backup(out).ok
    # a private file is stored verbatim under its opaque key
    key = next(iter(m["files"]))
    assert hashlib.sha256((out / "files" / key).read_bytes()).hexdigest() == m["files"][key]


def test_backup_refuses_a_non_empty_target_and_never_deletes_anything(src, tmp_path):
    p, *_ = src
    out = tmp_path / "bk"
    out.mkdir()
    (out / "precious.txt").write_text("keep me")
    rep = backup(p, out, execute=True)
    assert not rep.ok and "backup_target_not_empty" in rep.codes
    assert (out / "precious.txt").read_text() == "keep me" and not (out / "manifest.json").exists()


def test_backup_refuses_while_knowledge_jobs_are_active_unless_forced(src, tmp_path):
    p, r, *_ = src
    p.svc.request_reindex(r["version_public_id"], actor_user_id=1)       # a queued knowledge job
    rep = backup(p, tmp_path / "bk", execute=True)
    assert not rep.ok and "knowledge_jobs_active" in rep.codes and not (tmp_path / "bk").exists()
    forced = backup(p, tmp_path / "bk2", execute=True, allow_active_jobs=True)
    assert forced.ok and forced.details["consistent"] is False


def test_backup_reports_missing_private_files_instead_of_hiding_them(src, tmp_path):
    p, r, *_ = src
    with p.sf() as s:
        key = s.scalar(select(V.storage_key).where(V.public_id == r["version_public_id"]))
    (p.root / "private" / key).unlink()
    rep = backup(p, tmp_path / "bk", execute=True)
    assert rep.ok and "private_files_missing" in rep.codes and rep.counts["private_files_missing"] == 1
    assert key in json.loads((tmp_path / "bk" / "manifest.json").read_text())["missing_files"]


# ===================================================================== verify
def test_verify_detects_tampering_in_files_registry_chunks_and_index(src, tmp_path):
    p, *_ = src
    out = tmp_path / "bk"
    backup(p, out, execute=True)
    assert verify_backup(out).ok
    m = json.loads((out / "manifest.json").read_text())
    for target, code in ((out / "files" / next(iter(m["files"])), "private_file_integrity"), (out / "registry.json", "registry.json_integrity"),
                         (out / "chunks.jsonl", "chunks.jsonl_integrity"), (out / "index" / next(iter(m["index_files"])), "index_file_integrity")):
        original = target.read_bytes()
        target.write_bytes(original + b"x")
        rep = verify_backup(out)
        assert not rep.ok and code in rep.codes, code
        target.write_bytes(original)
        assert verify_backup(out).ok
    (out / "manifest.json").unlink()
    assert verify_backup(out).codes == ["backup_manifest_missing"]


# ===================================================================== the restore drill
def test_restore_drill_into_a_separate_environment_matches_registry_files_index_and_candidate_provenance(src, tmp_path):
    p, r, r2, v3 = src
    out = tmp_path / "bk"
    assert backup(p, out, execute=True).ok
    source_tree = (tree_hash(p.root / "private"), tree_hash(p.root / "chroma"))
    expected_evidence = p.evidence()
    assert expected_evidence

    target = tmp_path / "restored"
    dry, *_ = restore(out, target)                                      # DRY-RUN first: default, writes no data
    assert dry.executed is False and dry.ok and tree_hash(target / "private") == {} and tree_hash(target / "chroma") == {}
    rep, sf, engine = restore(out, target, execute=True)
    assert rep.ok, rep.to_dict()
    assert rep.counts["restored_chunks"] == p.store.count()
    assert rep.details["rows_added"] == {"knowledge_sources": 2, "knowledge_source_versions": 3, "knowledge_index_records": 2}
    engine.dispose()

    q = Process(target, environment="development")                      # open the restored environment like a fresh process
    try:
        with q.sf() as s, p.sf() as o:
            for model in (KnowledgeSource, V, KnowledgeIndexRecord):
                cols = [c.key for c in model.__table__.columns if not c.key.endswith("_user_id")]
                a = sorted(tuple(str(getattr(x, c)) for c in cols) for x in o.scalars(select(model)).all())
                b = sorted(tuple(str(getattr(x, c)) for c in cols) for x in s.scalars(select(model)).all())
                assert a == b, model.__tablename__
        assert tree_hash(q.root / "private") == source_tree[0]          # every private file byte-identical, same opaque keys
        assert q.store.count() == p.store.count()
        assert q.state(r["version_public_id"]) == "active" and q.state(v3) == p.state(v3) == "review_required"
        ev = q.evidence()
        assert ev == expected_evidence                                   # candidate-facing retrieval and citation provenance are identical
        assert {e["knowledge_version_id"] for e in ev} <= {r["version_public_id"], r2["version_public_id"]}
        assert all(e["publisher"] == META["publisher"] and e["authority_level"] == 2 for e in ev)
        rd = q.readiness.readiness()
        assert rd["governed_retrieval_ready"] and rd["status"] in ("ready", "degraded")
        assert q.guard.check(fresh=True).serving_allowed
        # the restored environment is independent: changing it does not touch the source
        q.svc.retire(r2["version_public_id"], actor_user_id=1)
        assert p.state(r2["version_public_id"]) == "active"
    finally:
        q.close()
    assert (tree_hash(p.root / "private"), tree_hash(p.root / "chroma")) == source_tree      # the source environment was only read


def test_restore_clears_actor_references_for_users_missing_in_the_target(src, tmp_path):
    p, *_ = src
    out = tmp_path / "bk"
    backup(p, out, execute=True)
    rep, _, engine = restore(out, tmp_path / "restored", execute=True)
    engine.dispose()
    assert rep.ok and rep.details["actor_references_remapped"] > 0       # the approving administrator's account does not exist in the new database
    assert rep.details["actor_references_cleared"] > 0                   # other (nullable) actor references are cleared, never invented


def test_restore_refuses_when_approval_evidence_has_no_actor_in_the_target(src, tmp_path):
    p, *_ = src
    out = tmp_path / "bk"
    backup(p, out, execute=True)
    rep, _, engine = restore(out, tmp_path / "restored", operator=False, execute=True)
    engine.dispose()
    assert not rep.ok and "approval_actor_missing_in_target" in rep.codes and rep.details["versions_needing_an_actor"] == 2
    assert tree_hash(tmp_path / "restored" / "private") == {} and tree_hash(tmp_path / "restored" / "chroma") == {}      # refused BEFORE any write
    dry, _, engine = restore(out, tmp_path / "restored-dry", operator=False)                                              # the dry-run reports it too
    engine.dispose()
    assert not dry.ok and "approval_actor_missing_in_target" in dry.codes


def test_restore_refuses_a_non_empty_target_and_never_changes_or_deletes_it(src, tmp_path):
    p, *_ = src
    out = tmp_path / "bk"
    backup(p, out, execute=True)
    target = tmp_path / "restored"
    first, _, engine = restore(out, target, execute=True)
    engine.dispose()
    assert first.ok
    before = (tree_hash(target / "private"), tree_hash(target / "chroma"), (target / "kb.db").read_bytes())
    second, _, engine = restore(out, target, execute=True)               # restoring again over the same target
    engine.dispose()
    assert not second.ok and second.codes[0] == "target_not_empty" and {"registry_not_empty", "files_not_empty", "index_not_empty"} <= set(second.codes)
    assert (tree_hash(target / "private"), tree_hash(target / "chroma"), (target / "kb.db").read_bytes()) == before


def test_restore_refuses_a_target_with_unrelated_existing_files_and_deletes_nothing(src, tmp_path):
    p, *_ = src
    out = tmp_path / "bk"
    backup(p, out, execute=True)
    target = tmp_path / "restored"
    (target / "private").mkdir(parents=True)
    (target / "private" / "someone-elses-file").write_bytes(b"do not touch")
    rep, _, engine = restore(out, target, execute=True)
    engine.dispose()
    assert not rep.ok and "files_not_empty" in rep.codes
    assert (target / "private" / "someone-elses-file").read_bytes() == b"do not touch" and not (target / "chroma").exists()


def test_restore_with_explicit_allow_non_empty_adds_only_what_is_missing_and_leaves_the_index_alone(src, tmp_path):
    p, *_ = src
    out = tmp_path / "bk"
    backup(p, out, execute=True)
    target = tmp_path / "restored"
    (target / "chroma").mkdir(parents=True)
    (target / "chroma" / "existing-index-file").write_bytes(b"existing index")
    rep, sf, engine = restore(out, target, execute=True, allow_non_empty=True)
    engine.dispose()
    assert rep.ok and "non_empty_target_allowed" in rep.codes and "index_not_restored_run_reindex" in rep.codes
    assert (target / "chroma" / "existing-index-file").read_bytes() == b"existing index" and rep.details["index_files_copied"] == 0
    assert rep.details["rows_added"]["knowledge_source_versions"] == 3 and len(list((target / "private").iterdir())) == 3


def test_restore_refuses_a_tampered_backup_before_writing_anything(src, tmp_path):
    p, *_ = src
    out = tmp_path / "bk"
    backup(p, out, execute=True)
    key = next(iter(json.loads((out / "manifest.json").read_text())["files"]))
    (out / "files" / key).write_bytes(b"tampered")
    rep, _, engine = restore(out, tmp_path / "restored", execute=True)
    engine.dispose()
    assert not rep.ok and rep.codes[0] == "backup_integrity_failed" and "private_file_integrity" in rep.codes
    assert tree_hash(tmp_path / "restored" / "private") == {} and tree_hash(tmp_path / "restored" / "chroma") == {}


def test_restore_can_rebuild_the_index_from_the_backed_up_chunks_with_the_local_embedder(src, tmp_path):
    p, *_ = src
    out = tmp_path / "bk"
    backup(p, out, execute=True)
    rep, sf, engine = restore(out, tmp_path / "restored", execute=True, rebuild_index=True)
    engine.dispose()
    assert rep.ok and "index_rebuilt_from_chunks" in rep.codes and rep.counts["restored_chunks"] == p.store.count()
    q = Process(tmp_path / "restored")
    try:
        assert q.evidence() == p.evidence()
    finally:
        q.close()
    # a source that did not use the local embedder is never silently re-embedded
    m = json.loads((out / "manifest.json").read_text())
    m["source_identity"]["embedding"]["provider"] = "openai"
    (out / "manifest.json").write_text(json.dumps(m))
    rep2, _, engine2 = restore(out, tmp_path / "restored2", execute=True, rebuild_index=True)
    engine2.dispose()
    assert not rep2.ok and rep2.codes == ["rebuild_requires_local_embedder"]


def test_a_lost_environment_is_recoverable_from_backup_without_the_original(tmp_path):
    """The disaster drill: back up, destroy the (temp) source, restore elsewhere, serve the same evidence."""
    import shutil

    p = Process(tmp_path / "source")
    p.to_active()
    expected = p.evidence()
    out = tmp_path / "bk"
    assert backup(p, out, execute=True).ok
    p.close()
    shutil.rmtree(tmp_path / "source")                                    # a temp directory this test created: simulates the lost volume
    rep, _, engine = restore(out, tmp_path / "restored", execute=True)
    engine.dispose()
    assert rep.ok
    q = Process(tmp_path / "restored")
    try:
        assert q.evidence() == expected and q.guard.check(fresh=True).serving_allowed
    finally:
        q.close()


# ===================================================================== CLI
def run_cli(*args, env_extra=None, cwd=None):
    env = {"PATH": "/usr/bin:/bin", "HOME": str(cwd or ROOT), "PYTHONDONTWRITEBYTECODE": "1", **(env_extra or {})}
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "knowledge_backup.py"), *args], capture_output=True, text=True, env=env, cwd=str(cwd or ROOT),
                          timeout=300)


def test_cli_backup_verify_restore_round_trip_with_dry_run_default(src, tmp_path):
    p, *_ = src
    root = p.root
    p.close()                                       # release this process's native Chroma client before other interpreters open the same index
    env = {"KNOWLEDGE_STORAGE_DIR": str(root / "private")}
    common = ["--data-root", str(root), "--database-url", f"sqlite:///{root / 'kb.db'}"]
    out = tmp_path / "cli-bk"
    dry = run_cli("backup", "--out", str(out), *common, env_extra=env, cwd=tmp_path)
    assert dry.returncode == 0, dry.stderr[-500:]
    d = json.loads(dry.stdout)
    assert d["mode"] == "dry_run" and not out.exists()
    done = run_cli("backup", "--out", str(out), "--execute", *common, env_extra=env, cwd=tmp_path)
    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-500:]
    assert json.loads(done.stdout)["mode"] == "executed" and (out / "manifest.json").is_file()
    assert run_cli("verify", "--backup", str(out), cwd=tmp_path).returncode == 0
    target = tmp_path / "cli-restored"
    no_actor = run_cli("restore", "--backup", str(out), "--target-root", str(target), cwd=tmp_path)             # a brand-new database has no approver account
    assert no_actor.returncode == 1 and "approval_actor_missing_in_target" in no_actor.stdout and not target.exists()
    db = tmp_path / "target.db"                                                                                   # a prepared target database with one restorer-of-record account
    engine = make_engine(f"sqlite:///{db}")
    init_db(engine)
    with make_session_factory(engine)() as s:
        s.add(User(id=9001, subject="restore-operator", provider="restore-drill", status="deactivated"))
        s.commit()
    engine.dispose()
    tgt = ["--target-root", str(target), "--target-database-url", f"sqlite:///{db}", "--fallback-user-id", "9001"]
    plan = run_cli("restore", "--backup", str(out), *tgt, cwd=tmp_path)
    assert plan.returncode == 0 and json.loads(plan.stdout)["mode"] == "dry_run" and not target.exists()
    res = run_cli("restore", "--backup", str(out), *tgt, "--execute", cwd=tmp_path)
    assert res.returncode == 0, res.stdout[-600:] + res.stderr[-400:]
    assert json.loads(res.stdout)["ok"] is True
    again = run_cli("restore", "--backup", str(out), *tgt, "--execute", cwd=tmp_path)
    assert again.returncode == 1 and "target_not_empty" in again.stdout                # refused: the target is no longer empty
    for text in (dry.stdout, done.stdout, res.stdout, again.stdout, no_actor.stdout, plan.stdout, dry.stderr, done.stderr):
        assert not ABS_PATH.search(text) and "sqlite:///" not in text, text[:200]


def test_cli_usage_error_and_missing_backup_use_fixed_codes(tmp_path):
    bad = run_cli("verify", "--backup", str(tmp_path / "nothing-here"), cwd=tmp_path)
    assert bad.returncode == 1 and "backup_manifest_missing" in bad.stdout and str(tmp_path) not in bad.stdout
    assert run_cli("frobnicate", cwd=tmp_path).returncode == 2
