#!/usr/bin/env python
"""Destatis GENESIS-Online acquisition client (Phase 7A.1, §8/§9).

Downloads official German structured data from the documented GENESIS-Online REST API
(https://www-genesis.destatis.de/genesisWS/rest/2020/) — HTTPS only, no HTML scraping, no
browser automation. Primary target is the occupation-level gross-earnings table
``62361-0034``; optional employment tables (e.g. ``12211-0009``) may be added.

Credentials are read ONLY from the environment (``DESTATIS_USERNAME`` + ``DESTATIS_PASSWORD``
or ``DESTATIS_TOKEN``) and are never logged, printed or written to provenance. GENESIS
requires a free registered account; without credentials this script reports NOT CONFIGURED
and exits 0 — German compensation via Destatis is high-value but Phase 7B is NOT blocked by
it (§10/§41): Eurostat SES already provides German earnings, and this client is ready to run
once an account is configured.

Output: ``data/raw/destatis/earnings/<table>/`` with the raw table file, a sha256 sidecar
and a credential-free provenance sidecar. It does NOT normalize into Ask4Mo records (7B).

Usage:
    DESTATIS_USERNAME=... DESTATIS_PASSWORD=... python scripts/knowledge/download_destatis.py
    python scripts/knowledge/download_destatis.py --table 62361-0034
    python scripts/knowledge/download_destatis.py --check   # reachability + config only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

GENESIS_BASE = "https://www-genesis.destatis.de/genesisWS/rest/2020"
DEFAULT_TABLE = "62361-0034"  # gross annual earnings by occupation (KldB), Germany
RAW_ROOT = "data/raw/destatis/earnings"
TIMEOUT = 30
_UA = "Ask4Mo-KnowledgeAcquisition/7A.1"


def _configured() -> bool:
    return bool(os.environ.get("DESTATIS_TOKEN") or
                (os.environ.get("DESTATIS_USERNAME") and os.environ.get("DESTATIS_PASSWORD")))


def _auth_params() -> dict:
    if os.environ.get("DESTATIS_TOKEN"):
        return {"username": os.environ["DESTATIS_TOKEN"], "password": ""}
    return {"username": os.environ.get("DESTATIS_USERNAME", ""),
            "password": os.environ.get("DESTATIS_PASSWORD", "")}


def _redact(text: str) -> str:
    out = text
    for k in ("DESTATIS_TOKEN", "DESTATIS_USERNAME", "DESTATIS_PASSWORD"):
        v = os.environ.get(k)
        if v:
            out = out.replace(v, "***")
    import re
    return re.sub(r"(username|password)=[^&\s]+", r"\1=***", out)


def check() -> dict:
    """Reachability + configuration probe (no table download, no secrets)."""
    rep = {"reachable": False, "configured": _configured(), "endpoint": GENESIS_BASE}
    try:
        req = urllib.request.Request(f"{GENESIS_BASE}/helloworld/whoami",
                                     headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            rep["reachable"] = resp.status == 200
    except Exception as exc:  # noqa: BLE001
        rep["error"] = type(exc).__name__
    return rep


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def download_table(table: str, *, fmt: str = "ffcsv") -> dict:
    """Download one GENESIS table to data/raw/destatis/earnings/<table>/ (atomic)."""
    if not _configured():
        return {"status": "NOT CONFIGURED", "table": table,
                "detail": "Set DESTATIS_USERNAME+DESTATIS_PASSWORD (or DESTATIS_TOKEN)."}
    params = {"name": table, "area": "all", "format": fmt,
              "compress": "false", "language": "en"}
    params.update(_auth_params())
    url = f"{GENESIS_BASE}/data/tablefile?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        return {"status": "HTTP_ERROR", "table": table, "code": exc.code}
    except Exception as exc:  # noqa: BLE001
        return {"status": "NETWORK_ERROR", "table": table, "detail": type(exc).__name__}

    if status != 200 or not body:
        return {"status": "EMPTY", "table": table, "code": status}

    out_dir = Path(RAW_ROOT) / table
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{table}.{ 'csv' if fmt.endswith('csv') else fmt}"
    # Atomic write.
    fd, tmp = tempfile.mkstemp(dir=str(out_dir))
    with os.fdopen(fd, "wb") as fh:
        fh.write(body)
    os.replace(tmp, out_file)

    digest = _sha256(out_file)
    (out_dir / f"{out_file.name}.sha256").write_text(digest + "\n", encoding="utf-8")
    provenance = {
        "source": "destatis", "source_quality": "official_statistics",
        "publisher": "Statistisches Bundesamt (Destatis)", "table": table,
        "endpoint": f"{GENESIS_BASE}/data/tablefile", "format": fmt, "country": "DE",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "raw_file": str(out_file), "sha256": digest, "bytes": len(body),
    }
    (out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return {"status": "OK", "table": table, "raw_file": str(out_file),
            "bytes": len(body), "sha256": digest}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Acquire Destatis GENESIS tables.")
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--check", action="store_true", help="Reachability/config only.")
    args = ap.parse_args(argv)

    if args.check:
        rep = check()
        print("DESTATIS GENESIS")
        print(f"  endpoint reachable: {rep['reachable']}")
        print(f"  credentials: {'CONFIGURED' if rep['configured'] else 'NOT CONFIGURED'}")
        return 0

    if not _configured():
        print("DESTATIS: NOT CONFIGURED")
        print("  GENESIS requires a free account. Set DESTATIS_USERNAME + DESTATIS_PASSWORD")
        print("  (or DESTATIS_TOKEN) in the environment, then re-run.")
        print("  German compensation is high-value but does NOT block Phase 7B (Eurostat")
        print("  SES already provides German earnings).")
        return 0  # non-blocking

    res = download_table(args.table)
    print(f"DESTATIS: {res['status']} table={res['table']}"
          + (f" bytes={res.get('bytes')} sha256={res.get('sha256', '')[:12]}"
             if res["status"] == "OK" else ""))
    return 0 if res["status"] in ("OK", "NOT CONFIGURED") else 1


if __name__ == "__main__":
    sys.exit(main())
