#!/usr/bin/env python3
"""Backup set, restore and backup-erasure operator tool (package 05B). DRY-RUN IS THE DEFAULT: nothing is written without ``--execute``.

    python scripts/backup_set.py keygen                                         # prints a NEW base64 key once; store it in your secret manager, never in the repo
    python scripts/backup_set.py backup  --out DIR [--execute] [--encrypt] [--attest-encrypted-storage] [--ledger FILE]
    python scripts/backup_set.py verify  --set DIR [--require-signature] [--require-encryption]
    python scripts/backup_set.py restore --set DIR --target-root NEW [--target-database-url URL] [--execute] [--require-signature]
    python scripts/backup_set.py erase record-deletion --ledger FILE --user-id N [--deleted-at ISO]
    python scripts/backup_set.py erase register        --ledger FILE --set DIR
    python scripts/backup_set.py erase plan            --ledger FILE --sets-dir DIR
    python scripts/backup_set.py erase rewrite         --ledger FILE --set DIR --out NEW [--execute] [--encrypt]
    python scripts/backup_set.py erase attest-destroyed --ledger FILE --set-id ID --by LABEL --reason rewritten|expired [--sets-dir DIR]
    python scripts/backup_set.py erase reapply         --ledger FILE --target-root DIR [--execute]

Source (backup): the API's own variables, DATABASE_URL, DOCUMENT_STORAGE_DIR (required), COPILOT_DATA_DIR, KNOWLEDGE_STORAGE_DIR. Keys come ONLY from the environment:
BACKUP_ENCRYPTION_KEY (sealing; 32 bytes, base64) and BACKUP_SIGNING_KEY (optional manifest signature; derived from the sealing key when sealing). No key is ever accepted on
the command line (a process list would show it) and none is ever printed, logged or stored. Hosted environments (API_ENV other than development/test) REQUIRE a sealed set or
an explicit --attest-encrypted-storage. Nothing is ever deleted or overwritten. Output is JSON of codes and counts: no path, URL or credential. Exit: 0 ok, 1 refused, 2 usage.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("keygen", help="print a new random base64 key (store it in a secret manager; it is not saved anywhere)")
    b = sub.add_parser("backup")
    b.add_argument("--out", required=True)
    b.add_argument("--database-url", help="override the source database URL (never printed)")
    b.add_argument("--documents-dir")
    b.add_argument("--data-root")
    b.add_argument("--execute", action="store_true")
    b.add_argument("--encrypt", action="store_true", help="seal every file with AES-256-GCM using BACKUP_ENCRYPTION_KEY")
    b.add_argument("--attest-encrypted-storage", action="store_true", help="the destination is encrypted storage (recorded as an attestation, NOT verified)")
    b.add_argument("--allow-active-jobs", action="store_true", help="back up with jobs queued or running (marks the set inconsistent)")
    b.add_argument("--ledger", help="register the new set in this erasure ledger")
    v = sub.add_parser("verify")
    v.add_argument("--set", required=True)
    v.add_argument("--require-signature", action="store_true")
    v.add_argument("--require-encryption", action="store_true")
    r = sub.add_parser("restore")
    r.add_argument("--set", required=True)
    r.add_argument("--target-root", required=True)
    r.add_argument("--target-database-url", help="PostgreSQL sets only: an EMPTY database named *restore*, *staging* or *drill* (never printed)")
    r.add_argument("--execute", action="store_true")
    r.add_argument("--require-signature", action="store_true")
    e = sub.add_parser("erase")
    es = e.add_subparsers(dest="erase_cmd", required=True)
    for name in ("record-deletion", "register", "plan", "rewrite", "attest-destroyed", "reapply"):
        s = es.add_parser(name)
        s.add_argument("--ledger", required=True)
        if name == "record-deletion":
            s.add_argument("--user-id", type=int, required=True)
            s.add_argument("--deleted-at", help="ISO timestamp when the live deletion completed (default: now, UTC)")
        if name in ("register", "rewrite"):
            s.add_argument("--set", required=True)
        if name == "plan":
            s.add_argument("--sets-dir", required=True)
        if name == "rewrite":
            s.add_argument("--out", required=True)
            s.add_argument("--execute", action="store_true")
            s.add_argument("--encrypt", action="store_true")
            s.add_argument("--attest-encrypted-storage", action="store_true")
        if name == "attest-destroyed":
            s.add_argument("--set-id", required=True)
            s.add_argument("--by", required=True, help="a short label for who destroyed the set (no personal data needed)")
            s.add_argument("--reason", required=True, choices=("rewritten", "expired"))
            s.add_argument("--sets-dir")
        if name == "reapply":
            s.add_argument("--target-root", required=True)
            s.add_argument("--execute", action="store_true")
    q = sub.add_parser("qualified", help="PG16 sealed recovery; independent trusted ledger head and quarantined NEW targets")
    qs = q.add_subparsers(dest="qualified_cmd", required=True)
    for name in ("backup", "verify", "restore", "transfer", "rewrite"):
        child = qs.add_parser(name)
        child.add_argument("--execute", action="store_true")
        if name != "backup":
            child.add_argument("--set", required=True)
            child.add_argument("--manifest-sha256", required=True)
        if name in ("backup", "rewrite"):
            child.add_argument("--out", required=True)
        if name == "backup":
            child.add_argument("--attest-drained-at", required=True, help="UTC producer-drain observation, at most five minutes old")
        if name in ("restore", "rewrite"):
            child.add_argument("--target-root", required=True)
        if name == "restore":
            child.add_argument("--upgrade-to-head", action="store_true", help="explicit controlled 0047 -> 0048 rehearsal on the NEW target")
        if name == "transfer":
            child.add_argument("--destination", required=True)
    return p


def _keys(encrypt: bool, need_key_if_present: bool = True):
    from src.backup_set import crypto

    enc = crypto.key_from_env(crypto.ENCRYPTION_KEY_ENV) if encrypt else (crypto.key_from_env(crypto.ENCRYPTION_KEY_ENV) if (need_key_if_present and os.environ.get(crypto.ENCRYPTION_KEY_ENV)) else None)
    sig = crypto.key_from_env(crypto.SIGNING_KEY_ENV) if os.environ.get(crypto.SIGNING_KEY_ENV) else None
    return enc, sig


def _run(a) -> dict:
    from src.backup_set import crypto, engine as E

    if a.cmd == "qualified":
        from src.backup_set.operator import run
        return run(a)
    if a.cmd == "keygen":
        return {"action": "keygen", "ok": True, "key": crypto.generate_key(), "note": "store this in a secret manager; it is shown once and never saved by this tool"}
    if a.cmd == "backup":
        from src.backup_set.runtime import source_from_environment

        enc, sig = _keys(a.encrypt, need_key_if_present=False)
        src = source_from_environment(database_url=a.database_url, documents_dir=a.documents_dir, data_root=a.data_root)
        rep = E.create_set(src, out_dir=a.out, execute=a.execute, encryption_key=enc, signing_key=sig, storage_encrypted_attested=a.attest_encrypted_storage,
                           api_env=os.environ.get("API_ENV"), allow_active_jobs=a.allow_active_jobs)
        if a.ledger and rep.ok and a.execute:
            from src.backup_set.erasure import Ledger, register_set

            register_set(Ledger(a.ledger), a.out)
        return rep.to_dict()
    if a.cmd == "verify":
        enc, sig = _keys(False)
        return E.verify_set(a.set, encryption_key=enc, signing_key=sig, require_signature=a.require_signature, require_encryption=a.require_encryption).to_dict()
    if a.cmd == "restore":
        enc, sig = _keys(False)
        return E.restore_set(a.set, target_root=a.target_root, execute=a.execute, encryption_key=enc, signing_key=sig, require_signature=a.require_signature,
                             target_database_url=a.target_database_url).to_dict()
    # erase
    from src.backup_set import erasure as X

    ledger = X.Ledger(a.ledger)
    if a.erase_cmd == "record-deletion":
        when = datetime.fromisoformat(a.deleted_at) if a.deleted_at else datetime.now(timezone.utc)
        e = X.record_deletion(ledger, a.user_id, when)
        return {"action": "erase_record_deletion", "ok": True, "seq": e["seq"], "window_days": X.ERASURE_WINDOW_DAYS}
    if a.erase_cmd == "register":
        e = X.register_set(ledger, a.set)
        return {"action": "erase_register", "ok": True, "seq": e["seq"], "set_id": e["set_id"]}
    if a.erase_cmd == "plan":
        enc, _ = _keys(False)
        out = X.plan(ledger, a.sets_dir, encryption_key=enc)
        return {"action": "erase_plan", "ok": out["erasure_claim"] in ("complete_per_operator_attestation", "not_applicable_no_older_sets", "no_deletions_recorded"), **out}
    if a.erase_cmd == "rewrite":
        enc, sig = _keys(False)
        new_enc = crypto.key_from_env(crypto.ENCRYPTION_KEY_ENV) if a.encrypt else enc
        return X.rewrite_set(a.set, a.out, ledger, execute=a.execute, encryption_key=enc, new_encryption_key=new_enc, signing_key=sig,
                             storage_encrypted_attested=a.attest_encrypted_storage, api_env=os.environ.get("API_ENV")).to_dict()
    if a.erase_cmd == "attest-destroyed":
        e = X.attest_destruction(ledger, a.set_id, attested_by=a.by, reason=a.reason, sets_dir=a.sets_dir)
        return {"action": "erase_attest_destroyed", "ok": True, "seq": e["seq"], "verified_by_tool": False, "note": "operator attestation recorded; media destruction is not verified by this tool"}
    return X.reapply_after_restore(ledger, a.target_root, execute=a.execute).to_dict()


def main(argv: list[str] | None = None) -> int:
    a = _parser().parse_args(argv)
    try:
        out = _run(a)
    except Exception as exc:  # noqa: BLE001 - a fixed code, never the exception text (it could contain a path, a URL or key material)
        code = getattr(exc, "code", None) or type(exc).__name__
        print(json.dumps({"action": a.cmd, "ok": False, "codes": [str(code)]}))
        return 1
    print(json.dumps(out, indent=1, sort_keys=True))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
