"""Builds a backup ``Source`` from the operator's environment, configured exactly like the API and the worker (package 05B).

``DATABASE_URL``, ``COPILOT_DATA_DIR`` and ``KNOWLEDGE_STORAGE_DIR`` go through the ONE knowledge runtime configuration (02A); ``DOCUMENT_STORAGE_DIR`` is the private
candidate document directory and is REQUIRED (a backup that silently skips the documents is not a backup). Nothing here prints a URL, a path or a credential.
"""

from __future__ import annotations

import os
from pathlib import Path

from src.backup_set.engine import Source, SetError


def source_from_environment(*, database_url: str | None = None, documents_dir: str | None = None, data_root: str | None = None) -> Source:
    docs = documents_dir or os.environ.get("DOCUMENT_STORAGE_DIR", "").strip()
    if not docs:
        raise SetError("document_storage_dir_missing")
    if data_root:
        os.environ["COPILOT_DATA_DIR"] = str(Path(data_root).resolve())
    from src.config import load_config
    from src.copilot.config import load_config as load_copilot_config
    from src.knowledge_admin.config import resolve_knowledge_runtime_config
    from src.knowledge_admin.environment import build_identity
    from src.persistence import make_engine, make_session_factory

    app_cfg, cop_cfg = load_config(), load_copilot_config()
    url = database_url or app_cfg.database_url
    engine = make_engine(url)
    try:
        sf = make_session_factory(engine)
        runtime = resolve_knowledge_runtime_config(app_cfg if not database_url else type("U", (), {"database_url": database_url})(), cop_cfg, session_factory=sf)
        identity = build_identity(runtime, cop_cfg)
    finally:
        engine.dispose()
    return Source(database_url=url, documents_dir=Path(docs), knowledge_files_dir=Path(runtime.private_files_dir), knowledge_index_dir=Path(runtime.chroma_dir), identity=identity)
