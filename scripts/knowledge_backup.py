#!/usr/bin/env python3
"""Governed knowledge backup, verification and restore (package 02A). DRY-RUN IS THE DEFAULT: nothing is written without ``--execute``.

    python scripts/knowledge_backup.py backup  --out DIR                       # plan only
    python scripts/knowledge_backup.py backup  --out DIR --execute             # writes DIR (must be new or empty)
    python scripts/knowledge_backup.py verify  --backup DIR                    # checksums only, reads the backup
    python scripts/knowledge_backup.py restore --backup DIR --target-root NEW  # plan only
    python scripts/knowledge_backup.py restore --backup DIR --target-root NEW --execute

The source is configured exactly like the API and the worker (``DATABASE_URL``, ``COPILOT_DATA_DIR``, ``KNOWLEDGE_STORAGE_DIR``); ``--data-root`` and
``--database-url`` override them for the backup source (the URL is never printed). A restore always goes into a SEPARATE environment under ``--target-root``
(``restored.db`` unless ``--target-database-url`` names an already-migrated database, ``knowledge_private/`` and ``chroma/``). Nothing is ever deleted or
overwritten: a non-empty target is refused unless ``--allow-non-empty`` (then only missing registry rows and files are added and the index is left alone).
``--rebuild-index`` re-adds the backed-up chunks through the LOCAL hashing embedder instead of copying the index files; it is refused unless the source
used the local embedder. No provider or network call is ever made. Exit status: 0 ok, 1 refused or failed, 2 usage.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backup", help="back up the registry, private files and the persistent governed index")
    b.add_argument("--out", required=True)
    b.add_argument("--data-root", help="override COPILOT_DATA_DIR for the source")
    b.add_argument("--database-url", help="override the source database URL (never printed)")
    b.add_argument("--execute", action="store_true")
    b.add_argument("--allow-active-jobs", action="store_true", help="back up even while knowledge jobs are queued or running (marks the backup inconsistent)")
    v = sub.add_parser("verify", help="verify a backup's checksums")
    v.add_argument("--backup", required=True)
    r = sub.add_parser("restore", help="restore into a separate environment")
    r.add_argument("--backup", required=True)
    r.add_argument("--target-root", required=True)
    r.add_argument("--target-database-url", help="an already-migrated database; default: a new SQLite file under the target root (never printed)")
    r.add_argument("--execute", action="store_true")
    r.add_argument("--allow-non-empty", action="store_true")
    r.add_argument("--rebuild-index", action="store_true")
    r.add_argument("--fallback-user-id", type=int, help="an EXISTING user id in the target recorded as the approver of versions whose original approver does not exist there")
    return p


def _backup(a) -> dict:
    if a.data_root:
        os.environ["COPILOT_DATA_DIR"] = str(Path(a.data_root).resolve())
    from src.config import load_config
    from src.copilot.config import load_config as load_copilot_config
    from src.copilot.embeddings import LocalHashEmbedder
    from src.copilot.vectorstore import ChromaStore
    from src.documents.storage import LocalDocumentStore
    from src.knowledge_admin import policy as P
    from src.knowledge_admin.config import resolve_knowledge_runtime_config
    from src.knowledge_admin.environment import build_identity
    from src.knowledge_admin.recovery import create_backup
    from src.persistence import make_engine, make_session_factory

    app_cfg, cop_cfg = load_config(), load_copilot_config()
    engine = make_engine(a.database_url or app_cfg.database_url)
    sf = make_session_factory(engine)
    runtime = resolve_knowledge_runtime_config(app_cfg if not a.database_url else type("U", (), {"database_url": a.database_url})(), cop_cfg, session_factory=sf)
    chroma = Path(runtime.chroma_dir)
    store = ChromaStore(LocalHashEmbedder(), persist_dir=str(chroma), collection_name=P.COLLECTION) if chroma.is_dir() else None   # never creates a missing index
    docs_dir = Path(runtime.private_files_dir)
    docs = LocalDocumentStore(str(docs_dir)) if docs_dir.is_dir() else _NoFiles()
    rep = create_backup(sf, docs, store, out_dir=a.out, chroma_dir=chroma if chroma.is_dir() else None, identity=build_identity(runtime, cop_cfg),
                        execute=a.execute, allow_active_jobs=a.allow_active_jobs)
    return rep.to_dict()


class _NoFiles:
    def exists(self, key: str) -> bool:
        return False

    def read(self, key: str) -> bytes:   # pragma: no cover - never reached (exists is always False)
        raise FileNotFoundError(key)


def _verify(a) -> dict:
    from src.knowledge_admin.recovery import verify_backup

    return verify_backup(a.backup).to_dict()


def _restore(a) -> dict:
    from src.copilot.embeddings import LocalHashEmbedder
    from src.copilot.vectorstore import ChromaStore
    from src.knowledge_admin import policy as P
    from src.knowledge_admin.recovery import load_manifest, restore_backup
    from src.persistence import init_db, make_engine, make_session_factory

    root = Path(a.target_root).resolve()
    load_manifest(a.backup)                                 # fails fast (fixed code) on a missing or unsupported backup
    files_dir, index_dir = root / "knowledge_private", root / "chroma"
    if a.execute:
        root.mkdir(parents=True, exist_ok=True)
    url = a.target_database_url or f"sqlite:///{root / 'restored.db'}"
    if not a.execute and not a.target_database_url and not root.exists():
        url = "sqlite://"                                   # dry-run against a target that does not exist yet: an empty in-memory registry, nothing is created
    engine = make_engine(url)
    if (a.execute or url == "sqlite://") and engine.dialect.name == "sqlite":
        init_db(engine)                                     # a brand-new SQLite target gets its schema; PostgreSQL targets must already be migrated
    sf = make_session_factory(engine)
    rep = restore_backup(a.backup, session_factory=sf, files_dir=files_dir, index_dir=index_dir, execute=a.execute, allow_non_empty=a.allow_non_empty,
                         rebuild_index=a.rebuild_index, fallback_user_id=a.fallback_user_id,
                         open_store=lambda: ChromaStore(LocalHashEmbedder(), persist_dir=str(index_dir), collection_name=P.COLLECTION))
    return rep.to_dict()


def main(argv: list[str] | None = None) -> int:
    a = _parser().parse_args(argv)
    try:
        out = {"backup": _backup, "verify": _verify, "restore": _restore}[a.cmd](a)
    except Exception as exc:  # noqa: BLE001 - a fixed code, never the exception text (it could contain a path or a URL)
        code = getattr(exc, "code", None) or type(exc).__name__
        print(json.dumps({"action": a.cmd, "ok": False, "codes": [str(code)]}))
        return 1
    print(json.dumps(out, indent=1, sort_keys=True))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
