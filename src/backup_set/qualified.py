"""Qualified PostgreSQL recovery over the existing 05B AES-GCM backup-set engine.

All writes require execute=True. Sources/sets are never deleted or overwritten.
Only new isolated targets are supported; no promotion or accounting release exists.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from src.backup_set import engine as E, erasure as X
from src.knowledge_admin.recovery import Report

FORMAT = 1
QUALIFIED = "qualified_recovery"
# Explicitly reviewed revisions only; never infer compatibility with a future head.
RECOVERY_REVISIONS = ("0047_workspace_ownership_transfers", "0048_agent_run_controls", "0049_workspace_mail_attempts")
RELEASE_REVISIONS = ("0048_agent_run_controls", "0049_workspace_mail_attempts")
EMAIL_TYPES_0049 = ("email_verification", "password_reset", "account_notice", "admin_test", "workspace_invitation", "ownership_transfer")


def require(ok, code):
    if not ok:
        raise E.SetError(code)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def identity(url):
    u = make_url(url)
    require(u.get_backend_name() == "postgresql" and u.database and u.host, "postgresql_required")
    require(not set(u.query) - {"sslmode", "sslrootcert", "sslcert", "sslkey", "sslcrl", "connect_timeout"}, "database_options_unsupported")
    return _hash([u.host, u.port or 5432, u.database])


def file_tree(root):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "source_component_missing")
    require(not any(p.is_symlink() for p in root.rglob("*")), "source_symlink_refused")
    return {p.relative_to(root).as_posix(): E.sha_file(p) for p in sorted(root.rglob("*")) if p.is_file()}


def client_version(binary):
    try:
        out = subprocess.run([binary, "--version"], capture_output=True, text=True, check=True, timeout=10).stdout
    except Exception:
        raise E.SetError("postgresql_client_unavailable") from None
    version = re.search(r"PostgreSQL\) (16\.\d+)", out)
    require(version is not None, "postgresql_16_client_required")
    return version.group(1)


def _canonical_definition(value):
    # PostgreSQL's dump/parser distributes a varchar[] -> text[] cast over
    # literal array members. Canonicalize only that exact, semantics-preserving
    # form; retain all constraint names, expressions, types and other casts.
    if not isinstance(value, str):
        return value
    pattern = r"\(\(ARRAY\[(('(?:[^']|'')*'::character varying)(?:, '(?:[^']|'')*'::character varying)*)\]\)::text\[\]\)"
    def distribute(match):
        literals = re.findall(r"'(?:[^']|'')*'::character varying", match.group(1))
        return "(ARRAY[" + ", ".join("(" + item + ")::text" for item in literals) + "])"
    return re.sub(pattern, distribute, value)


def schema_objects(connection):
    """Stable, non-OID definitions, including constraints, triggers and sequence state."""
    queries = [
        "SELECT table_name,column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' ORDER BY 1,2",
        "SELECT conrelid::regclass::text,conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY 1,2",
        "SELECT tgrelid::regclass::text,tgname,pg_get_triggerdef(oid) FROM pg_trigger WHERE NOT tgisinternal AND tgrelid IN (SELECT oid FROM pg_class WHERE relnamespace='public'::regnamespace) ORDER BY 1,2",
        "SELECT sequencename,start_value,min_value,max_value,increment_by,cycle,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY 1",
        "SELECT p.proname,pg_get_functiondef(p.oid) FROM pg_proc p WHERE p.pronamespace='public'::regnamespace AND p.prokind='f' ORDER BY 1,2",
    ]
    return _hash([[[_canonical_definition(v) for v in row] for row in connection.execute(text(q))] for q in queries])



def extended_schema_objects(connection):
    """Index and view definitions, recorded separately to preserve older set format."""
    queries = [
        "SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY 1,2",
        "SELECT viewname,definition FROM pg_views WHERE schemaname='public' ORDER BY 1",
        "SELECT matviewname,definition FROM pg_matviews WHERE schemaname='public' ORDER BY 1",
    ]
    return _hash([[[_canonical_definition(v) for v in row] for row in connection.execute(text(q))] for q in queries])


def _require_reviewed_schema(connection, revision, names):
    require(revision in RECOVERY_REVISIONS, "recovery_schema_unsupported")
    if revision in RECOVERY_REVISIONS[1:]:
        require("agent_run_controls" in names, "recovery_schema_unsupported")
    if revision == RECOVERY_REVISIONS[2]:
        require("email_attempts" in names, "recovery_schema_unsupported")
        definition = connection.execute(text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='public.email_attempts'::regclass AND conname='ck_email_attempts_type' AND contype='c' AND convalidated")).scalar_one_or_none()
        literals = ", ".join("'" + value + "'::character varying" for value in EMAIL_TYPES_0049)
        expected = "CHECK (((message_type)::text = ANY ((ARRAY[" + literals + "])::text[])))"
        require(definition is not None and _canonical_definition(definition) == _canonical_definition(expected), "recovery_schema_unsupported")
        indexes = {row[0] for row in connection.execute(text("SELECT indexname FROM pg_indexes WHERE schemaname='public' AND tablename='email_attempts'"))}
        require({"ix_email_attempts_created", "ix_email_attempts_type_created", "ix_email_attempts_message_ref"} <= indexes, "recovery_schema_unsupported")

def database_content_fingerprint(connection, names):
    """Hash every row, including unknown usage, credentials and checkpoints.

    Only the final digest leaves the process. No row values enter the report.
    """
    digest = hashlib.sha256()
    for name in names:
        name = E._check_ident(name)
        digest.update(name.encode() + b"\0")
        for (row,) in connection.execute(text(f'SELECT to_jsonb(t)::text FROM public."{name}" t ORDER BY 1')):
            encoded = row.encode()
            digest.update(len(encoded).to_bytes(8, "big") + encoded)
    return digest.hexdigest()


def money_fingerprint(url):
    engine = E._engine(url)
    try:
        with engine.connect() as c:
            rows = [list(r) for r in c.execute(text("SELECT scope_key,held_micro_usd,requests FROM ai_budget_controls WHERE scope_key != 'global' ORDER BY scope_key"))]
            entries = [list(r) for r in c.execute(text("SELECT * FROM ai_budget_entries ORDER BY id"))]
            return _hash([rows, entries])
    finally:
        engine.dispose()


def _source_checks(source, checkpoint_url, release):
    require(identity(source.database_url) == identity(checkpoint_url), "separate_checkpoint_store_unsupported")
    require(set(release) == {"application_sha", "manifest_sha256", "budget_policy_version", "recovery_policy_version", "migration_head", "prompt_assets_sha256", "language_activation_sha256"}, "release_fields_invalid")
    require(release["migration_head"] in RELEASE_REVISIONS and all(re.fullmatch(r"[0-9a-f]{64}", release[k]) for k in ("prompt_assets_sha256", "language_activation_sha256")), "release_metadata_invalid")
    require(re.fullmatch(r"[0-9a-f]{40}", release.get("application_sha", "")), "release_identity_invalid")
    require(re.fullmatch(r"[0-9a-f]{64}", release.get("manifest_sha256", "")), "release_anchor_invalid")
    require(release.get("budget_policy_version") == 2 and release.get("recovery_policy_version") == 1, "recovery_image_incompatible")
    roots = [source.documents_dir, source.knowledge_files_dir, source.knowledge_index_dir]
    require(all(p is not None for p in roots), "source_component_missing")
    return roots


@contextmanager
def frozen_source(source):
    """Bounded table locks plus exported snapshot; no source data is modified.

    An independently attested producer drain is still required for file writers.
    New tables/schema changes are checked again before manifest publication.
    """
    engine = E._engine(source.database_url)
    try:
        # Inspect before the snapshot transaction. LOCK statements run first in
        # that transaction: pg_dump and all verification then see the committed
        # state AFTER any writer we had to wait for, never a pre-lock snapshot.
        with engine.connect() as check:
            require(check.execute(text("SHOW server_version")).scalar().startswith("16."), "postgresql_16_required")
            require(check.execute(text("SELECT current_schema()")).scalar() == "public", "checkpoint_schema_unsupported")
            schemas = check.execute(text("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname NOT IN ('public','information_schema')")).all()
            require(not schemas, "additional_database_schema_unsupported")
            names = sorted(inspect(check).get_table_names())
        require({"alembic_version", "ai_budget_controls", "ai_budget_entries"} <= set(names), "recovery_schema_unsupported")
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as c:
            c.execute(text("SET LOCAL lock_timeout='5s'"))
            for name in names:
                c.execute(text(f'LOCK TABLE public."{E._check_ident(name)}" IN SHARE MODE'))
            snapshot = c.execute(text("SELECT pg_export_snapshot()")).scalar()
            require(sorted(inspect(c).get_table_names()) == names, "source_schema_changed")
            revisions = list(c.execute(text("SELECT version_num FROM alembic_version")).scalars())
            require(len(revisions) == 1, "recovery_schema_unsupported")
            _require_reviewed_schema(c, revisions[0], names)
            yield c, snapshot, names
    finally:
        engine.dispose()


def _completeness(c, source, names):
    for query, root in [("SELECT storage_key FROM document_versions WHERE storage_key IS NOT NULL", source.documents_dir),
                        ("SELECT storage_key FROM knowledge_source_versions WHERE storage_key IS NOT NULL", source.knowledge_files_dir)]:
        for (key,) in c.execute(text(query)):
            require(E.safe_rel(key) and (Path(root) / key).is_file() and not (Path(root) / key).is_symlink(), "referenced_private_file_missing")
    runs = c.execute(text("SELECT COUNT(*) FROM preparation_runs")).scalar()
    if runs:
        require({"checkpoints", "checkpoint_writes", "checkpoint_blobs"} <= set(names), "checkpoint_component_missing")
    if "checkpoints" in names:
        # Without a durable owner/run mapping, a later erasure could not identify
        # whose historical checkpoint must be purged. Refuse the recovery point.
        orphan = "SELECT 1 FROM checkpoints c WHERE NOT EXISTS (SELECT 1 FROM preparation_runs p WHERE p.run_id=c.thread_id)"
        if "agent_run_controls" in names:
            orphan += " AND NOT EXISTS (SELECT 1 FROM agent_run_controls a WHERE a.run_id=c.thread_id)"
        require(c.execute(text(orphan + " LIMIT 1")).first() is None, "checkpoint_owner_mapping_missing")
    from src.llm.budget.ledger import DbBudgetLedger
    from src.persistence import make_session_factory
    ledger = DbBudgetLedger(make_session_factory(c.engine))
    ledger.ensure_ready()
    classes = {r[0] for r in c.execute(text("SELECT DISTINCT budget_class FROM ai_budget_entries"))}
    require(all(ledger.integrity(k)["consistent"] for k in classes), "budget_ledger_inconsistent")
    if c.execute(text("SELECT COUNT(*) FROM knowledge_index_records WHERE state='built'")).scalar():
        require((Path(source.knowledge_index_dir) / "chroma.sqlite3").is_file(), "knowledge_index_missing")
        require(source.identity is not None and source.identity.embedding.provider is not None and source.identity.embedding.model is not None,
                "embedding_identity_missing")
        from src.copilot.index_manifest import manifest_file, read_manifest
        from src.knowledge_admin.policy import COLLECTION
        manifest = read_manifest(manifest_file(source.knowledge_index_dir, COLLECTION))
        require(manifest is not None and all(getattr(manifest, k) == getattr(source.identity.embedding, k)
                                            for k in ("provider", "model", "dimensions")), "embedding_identity_mismatch")


def create(source, *, out_dir, checkpoint_database_url, release, ledger, ledger_head, ledger_key,
           encryption_key, signing_key=None, execute=False, drained=False, drain_observed_at=None, pg_dump_bin="pg_dump", rewrites=None):
    started = time.perf_counter()
    require(isinstance(encryption_key, bytes) and len(encryption_key) == 32, "encryption_key_invalid")
    require(encryption_key != ledger_key, "independent_ledger_key_required")
    roots = _source_checks(source, checkpoint_database_url, release)
    X.require_head(ledger, ledger_head, ledger_key)
    require(drained is True and drain_observed_at is not None and
            0 <= (datetime.now(timezone.utc) - drain_observed_at).total_seconds() <= 300, "fresh_producer_drain_required")
    fingerprints = [file_tree(p) for p in roots]
    out = Path(out_dir)
    require(not out.exists() and not out.is_symlink(), "backup_target_exists")
    require(not any(E._is_inside(out, Path(p)) or E._is_inside(ledger.path, Path(p)) or E._is_inside(ledger.path, out) for p in roots), "recovery_paths_overlap")
    version = client_version(pg_dump_bin)
    if not execute:
        return Report("qualified_backup", False, details={"postgresql_client": version})
    out.mkdir(parents=True, mode=0o700, exist_ok=False)
    with frozen_source(source) as (c, snapshot, names), tempfile.TemporaryDirectory(prefix="a4m-qualified-") as work:
        require(E.active_jobs(source.database_url) == 0, "jobs_active")
        _completeness(c, source, names)
        source_revision = c.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        require(RECOVERY_REVISIONS.index(source_revision) <= RECOVERY_REVISIONS.index(release["migration_head"]), "recovery_release_schema_incompatible")
        schema = schema_objects(c)
        extended_schema = extended_schema_objects(c)
        content = database_content_fingerprint(c, names)
        # Opening an index must never rewrite the source's HNSW files.
        index = Path(work) / "index"
        shutil.copytree(source.knowledge_index_dir, index)
        staged = replace(source, knowledge_index_dir=index)
        def before_publish(manifest):
            require(fingerprints == [file_tree(p) for p in roots], "source_changed_during_backup")
            with c.engine.connect() as fresh:
                require(schema_objects(fresh) == schema and extended_schema_objects(fresh) == extended_schema and sorted(inspect(fresh).get_table_names()) == names, "source_schema_changed")
            require(manifest["consistency"]["consistent"] and manifest["knowledge"]["consistent"], "inconsistent_recovery_point")
            X.require_head(ledger, ledger_head, ledger_key)
            manifest[QUALIFIED] = {"format": FORMAT, "release": release, "schema_objects_sha256": schema,
                                   "checkpoint_placement": "shared_public_database", "erasure_head": ledger_head,
                                   "database_content_sha256": content, "extended_schema_sha256": extended_schema, "money_sha256": money_fingerprint(source.database_url), "producer_drain_attested": True,
                                   "consistency": "exported PostgreSQL snapshot + table write locks + content fingerprints"}
        result = E.create_set(staged, out_dir=out, execute=True, api_env="staging", encryption_key=encryption_key,
                              signing_key=signing_key, pg_dump_bin=pg_dump_bin, pg_snapshot=snapshot, private_probe=True,
                              before_publish=before_publish, extra_manifest={"rewrites": rewrites} if rewrites else None)
        require(result.ok, "backup_set_failed")
    verification = E.verify_set(out, encryption_key=encryption_key, signing_key=signing_key, require_signature=True, require_encryption=True)
    require(verification.ok, "backup_verification_failed")
    X.register_set(ledger, out)
    result.details.update(duration_seconds=round(time.perf_counter()-started, 3), postgres_client=version,
                          erasure_head=X.signed_head(ledger, ledger_key), stored_bytes=sum(p.stat().st_size for p in out.rglob('*') if p.is_file()))
    return result


def verify(set_dir, *, anchor, encryption_key, signing_key=None):
    base = Path(set_dir)
    require(not base.is_symlink() and not any(p.is_symlink() for p in base.rglob('*')), "symlink_in_set")
    require(E.manifest_digest(base) == anchor, "backup_anchor_mismatch")
    result = E.verify_set(base, encryption_key=encryption_key, signing_key=signing_key, require_signature=True, require_encryption=True)
    require(result.ok, "backup_integrity_failed")
    m = E.load_manifest(base)
    require(m.get("encryption", {}).get("mode") == "aes-256-gcm-chunked" and
            all(e.get("sealed") for e in m["files"].values()), "sealed_set_required")
    require(m.get(QUALIFIED, {}).get("format") == FORMAT and m["consistency"].get("consistent") is True, "qualified_recovery_point_required")
    require(m["database"]["file"] in m["files"] and "knowledge/manifest.json" in m["files"] and
            "evidence/retrieval-probe.json" in m["files"], "incomplete_recovery_point")
    return m


def quarantine_database(url):
    """Database-level latch is outside pg_dump's restored table history."""
    engine = E._engine(url)
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
            require(c.execute(text("SHOW server_version")).scalar().startswith("16."), "postgresql_16_required")
            require(not inspect(c).get_table_names(), "target_database_not_empty")
            require(c.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid != pg_backend_pid()")).scalar() == 0,
                    "restore_target_in_use")
            name = c.execute(text("SELECT current_database()")).scalar()
            c.execute(text(f'ALTER DATABASE "{E._check_ident(name)}" SET ask4mo.recovery_pending = \'on\''))
    finally:
        engine.dispose()


def restore(set_dir, *, target_root, target_database_url, anchor, ledger, ledger_head, ledger_key, encryption_key,
            signing_key=None, execute=False, pg_restore_bin="pg_restore", expected_release=None, upgrade_to_head=False):
    started = time.perf_counter()
    m = verify(set_dir, anchor=anchor, encryption_key=encryption_key, signing_key=signing_key)
    q = m[QUALIFIED]
    require(encryption_key != ledger_key, "independent_ledger_key_required")
    X.require_head(ledger, ledger_head, ledger_key, minimum_seq=q["erasure_head"]["seq"])
    require(expected_release is not None and expected_release == q["release"], "recovery_release_mismatch")
    source_revision = m["database"]["schema_revision"]
    release_revision = expected_release.get("migration_head")
    require(source_revision in RECOVERY_REVISIONS and release_revision in RELEASE_REVISIONS, "recovery_schema_unsupported")
    require(RECOVERY_REVISIONS.index(source_revision) <= RECOVERY_REVISIONS.index(release_revision), "recovery_release_schema_incompatible")
    require(source_revision != RECOVERY_REVISIONS[2] or re.fullmatch(r"[0-9a-f]{64}", q.get("extended_schema_sha256", "")), "recovery_schema_evidence_missing")
    require(m["set_id"] in ledger.registered_sets(), "unregistered_backup_set")
    require(source_revision == release_revision or upgrade_to_head is True, "controlled_upgrade_required")
    identity(target_database_url)
    require(not E._pg_target_problems(target_database_url), "restore_target_refused")
    root = Path(target_root)
    require(not root.exists() and not E._is_inside(root, Path(set_dir)), "restore_target_exists")
    require(not E._is_inside(ledger.path, root), "erasure_history_must_be_independent")
    version = client_version(pg_restore_bin)
    if not execute:
        return Report("qualified_restore", False, details={"postgresql_client": version})
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    token = uuid.uuid4().hex
    (root / "RECOVERY_PENDING.json").write_text(json.dumps({"token": token, "manifest_sha256": anchor}))
    quarantine_database(target_database_url)
    try:
        result = E.restore_set(set_dir, target_root=root, target_database_url=target_database_url, execute=True, encryption_key=encryption_key,
                               signing_key=signing_key, require_signature=True, recovery_token=token, pg_restore_bin=pg_restore_bin)
        require(result.ok, "restore_verification_failed")
        engine = E._engine(target_database_url)
        try:
            with engine.connect() as c:
                require(schema_objects(c) == q["schema_objects_sha256"], "restored_schema_objects_mismatch")
                if "extended_schema_sha256" in q:
                    require(extended_schema_objects(c) == q["extended_schema_sha256"], "restored_extended_schema_mismatch")
                require(database_content_fingerprint(c, sorted(inspect(c).get_table_names())) == q["database_content_sha256"], "restored_database_content_mismatch")
        finally:
            engine.dispose()
        require(money_fingerprint(target_database_url) == q["money_sha256"], "restored_monetary_state_mismatch")
        with tempfile.TemporaryDirectory(prefix="a4m-probe-") as work:
            probe_file = Path(work) / "probe.json"
            E._materialise(Path(set_dir), m, "evidence/retrieval-probe.json", probe_file, encryption_key)
            probe = json.loads(probe_file.read_text())
            if probe.get("run"):
                require(probe.get("embedder") == "local_hash", "network_probe_refused")
                from src.backup_set.drill import _open_store
                store = _open_store(E.restore_layout(root)["knowledge_index"])
                for query in probe["queries"]:
                    hits = store.query(query["query"], top_k=probe["top_k"])
                    require([h.chunk_id for h in hits] == query["hit_ids"] and [round(float(h.score),6) for h in hits] == query["scores"], "retrieval_parity_failed")
        if m["database"]["schema_revision"] != expected_release["migration_head"]:
            import os
            import sys
            env = {**os.environ, "DATABASE_URL": target_database_url, "PYTHON_DOTENV_DISABLED": "1", "ASK4MO_PROVIDER_MODE": "offline", "AI_BUDGET_KILL": "true"}
            upgraded = subprocess.run([sys.executable, "-m", "alembic", "upgrade", expected_release["migration_head"]], env=env, cwd=Path(__file__).resolve().parents[2], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
            require(upgraded.returncode == 0 and E.schema_revision(target_database_url) == expected_release["migration_head"], "controlled_upgrade_failed")
        from src.llm.budget.ledger import DbBudgetLedger
        from src.persistence import make_session_factory
        engine = E._engine(target_database_url)
        try:
            DbBudgetLedger(make_session_factory(engine)).kill("recovery_reconciliation_required")
        finally:
            engine.dispose()
        X.require_head(ledger, ledger_head, ledger_key, minimum_seq=q["erasure_head"]["seq"])
        erased = X.reapply_postgresql(ledger, target_database_url, E.restore_layout(root)["documents"], execute=True)
        require(erased.ok, "erasure_reapply_failed")
        require(money_fingerprint(target_database_url) == q["money_sha256"], "erasure_changed_monetary_state")
        X.require_head(ledger, ledger_head, ledger_key, minimum_seq=q["erasure_head"]["seq"])
        receipt = {"format": FORMAT, "set_id": m["set_id"], "manifest_sha256": anchor, "erasure_head": ledger_head,
                   "database_identity_sha256": identity(target_database_url), "recovery_hold": True,
                   "accounting_reconciliation": "REQUIRED; historical figures are not current provider receipts", "erasure": erased.counts,
                   "duration_seconds": round(time.perf_counter()-started, 3), "postgres_client": version}
        (root / "RECOVERY_VERIFIED.json").write_text(json.dumps(receipt, sort_keys=True))
        result.details.update(receipt)
        return result
    except Exception:
        # PENDING remains, database-level hold survives partial file/schema failure.
        raise E.SetError("recovery_failed_target_quarantined") from None


def transfer(set_dir, destination, *, anchor, encryption_key, signing_key=None, execute=False):
    """Independent local destination simulator; no provider, upload or deletion."""
    verify(set_dir, anchor=anchor, encryption_key=encryption_key, signing_key=signing_key)
    dst = Path(destination)
    require(not dst.exists() and not E._is_inside(dst, Path(set_dir)) and not E._is_inside(Path(set_dir), dst), "transfer_target_refused")
    if execute:
        shutil.copytree(set_dir, dst)
        verify(dst, anchor=anchor, encryption_key=encryption_key, signing_key=signing_key)
    return Report("qualified_transfer", execute, details={"verified": bool(execute), "manifest_sha256": anchor, "provider": "disposable_local_destination"})


def rewrite(set_dir, *, out_dir, target_root, target_database_url, anchor, ledger, ledger_head, ledger_key,
            encryption_key, signing_key=None, expected_release=None, execute=False):
    """Erasure-safe NEW encrypted PostgreSQL set via a quarantined scratch restore.

    The original remains intact. No physical-media destruction is performed or claimed.
    """
    m = verify(set_dir, anchor=anchor, encryption_key=encryption_key, signing_key=signing_key)
    X.require_head(ledger, ledger_head, ledger_key, minimum_seq=m[QUALIFIED]["erasure_head"]["seq"])
    require(not Path(out_dir).exists(), "backup_target_exists")
    restored = restore(set_dir, target_root=target_root, target_database_url=target_database_url, anchor=anchor,
                       ledger=ledger, ledger_head=ledger_head, ledger_key=ledger_key, encryption_key=encryption_key,
                       signing_key=signing_key, expected_release=expected_release, execute=execute)
    if not execute:
        return Report("qualified_rewrite", False)
    require(restored.ok, "rewrite_restore_failed")
    from src.knowledge_admin.contracts import RuntimeIdentity
    with tempfile.TemporaryDirectory(prefix="a4m-rewrite-") as work:
        path = Path(work) / "knowledge-manifest.json"
        E._materialise(Path(set_dir), m, "knowledge/manifest.json", path, encryption_key)
        source_identity = RuntimeIdentity.from_dict(json.loads(path.read_text())["source_identity"])
    layout = E.restore_layout(Path(target_root))
    source = E.Source(database_url=target_database_url, documents_dir=layout["documents"], knowledge_files_dir=layout["knowledge_files"],
                      knowledge_index_dir=layout["knowledge_index"], identity=source_identity)
    erased = sorted(ledger.deletions())
    facts = {"rewritten_from_set_id": m["set_id"], "erased_user_ids": erased,
             "method": "account_deletion_service on a quarantined PostgreSQL restore", "ledger_seq": ledger_head["seq"], "original_destroyed": False}
    result = create(source, out_dir=out_dir, checkpoint_database_url=target_database_url, release=expected_release,
                    ledger=ledger, ledger_head=ledger_head, ledger_key=ledger_key, encryption_key=encryption_key,
                    signing_key=signing_key, execute=True, drained=True, drain_observed_at=datetime.now(timezone.utc), rewrites=facts)
    ledger.append("set_rewritten", old_set_id=m["set_id"], new_set_id=result.details["set_id"], erased_user_ids=erased)
    result.action = "qualified_rewrite"
    result.details.update(original_destroyed=False, erasure_claim="none_until_original_destroyed_and_attested", erasure_head=X.signed_head(ledger, ledger_key))
    return result
