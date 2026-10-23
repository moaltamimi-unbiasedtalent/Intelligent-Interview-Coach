"""05B (PG-09): the backup SET, tamper and refusal cases, encryption and key hygiene, the restore drill harness and record, the backup-erasure procedure, and the
no-secret / no-path guarantees. Offline and deterministic: file SQLite, a persistent Chroma index under tmp_path with the local hashing embedder, synthetic data only,
no network, no provider, no Docker, no PostgreSQL (the PostgreSQL-only paths live in tests/test_pg_05b.py and are skipped without TEST_DATABASE_URL)."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from src.backup_set import crypto, drill as D, engine as E, erasure as X
from src.backup_set.fixture import build_synthetic_environment
from src.jobs.registry import JobTypeDef
from src.jobs.service import JobService
from src.persistence import make_engine, make_session_factory

ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 10, 12, 8, 0, tzinfo=timezone.utc)
PATHISH = re.compile(r"(/Users/|/Volumes/|/private/|/tmp/|/var/folders/|://)")
KEY_TEXT = crypto.generate_key()
KEY = crypto.parse_key(KEY_TEXT)


def tree(path: Path) -> dict:
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(path.rglob("*")) if p.is_file()} if path.exists() else {}


def clock(when):
    return lambda: when


@pytest.fixture()
def src(tmp_path):
    return build_synthetic_environment(tmp_path / "src")


def make_set(source, out, **kw):
    kw.setdefault("api_env", "test")
    rep = E.create_set(source, out_dir=out, execute=True, **kw)
    assert rep.ok, rep.codes
    return rep


def blobs(path: Path) -> bytes:
    return b"".join(p.read_bytes() for p in sorted(path.rglob("*")) if p.is_file())


def _job_types():
    class P(BaseModel):
        model_config = ConfigDict(extra="forbid")
        n: str = "x"

    return {"t": JobTypeDef(code="t", label="Test", payload_model=P, handler=lambda payload, ctx: None, summarize=lambda p: {"n": p.n}, idempotency="test", max_attempts=3,
                            lease_seconds=30, backoff_base_seconds=10, backoff_cap_seconds=40, admin_enqueue=True)}


def enqueue_job(source):
    eng = make_engine(source.database_url)
    try:
        JobService(make_session_factory(eng), _job_types()).enqueue("t", {"n": "x"})
    finally:
        eng.dispose()


# ===================================================================== dry run, manifest and checksums
def test_backup_is_a_dry_run_by_default_and_writes_nothing(src, tmp_path):
    out = tmp_path / "set"
    rep = E.create_set(src, out_dir=out, api_env="test")
    assert rep.executed is False and rep.ok and rep.counts["document_files"] == 4 and rep.counts["tables"] > 50
    assert not out.exists()


def test_execute_writes_one_manifest_described_set_with_checksums_row_counts_and_consistency(src, tmp_path):
    out = tmp_path / "set"
    rep = make_set(src, out)
    m = E.load_manifest(out)
    assert rep.details["manifest_sha256"] == E.manifest_digest(out)
    assert m["database"]["row_counts"] == E.table_counts(src.database_url) and m["database"]["tables"] == len(m["database"]["row_counts"])
    assert m["documents"]["count"] == 4 and m["knowledge"]["chunks"] == 4 and m["knowledge"]["index_checksum"] and m["retrieval_probe"]["run"] is True
    assert m["consistency"]["consistent"] is True and m["consistency"]["jobs_active_at_start"] == 0 and m["consistency"]["jobs_active_at_end"] == 0
    for logical, e in m["files"].items():
        assert E.sha_file(out / e["stored"]) == e["stored_sha256"] == e["sha256"] and E.safe_rel(logical)      # unsealed: stored == plaintext
    assert {"database", "documents", "knowledge"} <= {p.name for p in out.iterdir()}
    assert E.verify_set(out).ok


def test_manifest_and_report_carry_no_path_url_or_secret(src, tmp_path):
    out = tmp_path / "set"
    rep = make_set(src, out, encryption_key=KEY)
    text = json.dumps(rep.to_dict()) + (out / E.MANIFEST).read_text(encoding="utf-8")
    assert not PATHISH.search(text) and KEY_TEXT not in text and str(tmp_path) not in text
    assert "synthetic1@example.invalid" not in text                       # no candidate email or content in a manifest


def test_source_is_only_read(src, tmp_path):
    before = (tree(Path(src.documents_dir)), tree(Path(src.knowledge_index_dir)), E.table_counts(src.database_url))
    make_set(src, tmp_path / "set")
    assert (tree(Path(src.documents_dir)), tree(Path(src.knowledge_index_dir)), E.table_counts(src.database_url)) == before


# ===================================================================== refusals
def test_backup_refuses_a_non_empty_target_and_a_target_inside_a_source_directory(src, tmp_path):
    out = tmp_path / "set"
    out.mkdir()
    (out / "keep.txt").write_text("existing")
    rep = E.create_set(src, out_dir=out, execute=True, api_env="test")
    assert not rep.ok and "backup_target_not_empty" in rep.codes and (out / "keep.txt").read_text() == "existing" and not (out / E.MANIFEST).exists()
    inside = Path(src.documents_dir) / "nested-set"
    rep = E.create_set(src, out_dir=inside, execute=True, api_env="test")
    assert not rep.ok and "backup_target_inside_source" in rep.codes and not inside.exists()


def test_backup_refuses_active_jobs_and_marks_an_allowed_one_inconsistent(src, tmp_path):
    enqueue_job(src)
    out = tmp_path / "set"
    rep = E.create_set(src, out_dir=out, execute=True, api_env="test")
    assert not rep.ok and "jobs_active" in rep.codes and not out.exists()
    rep = E.create_set(src, out_dir=out, execute=True, api_env="test", allow_active_jobs=True)
    assert rep.ok and "jobs_active_allowed_inconsistent" in rep.codes and E.load_manifest(out)["consistency"]["consistent"] is False


def test_a_source_that_changes_during_the_copy_leaves_no_manifest_so_it_can_never_be_restored(src, tmp_path, monkeypatch):
    orig = E.retrieval_probe

    def late_write(store):
        (Path(src.documents_dir) / "written-during-backup").write_bytes(b"late")
        return orig(store)

    monkeypatch.setattr(E, "retrieval_probe", late_write)
    out = tmp_path / "set"
    rep = E.create_set(src, out_dir=out, execute=True, api_env="test")
    assert not rep.ok and "source_changed_during_backup" in rep.codes and not (out / E.MANIFEST).exists()
    assert E.verify_set(out).codes == ["set_manifest_missing"]
    r = E.restore_set(out, target_root=tmp_path / "r", execute=True)
    assert not r.ok and not (tmp_path / "r").exists()


def test_a_missing_source_database_is_a_fixed_code_not_a_traceback(tmp_path):
    rep = E.create_set(E.Source(database_url=f"sqlite:///{tmp_path / 'nope' / 'x.db'}", documents_dir=tmp_path / "d"), out_dir=tmp_path / "set", execute=True, api_env="test")
    assert not rep.ok and rep.codes and not PATHISH.search(json.dumps(rep.to_dict()))


# ===================================================================== tamper detection
def test_verify_detects_a_modified_a_missing_and_an_unlisted_file_and_unsafe_manifest_paths(src, tmp_path):
    out = tmp_path / "set"
    make_set(src, out)
    m = E.load_manifest(out)
    doc = sorted(k for k in m["files"] if k.startswith("documents/"))[0]
    victim = out / m["files"][doc]["stored"]
    original = victim.read_bytes()
    victim.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    assert "file_checksum_mismatch" in E.verify_set(out).codes
    victim.write_bytes(original)
    assert E.verify_set(out).ok
    victim.unlink()
    assert "file_missing" in E.verify_set(out).codes
    victim.write_bytes(original)
    (out / "documents" / "extra").write_bytes(b"x")
    assert "unlisted_file" in E.verify_set(out).codes
    (out / "documents" / "extra").unlink()
    m2 = json.loads((out / E.MANIFEST).read_text())
    m2["files"]["../escape"] = {"stored": "../escape", "sha256": "0" * 64, "stored_sha256": "0" * 64, "size": 1, "sealed": False}
    (out / E.MANIFEST).write_text(json.dumps(m2))
    assert "unsafe_path_in_manifest" in E.verify_set(out).codes


def test_verify_refuses_a_symlink_inside_a_set_and_a_foreign_or_missing_manifest(src, tmp_path):
    out = tmp_path / "set"
    make_set(src, out)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret outside")
    (out / "documents" / "link").symlink_to(outside)
    assert "symlink_in_set" in E.verify_set(out).codes
    assert E.verify_set(tmp_path / "nothing").codes == ["set_manifest_missing"]
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / E.MANIFEST).write_text(json.dumps({"format": 99, "files": {}, "set_id": "x"}))
    assert E.verify_set(bad).codes == ["set_format_unsupported"]
    (bad / E.MANIFEST).write_text("not json")
    assert E.verify_set(bad).codes == ["set_manifest_invalid"]


def test_a_signed_manifest_cannot_be_edited_and_an_unsigned_one_is_refused_when_a_signature_is_required(src, tmp_path):
    signed, plain = tmp_path / "signed", tmp_path / "plain"
    skey = crypto.parse_key(crypto.generate_key())
    make_set(src, signed, signing_key=skey)
    make_set(src, plain)
    m = json.loads((signed / E.MANIFEST).read_text())
    first = sorted(m["database"]["row_counts"])[0]
    m["database"]["row_counts"][first] += 1
    (signed / E.MANIFEST).write_text(json.dumps(m))
    assert "manifest_tampered" in E.verify_set(signed, signing_key=skey).codes
    assert "manifest_signature_key_mismatch" in E.verify_set(signed, signing_key=crypto.parse_key(crypto.generate_key())).codes
    assert "manifest_unsigned" in E.verify_set(plain, require_signature=True).codes
    r = E.restore_set(plain, target_root=tmp_path / "r", execute=True, require_signature=True)
    assert not r.ok and not (tmp_path / "r").exists()


# ===================================================================== encryption at rest
@pytest.mark.parametrize("env", ["production", "staging", "preview", "totally-unknown"])
def test_hosted_environments_refuse_an_unencrypted_set_and_write_nothing(src, tmp_path, env):
    out = tmp_path / "set"
    rep = E.create_set(src, out_dir=out, execute=True, api_env=env)
    assert not rep.ok and "encryption_required" in rep.codes and not out.exists()


def test_hosted_set_is_allowed_when_sealed_or_when_encrypted_storage_is_attested_and_the_attestation_is_not_a_verification(src, tmp_path):
    sealed = make_set(src, tmp_path / "a", api_env="production", encryption_key=KEY)
    assert sealed.details["encryption"] == "aes-256-gcm-chunked" and sealed.details["signed"] is True and "encryption_required" not in sealed.codes
    att = make_set(src, tmp_path / "b", api_env="production", storage_encrypted_attested=True)
    assert "encryption_attested_not_verified" in att.codes and E.load_manifest(tmp_path / "b")["encryption"]["mode"] == "storage_attested"
    assert "NOT verified" in E.load_manifest(tmp_path / "b")["encryption"]["note"]
    local = E.create_set(src, out_dir=tmp_path / "c", execute=True, api_env="development")
    assert local.ok and "unencrypted_set" in local.codes and E.load_manifest(tmp_path / "c")["encryption"]["mode"] == "none"
    assert E.verify_set(tmp_path / "c", require_encryption=True).codes[0] == "set_not_encrypted"


def test_a_sealed_set_holds_no_plaintext_and_needs_the_right_key(src, tmp_path):
    plain, sealed = tmp_path / "plain", tmp_path / "sealed"
    make_set(src, plain)
    make_set(src, sealed, encryption_key=KEY)
    m = E.load_manifest(sealed)
    doc = sorted(k for k in m["files"] if k.startswith("documents/"))[0]
    original = (plain / doc).read_bytes()
    assert original not in blobs(sealed) and b"SQLite format 3" not in blobs(sealed) and b"Synthetic private document" not in blobs(sealed)
    assert E.verify_set(sealed, encryption_key=KEY).ok
    assert "plaintext_not_verified_no_key" in E.verify_set(sealed).codes            # checksums of the sealed files still verify without the key
    wrong = E.verify_set(sealed, encryption_key=crypto.parse_key(crypto.generate_key()))
    assert not wrong.ok and "encryption_key_mismatch" in wrong.codes
    r = E.restore_set(sealed, target_root=tmp_path / "r", execute=True)
    assert not r.ok and r.codes == ["encryption_key_missing"] and not (tmp_path / "r").exists()
    r = E.restore_set(sealed, target_root=tmp_path / "r2", execute=True, encryption_key=KEY)
    assert r.ok and (tmp_path / "r2" / doc).read_bytes() == original


def test_a_sealed_file_cannot_be_modified_swapped_between_names_or_truncated_even_with_the_manifest_adjusted(src, tmp_path):
    out = tmp_path / "set"
    make_set(src, out, encryption_key=KEY)
    m = json.loads((out / E.MANIFEST).read_text())
    docs = sorted(k for k in m["files"] if k.startswith("documents/"))
    a, b = out / m["files"][docs[0]]["stored"], out / m["files"][docs[1]]["stored"]
    da, db = a.read_bytes(), b.read_bytes()
    a.write_bytes(db)
    b.write_bytes(da)                                                               # swap: the checksums of the two stored files no longer match
    assert not E.verify_set(out, encryption_key=KEY).ok
    for name, e in ((docs[0], db), (docs[1], da)):                                  # the attacker also fixes the stored checksums in the manifest ...
        m["files"][name]["stored_sha256"] = hashlib.sha256(e).hexdigest()
    (out / E.MANIFEST).write_text(json.dumps(m))
    r = E.verify_set(out, encryption_key=KEY)
    assert not r.ok and ("manifest_tampered" in r.codes)                            # ... but cannot re-sign: the signature key is derived from the sealing key
    # even if the manifest were trusted, the authenticated encryption binds each file to its own name and set
    with pytest.raises(crypto.CryptoError):
        crypto.sealed_sha256(a, KEY, set_id=m["set_id"], logical=docs[0])
    a.write_bytes(db[: len(db) // 2])
    with pytest.raises(crypto.CryptoError):
        crypto.sealed_sha256(a, KEY, set_id=m["set_id"], logical=docs[0])


def test_key_handling_never_leaks_the_key_and_rejects_bad_keys(src, tmp_path, monkeypatch, capsys):
    for bad in (None, "", "   ", "not-base64!!", base64_of(b"short"), base64_of(b"x" * 33)):
        with pytest.raises(crypto.CryptoError) as exc:
            crypto.parse_key(bad)
        assert exc.value.code in ("encryption_key_missing", "encryption_key_invalid") and (not (bad or "").strip() or bad.strip() not in str(exc.value))
    assert crypto.generate_key() != crypto.generate_key() and len(crypto.fingerprint(KEY)) == 8 and KEY_TEXT not in crypto.fingerprint(KEY)
    out = tmp_path / "set"
    make_set(src, out, encryption_key=KEY)
    everything = blobs(out).decode("latin-1")
    assert KEY_TEXT not in everything and KEY.hex() not in everything and KEY not in blobs(out)
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", KEY_TEXT)
    sys.path.insert(0, str(ROOT / "scripts"))
    import backup_set as cli
    assert cli.main(["verify", "--set", str(out)]) == 0
    printed = capsys.readouterr().out
    assert KEY_TEXT not in printed and not PATHISH.search(printed)
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", "garbage")
    assert cli.main(["verify", "--set", str(out)]) == 1
    printed = capsys.readouterr().out
    assert "garbage" not in printed and "encryption_key_invalid" in printed


def base64_of(b: bytes) -> str:
    import base64

    return base64.b64encode(b).decode()


# ===================================================================== restore
def test_restore_dry_run_writes_nothing_and_execute_restores_everything_into_a_separate_environment(src, tmp_path):
    out = tmp_path / "set"
    make_set(src, out)
    target = tmp_path / "restored"
    plan = E.restore_set(out, target_root=target)
    assert plan.ok and plan.executed is False and not target.exists()
    live_before = (tree(Path(src.documents_dir)), E.table_counts(src.database_url))
    rep = E.restore_set(out, target_root=target, execute=True)
    assert rep.ok, rep.codes
    m = E.load_manifest(out)
    lay = E.restore_layout(target)
    assert E.table_counts(f"sqlite:///{lay['database']}") == m["database"]["row_counts"]
    assert tree(lay["documents"]) == tree(Path(src.documents_dir))
    assert tree(lay["knowledge_files"]) == tree(Path(src.knowledge_files_dir))
    assert (tree(Path(src.documents_dir)), E.table_counts(src.database_url)) == live_before         # the source was not touched


def test_restore_refuses_a_non_empty_target_and_never_overwrites_a_file_in_it(src, tmp_path):
    out = tmp_path / "set"
    make_set(src, out)
    target = tmp_path / "restored"
    (target / "documents").mkdir(parents=True)
    precious = target / "documents" / "precious"
    precious.write_bytes(b"do not overwrite")
    r = E.restore_set(out, target_root=target, execute=True)
    assert not r.ok and r.codes == ["target_not_empty"] and precious.read_bytes() == b"do not overwrite" and not (target / "database").exists()
    done = tmp_path / "done"
    assert E.restore_set(out, target_root=done, execute=True).ok
    again = E.restore_set(out, target_root=done, execute=True)
    assert not again.ok and "target_not_empty" in again.codes


def test_restore_of_a_tampered_set_is_refused_before_anything_is_written(src, tmp_path):
    out = tmp_path / "set"
    make_set(src, out)
    m = E.load_manifest(out)
    victim = out / m["files"][m["database"]["file"]]["stored"]
    data = victim.read_bytes()
    victim.write_bytes(data[:100] + bytes([data[100] ^ 1]) + data[101:])
    r = E.restore_set(out, target_root=tmp_path / "r", execute=True)
    assert not r.ok and r.codes[0] == "backup_integrity_failed" and "file_checksum_mismatch" in r.codes and not (tmp_path / "r").exists()


def test_restore_detects_a_row_count_mismatch_instead_of_reporting_success(src, tmp_path, monkeypatch):
    out = tmp_path / "set"
    make_set(src, out)
    real = E.verify_restored_environment

    def fewer(manifest, db_url, root):
        con = sqlite3.connect(db_url.replace("sqlite:///", ""))
        con.execute("DELETE FROM candidate_documents")
        con.commit()
        con.close()
        return real(manifest, db_url, root)

    monkeypatch.setattr(E, "verify_restored_environment", fewer)
    r = E.restore_set(out, target_root=tmp_path / "r", execute=True)
    assert not r.ok and "row_count_mismatch" in r.codes


def test_postgresql_commands_pass_credentials_through_the_environment_never_the_command_line(tmp_path):
    url = "postgresql+psycopg://appuser:S3cretPassw0rd@db.internal:5432/ask4mo"
    env, args = E._pg_env_and_args(url)
    assert env["PGPASSWORD"] == "S3cretPassw0rd" and "S3cretPassw0rd" not in " ".join(args) and args[-2:] == ["--dbname", "ask4mo"]
    stub = tmp_path / "pg_dump"
    stub.write_text("#!/bin/sh\necho 'connection to db.internal as appuser failed' >&2\nexit 1\n")
    stub.chmod(0o755)
    with pytest.raises(E.SetError) as exc:
        E._run_pg(str(stub), ["--x"], env, "pg_dump_failed")
    assert exc.value.code == "pg_dump_failed" and "appuser" not in str(exc.value) and "db.internal" not in str(exc.value)
    with pytest.raises(E.SetError) as exc:
        E._run_pg(str(tmp_path / "missing"), [], env, "pg_dump_failed")
    assert exc.value.code == "pg_dump_failed_tool_missing"
    assert E._pg_target_problems("postgresql://u:p@h/ask4mo_production") == ["target_database_name_refused"]      # refused before any connection
    assert E._pg_target_problems("sqlite:///x.db") == ["postgresql_required"]


# ===================================================================== restore drill harness and record
def drill_run(src, tmp_path, **kw):
    kw.setdefault("api_env", "test")
    return D.run_drill(src, work_dir=tmp_path / "work", record_dir=tmp_path / "records", **kw)


def test_restore_drill_passes_on_a_sealed_signed_set_and_writes_json_and_markdown_records(src, tmp_path):
    res = drill_run(src, tmp_path, label="sealed", encryption_key=KEY, commit_sha="abc1234")
    by = {c["id"]: c["result"] for c in res.record["checks"]}
    assert res.overall == "PASS", by
    for needed in ("backup_set_created", "set_verified", "restore_dry_run_writes_nothing", "restore_executed", "restore_refuses_non_empty_target", "schema_revision_matches",
                   "row_counts_match", "document_checksums_match", "knowledge_files_match", "index_checksum_matches", "retrieval_parity", "tamper_file_detected",
                   "tamper_restore_refused", "tamper_unlisted_file_detected", "tamper_manifest_detected", "source_unchanged"):
        assert by[needed] == "PASS", needed
    rd = tmp_path / "records"
    data = json.loads((rd / res.json_name).read_text())
    md = (rd / res.md_name).read_text()
    assert data == res.record and data["hosted_verification"] == "NOT RUN (OD-HOSTED)" and data["kind"] == "offline_synthetic" and data["commit_sha"] == "abc1234"
    assert data["set"]["encryption"] == "aes-256-gcm-chunked" and data["set"]["signed"] and data["set"]["rows"] > 0 and data["set"]["chunks"] == 4
    assert "NOT RUN (OD-HOSTED)" in md and "retrieval probes" in md and "Not exercised" in md
    blob = json.dumps(data) + md
    assert not PATHISH.search(blob) and KEY_TEXT not in blob and "example.invalid" not in blob


def test_an_unsigned_set_is_partial_because_manifest_edits_are_not_detectable_without_a_signature(src, tmp_path):
    res = drill_run(src, tmp_path, label="plain")
    by = {c["id"]: c["result"] for c in res.record["checks"]}
    assert res.overall == "PARTIAL" and by["tamper_manifest_detected"] == "NOT_RUN" and "FAIL" not in by.values()


def test_a_drill_that_cannot_back_up_records_a_fail_and_never_raises(src, tmp_path):
    enqueue_job(src)
    res = drill_run(src, tmp_path, label="busy")
    assert res.overall == "FAIL" and res.record["checks"][0]["id"] == "backup_set_created" and "jobs_active" in res.record["checks"][0]["detail"]["codes"]
    assert (tmp_path / "records" / res.json_name).is_file()


def test_drill_records_are_never_overwritten_and_inputs_are_validated(src, tmp_path):
    when = clock(T0)
    drill_run(src, tmp_path, label="once", clock=when)
    with pytest.raises(ValueError):
        D.run_drill(src, work_dir=tmp_path / "work2", record_dir=tmp_path / "records", label="bad label!")
    with pytest.raises(ValueError):
        D.run_drill(src, work_dir=tmp_path / "work2", record_dir=tmp_path / "records", label="x", commit_sha="not a sha")
    with pytest.raises(ValueError):
        D.run_drill(src, work_dir=tmp_path / "work", record_dir=tmp_path / "records", label="x")          # a used work directory is refused
    with pytest.raises(FileExistsError):
        D.run_drill(src, work_dir=tmp_path / "work3", record_dir=tmp_path / "records", label="once", clock=when)


def test_the_drill_detects_index_drift_between_the_set_and_the_live_source(src, tmp_path, monkeypatch):
    real = D.collection_checksum
    monkeypatch.setattr(D, "collection_checksum", lambda chunks: "0" * 64 if len(chunks) == 4 else real(chunks))
    res = drill_run(src, tmp_path, label="drift", encryption_key=KEY)
    by = {c["id"]: c["result"] for c in res.record["checks"]}
    assert by["index_checksum_matches"] == "FAIL" and res.overall == "FAIL"


def test_the_drill_cli_writes_a_record_and_reports_partial_or_pass_through_its_exit_status(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", KEY_TEXT)
    sys.path.insert(0, str(ROOT / "scripts"))
    import restore_drill as cli

    rc = cli.main(["--synthetic", "--record-dir", str(tmp_path / "rec"), "--label", "cli", "--encrypt"])
    out = capsys.readouterr().out
    assert rc == 0 and '"overall": "PASS"' in out and KEY_TEXT not in out and not PATHISH.search(out)
    assert len(list((tmp_path / "rec").glob("drill-*-cli.json"))) == 1 and len(list((tmp_path / "rec").glob("drill-*-cli.md"))) == 1


# ===================================================================== backup erasure after account deletion (PRIV-BACKUP)
def live_delete(source, user_id):
    from src.application.account_deletion_service import AccountDeletionService
    from src.documents.storage import LocalDocumentStore

    eng = make_engine(source.database_url)
    try:
        return AccountDeletionService(make_session_factory(eng), document_store=LocalDocumentStore(str(source.documents_dir))).delete_account(user_id)
    finally:
        eng.dispose()


def users_in(set_dir, key=None):
    return X._users_in_set(Path(set_dir), E.load_manifest(set_dir), key)


@pytest.fixture()
def world(tmp_path, src):
    """Set A taken at T0 (holds user 1), user 1 deleted LIVE and recorded in the ledger at T1, set C taken at T2 (does not hold user 1)."""
    sets = tmp_path / "sets"
    ledger = X.Ledger(tmp_path / "ledger" / "erasure.jsonl", clock=clock(T1))
    a = sets / "a"
    make_set(src, a, clock=clock(T0))
    X.register_set(ledger, a)
    summary = live_delete(src, 1)
    assert summary.existed and summary.files_purged == 2
    X.record_deletion(ledger, 1, T1)
    c = sets / "c"
    make_set(src, c, clock=clock(T2))
    X.register_set(ledger, c)
    return type("W", (), {"src": src, "sets": sets, "ledger": ledger, "a": a, "c": c, "tmp": tmp_path})


def test_the_ledger_is_append_only_hash_chained_and_detects_edits_deletions_and_reordering(tmp_path):
    ledger = X.Ledger(tmp_path / "l.jsonl", clock=clock(T1))
    X.record_deletion(ledger, 7, T0)
    X.record_deletion(ledger, 8, T0)
    assert X.record_deletion(ledger, 7, T1)["seq"] == 1 and len(ledger.entries()) == 2          # idempotent per account
    assert ledger.verify() == []
    lines = (tmp_path / "l.jsonl").read_text().splitlines()
    for mutated in (["tampered".join(lines[0].split("7", 1))] + lines[1:], lines[1:], [lines[1], lines[0]]):
        (tmp_path / "l2.jsonl").write_text("\n".join(mutated) + "\n")
        assert X.Ledger(tmp_path / "l2.jsonl").verify() == ["ledger_tampered"]
    with pytest.raises(X.ErasureError):
        X.Ledger(tmp_path / "l2.jsonl").append("deletion_recorded", user_id=9, deleted_at=T0.isoformat())     # never extends a broken chain
    for bad in (0, -1, True, "7"):
        with pytest.raises(X.ErasureError):
            X.record_deletion(ledger, bad, T0)
    link = tmp_path / "link.jsonl"
    link.symlink_to(tmp_path / "l.jsonl")
    assert X.Ledger(link).verify() == ["ledger_symlink_refused"]


def test_the_window_is_stated_and_the_plan_never_claims_erasure_from_a_set_that_was_not_rewritten_or_destroyed(world):
    assert X.ERASURE_WINDOW_DAYS == X.BACKUP_RETENTION_DAYS == 35
    assert 1 in users_in(world.a) and 1 not in users_in(world.c)                                   # the older set holds the deleted account, the newer does not
    p = X.plan(world.ledger, world.sets, now=T1 + timedelta(days=1))
    rows = {r["set_id"]: r for r in p["sets"]}
    a_id, c_id = E.load_manifest(world.a)["set_id"], E.load_manifest(world.c)["set_id"]
    assert p["erasure_claim"] == "incomplete" and p["sets_open"] == 1 and rows[a_id]["status"] == "open" and rows[c_id]["status"] == "closed"
    d = rows[a_id]["deletions"][0]
    assert d["state"] == "contains_account" and d["open"] and not d["overdue"] and d["window_ends"] == (T1 + timedelta(days=35)).isoformat()
    assert "still holds the data" in p["claim_basis"] and "IS still in those sets" in p["policy"]["meaning"]
    late = X.plan(world.ledger, world.sets, now=T1 + timedelta(days=36))
    assert late["overdue_entries"] == 1 and late["erasure_claim"] == "incomplete"


def test_rewrite_produces_a_new_set_without_the_account_and_never_touches_or_deletes_the_original(world):
    before = tree(world.a)
    new = world.sets / "a2"
    dry = X.rewrite_set(world.a, new, world.ledger)
    assert dry.ok and dry.counts == {"accounts_to_erase": 1} and not new.exists()                  # dry-run by default
    rep = X.rewrite_set(world.a, new, world.ledger, execute=True, api_env="test")
    assert rep.ok, rep.codes
    assert tree(world.a) == before and E.verify_set(world.a).ok                                    # the original is byte-identical and still present
    assert rep.details["original_set_must_be_destroyed"] is True and rep.details["erasure_claim"].startswith("none")
    assert 1 not in users_in(new) and 2 in users_in(new) and E.verify_set(new).ok
    ma, mn = E.load_manifest(world.a), E.load_manifest(new)
    assert mn["documents"]["count"] == ma["documents"]["count"] - 2 and mn["rewrites"]["erased_user_ids"] == [1] and mn["rewrites"]["rewritten_from_set_id"] == ma["set_id"]
    assert mn["knowledge"]["index_checksum"] == ma["knowledge"]["index_checksum"]                  # shared knowledge is unchanged
    restored = E.restore_set(new, target_root=world.tmp / "r", execute=True)
    assert restored.ok
    p = X.plan(world.ledger, world.sets, now=T1 + timedelta(days=2))
    assert p["erasure_claim"] == "incomplete"                                                      # a rewrite alone is NOT erasure: the original still exists


def test_rewrite_target_must_be_empty_and_a_second_rewrite_has_nothing_to_do(world):
    out = world.sets / "a2"
    out.mkdir()
    (out / "keep").write_text("x")
    r = X.rewrite_set(world.a, out, world.ledger, execute=True, api_env="test")
    assert not r.ok and "backup_target_not_empty" in r.codes and (out / "keep").read_text() == "x"
    r = X.rewrite_set(world.c, world.sets / "c2", world.ledger, execute=True, api_env="test")        # set C was taken after the deletion
    assert r.ok and "nothing_to_rewrite" in r.codes and not (world.sets / "c2").exists()


def test_a_sealed_set_is_rewritten_into_a_sealed_signed_set(tmp_path, src):
    sets = tmp_path / "sets"
    ledger = X.Ledger(tmp_path / "l.jsonl", clock=clock(T1))
    make_set(src, sets / "a", clock=clock(T0), encryption_key=KEY)
    live_delete(src, 1)
    X.record_deletion(ledger, 1, T1)
    keyless = X.rewrite_set(sets / "a", sets / "a2", ledger, execute=True)
    assert not keyless.ok and "encryption_key_missing" in keyless.codes and not (sets / "a2").exists()
    rep = X.rewrite_set(sets / "a", sets / "a2", ledger, execute=True, encryption_key=KEY, new_encryption_key=KEY, api_env="production")
    assert rep.ok, rep.codes
    m = E.load_manifest(sets / "a2")
    assert m["encryption"]["mode"] == "aes-256-gcm-chunked" and m.get("signature") and E.verify_set(sets / "a2", encryption_key=KEY).ok
    assert users_in(sets / "a2") is None and 1 not in users_in(sets / "a2", KEY)                   # not inspectable without the key


def test_the_full_procedure_ends_in_a_complete_claim_only_per_operator_attestation_of_the_destruction(world):
    a_id = E.load_manifest(world.a)["set_id"]
    new = world.sets / "a2"
    assert X.rewrite_set(world.a, new, world.ledger, execute=True, api_env="test").ok
    with pytest.raises(X.ErasureError) as e:
        X.attest_destruction(world.ledger, a_id, attested_by="ops-1", reason="rewritten", sets_dir=world.sets)
    assert e.value.code == "set_still_present"                                                     # the tool refuses an attestation while the set is on disk
    with pytest.raises(X.ErasureError) as e:
        X.attest_destruction(world.ledger, "f" * 32, attested_by="ops-1", reason="rewritten")
    assert e.value.code == "set_not_rewritten"
    with pytest.raises(X.ErasureError) as e:
        X.attest_destruction(world.ledger, a_id, attested_by="ops-1", reason="expired", now=T1 + timedelta(days=1))
    assert e.value.code == "set_not_expired"
    for bad in ({"set_id": "nothex", "attested_by": "ops", "reason": "rewritten"}, {"set_id": a_id, "attested_by": "bad/label\n", "reason": "rewritten"},
                {"set_id": a_id, "attested_by": "ops", "reason": "because"}):
        with pytest.raises(X.ErasureError):
            X.attest_destruction(world.ledger, **bad)
    shutil.move(str(world.a), str(world.tmp / "destroyed-by-operator"))                            # the operator removes the original (this tool never deletes)
    absent = X.plan(world.ledger, world.sets, now=T1 + timedelta(days=2))
    row = next(r for r in absent["sets"] if r["set_id"] == a_id)
    assert row["deletions"][0]["state"] == "absent_without_attestation" and absent["erasure_claim"] == "incomplete"      # gone without a record is NOT erased
    att = X.attest_destruction(world.ledger, a_id, attested_by="ops-1", reason="rewritten", sets_dir=world.sets)
    assert att["verified_by_tool"] is False
    assert X.attest_destruction(world.ledger, a_id, attested_by="ops-2", reason="rewritten")["seq"] == att["seq"]     # idempotent
    done = X.plan(world.ledger, world.sets, now=T1 + timedelta(days=3))
    assert done["erasure_claim"] == "complete_per_operator_attestation" and done["sets_open"] == 0 and "not technically verified" in done["claim_basis"]
    assert world.ledger.verify() == []


def test_an_expired_set_closes_by_destruction_at_retention_age_and_an_unregistered_or_contradicted_set_keeps_the_claim_incomplete(world):
    a_id = E.load_manifest(world.a)["set_id"]
    stray = world.sets / "stray"
    make_set(world.src, stray, clock=clock(T2))                                                   # taken after the deletion but never registered in the ledger
    p = X.plan(world.ledger, world.sets, now=T1 + timedelta(days=1))
    assert p["unregistered_sets_present"] == 1
    X.register_set(world.ledger, stray)
    X.attest_destruction(world.ledger, a_id, attested_by="ops-1", reason="expired", now=T0 + timedelta(days=36))
    contradicted = X.plan(world.ledger, world.sets, now=T0 + timedelta(days=37))
    assert next(r for r in contradicted["sets"] if r["set_id"] == a_id)["deletions"][0]["state"] == "attested_destroyed_but_still_present"
    assert contradicted["erasure_claim"] == "incomplete"                                           # attested but still on disk: contradiction, never complete
    shutil.move(str(world.a), str(world.tmp / "destroyed"))
    assert X.plan(world.ledger, world.sets, now=T0 + timedelta(days=37))["erasure_claim"] == "complete_per_operator_attestation"


def test_a_tampered_ledger_makes_the_plan_report_ledger_invalid_and_never_complete(world):
    path = world.ledger.path
    lines = path.read_text().splitlines()
    path.write_text("\n".join(lines[1:]) + "\n")
    p = X.plan(world.ledger, world.sets)
    assert p["erasure_claim"] == "ledger_invalid" and p["ledger_problems"] == ["ledger_tampered"]
    assert X.rewrite_set(world.a, world.sets / "x", world.ledger, execute=True).codes == ["ledger_tampered"]


def test_restoring_an_old_backup_resurrects_a_deleted_account_and_the_ledger_re_deletes_it(world):
    target = world.tmp / "restored-old"
    assert E.restore_set(world.a, target_root=target, execute=True).ok
    lay = E.restore_layout(target)
    con = sqlite3.connect(lay["database"])
    assert con.execute("SELECT COUNT(*) FROM users WHERE id = 1").fetchone()[0] == 1 and con.execute("SELECT COUNT(*) FROM candidate_documents WHERE user_id = 1").fetchone()[0] == 2
    con.close()
    dry = X.reapply_after_restore(world.ledger, target)
    assert dry.ok and dry.counts == {"ledger_accounts": 1, "present_in_restored_environment": 1}
    assert sqlite3.connect(lay["database"]).execute("SELECT COUNT(*) FROM users WHERE id = 1").fetchone()[0] == 1               # dry-run changed nothing
    rep = X.reapply_after_restore(world.ledger, target, execute=True)
    assert rep.ok, rep.codes
    con = sqlite3.connect(lay["database"])
    assert con.execute("SELECT COUNT(*) FROM users WHERE id = 1").fetchone()[0] == 0 and con.execute("SELECT COUNT(*) FROM candidate_documents WHERE user_id = 1").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM users WHERE id = 2").fetchone()[0] == 1
    con.close()
    assert len(list(lay["documents"].iterdir())) == 2
    assert X.reapply_after_restore(world.ledger, target, execute=True).counts["present_in_restored_environment"] == 0       # idempotent


def test_checkpoint_threads_in_the_snapshot_are_purged_with_the_official_saver_and_a_snapshot_without_the_saver_has_nothing_to_purge(tmp_path):
    db = tmp_path / "c.sqlite"
    con = sqlite3.connect(db)
    assert X._SqliteCheckpointPurger(db).purge_run("run-a") is True                                # no saver tables: nothing in this database
    from langgraph.checkpoint.sqlite import SqliteSaver

    SqliteSaver(con).setup()
    for thread in ("run-a", "run-b"):
        con.execute("INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, type, checkpoint, metadata) VALUES (?, '', ?, 'json', x'00', x'00')", (thread, "1"))
    con.commit()
    con.close()
    assert X._SqliteCheckpointPurger(db).purge_run("run-a")
    con = sqlite3.connect(db)
    assert [r[0] for r in con.execute("SELECT thread_id FROM checkpoints")] == ["run-b"]
    con.close()


def test_erase_cli_round_trip_reports_codes_and_never_a_path(world, capsys, monkeypatch):
    sys.path.insert(0, str(ROOT / "scripts"))
    import backup_set as cli

    led = str(world.ledger.path)
    assert cli.main(["erase", "plan", "--ledger", led, "--sets-dir", str(world.sets)]) == 1
    out = capsys.readouterr().out
    assert '"erasure_claim": "incomplete"' in out and not PATHISH.search(out)
    assert cli.main(["erase", "rewrite", "--ledger", led, "--set", str(world.a), "--out", str(world.sets / "a2")]) == 0
    assert not (world.sets / "a2").exists()                                                         # dry-run
    capsys.readouterr()
    assert cli.main(["erase", "attest-destroyed", "--ledger", led, "--set-id", E.load_manifest(world.a)["set_id"], "--by", "ops", "--reason", "rewritten"]) == 1
    assert "set_not_rewritten" in capsys.readouterr().out
    assert cli.main(["erase", "record-deletion", "--ledger", led, "--user-id", "5"]) == 0


# ===================================================================== static guarantees
def test_no_command_line_flag_accepts_a_key_and_no_module_loads_a_dotenv_or_prints():
    cli = (ROOT / "scripts" / "backup_set.py").read_text()
    assert "--key" not in cli and "--password" not in cli and "--encryption-key" not in cli
    for p in (ROOT / "src" / "backup_set").glob("*.py"):
        text = p.read_text()
        assert "load_dotenv" not in text and not re.search(r"(?<![\w.])print\(", text), p.name


def test_the_staging_compose_file_was_not_edited_by_this_package():
    out = subprocess.run(["git", "diff", "--name-only", "origin/main", "--", "deploy/docker-compose.staging.yml"], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode != 0 or out.stdout.strip() == ""                    # no origin/main ref (a shallow checkout) is tolerated; any real diff fails
