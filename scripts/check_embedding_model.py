#!/usr/bin/env python3
"""No-network check that the configured embedding model id is an embeddings model in a RECORDED OpenRouter listing (02B, OD-EMBED).

    python scripts/check_embedding_model.py --listing listing.json [--model vendor/model] [--embeddings-listing]

``listing.json`` is a saved listing: the stdout of ``scripts/openrouter_models_probe.py`` (the free live probe, run by the owner), or a saved body of
``GET /api/v1/embeddings/models`` (pass ``--embeddings-listing``: every row is then an embeddings model) or of ``GET /api/v1/models?output_modalities=embeddings``.
This script reads one local file and prints a fixed-shape JSON verdict. It makes no request and reads no key. Exit 0 = ok, 1 = not ok, 2 = unreadable input.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listing", required=True, help="path to a recorded model listing (JSON)")
    ap.add_argument("--model", help="model id to check (default: COPILOT_EMBEDDING_MODEL)")
    ap.add_argument("--embeddings-listing", action="store_true", help="the listing came from the embeddings-only endpoint")
    a = ap.parse_args(argv)
    from src.copilot.embedding_catalogue import check_model_in_listing

    model = a.model
    if not model:
        from src.copilot.config import load_config

        model = load_config().embedding_model
    try:
        listing = json.loads(Path(a.listing).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(json.dumps({"ok": False, "code": "listing_unreadable", "model": model}))
        return 2
    verdict = check_model_in_listing(model, listing, embeddings_listing=a.embeddings_listing)
    print(json.dumps(verdict, indent=1, sort_keys=True))
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
