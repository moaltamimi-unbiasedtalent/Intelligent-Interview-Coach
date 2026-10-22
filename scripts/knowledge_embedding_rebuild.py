#!/usr/bin/env python3
"""Plan or run an operator-approved rebuild of the governed index with an approved embedder (package 02B). DRY-RUN IS THE DEFAULT.

    python scripts/knowledge_embedding_rebuild.py                         # inspect the active index, report compatibility, estimate calls and cost class
    python scripts/knowledge_embedding_rebuild.py --apply --target-dir NEW --confirm-embedder openai:text-embedding-3-small

The source registry, private files and active index are configured exactly like the API and the worker. The rebuild goes into a NEW, EMPTY directory
(never the active index), runs the existing reindex job handler once per active or indexed version, and verifies the new manifest. Nothing is
deleted or overwritten and switching to the new index is a manual step (COPILOT_CHROMA_DIR + restart of API and worker). A hosted environment refuses the
hash embedder; a paid embedder additionally needs the owner's approval environment (ASK4MO_ALLOW_PAID_EMBEDDINGS, ASK4MO_EMBEDDING_BUDGET_MARKER,
ASK4MO_EMBEDDING_MAX_CALLS), which this repository never sets. Output holds counts, field names and fixed codes only. Exit: 0 ok, 1 refused or failed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="build the new index (default: plan only)")
    ap.add_argument("--target-dir", help="a NEW or empty directory for the rebuilt index")
    ap.add_argument("--confirm-embedder", help="exact provider:model of a non-free embedder you approve")
    a = ap.parse_args(argv)

    from src.config import load_config
    from src.copilot.config import load_config as load_copilot_config
    from src.copilot.embeddings import EmbeddingConfigurationError, build_embedder
    from src.copilot.vectorstore import ChromaStore
    from src.documents.storage import LocalDocumentStore
    from src.knowledge_admin import policy as P
    from src.knowledge_admin.config import resolve_knowledge_runtime_config
    from src.knowledge_admin.embedding_rebuild import plan_rebuild, rebuild_into_new_index
    from src.persistence import make_engine, make_session_factory

    app_cfg, cop_cfg = load_config(), load_copilot_config()
    sf = make_session_factory(make_engine(app_cfg.database_url))
    runtime = resolve_knowledge_runtime_config(app_cfg, cop_cfg, session_factory=sf)
    chroma = Path(runtime.chroma_dir)
    try:
        embedder = build_embedder(cop_cfg)
    except EmbeddingConfigurationError as exc:
        print(json.dumps({"ok": False, "codes": exc.codes, "fields": list(exc.fields)}))
        return 1
    active = ChromaStore(embedder, persist_dir=str(chroma), collection_name=P.COLLECTION) if chroma.is_dir() else None   # never creates a missing index
    if not a.apply:
        out = plan_rebuild(sf, active, environment=runtime.environment)
        out["embedder"] = embedder.identity().to_dict()
        print(json.dumps(out, indent=1, sort_keys=True))
        return 0
    if not a.target_dir:
        print(json.dumps({"ok": False, "codes": ["target_dir_required"]}))
        return 1
    docs = LocalDocumentStore(runtime.private_files_dir)
    rep = rebuild_into_new_index(sf, docs, target_dir=a.target_dir, embedder=embedder, active_index_dir=chroma, environment=runtime.environment,
                                 confirm_embedder=a.confirm_embedder, execute=True)
    print(json.dumps(rep.to_dict(), indent=1, sort_keys=True))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
