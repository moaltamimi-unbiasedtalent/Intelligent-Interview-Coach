"""Backup erasure after account deletion (package 05B, PRIV-BACKUP).

THE PROBLEM. ``AccountDeletionService`` removes a deleted account's data from the LIVE application. Every backup set taken before the deletion still holds it.
A backup is a point-in-time copy and is never edited in place, so the data leaves the backups in exactly two ways: the set REACHES ITS MAXIMUM AGE and is
destroyed, or the set is REWRITTEN (restored into a scratch copy, the deletion re-applied, a NEW set taken) and the original is destroyed.

THE WINDOW (stated, an engineering default pending the owner's and legal counsel's confirmation, never a legal statement):
* ``BACKUP_RETENTION_DAYS`` (35): no backup set is kept longer than this. The operator destroys sets older than this.
* ``ERASURE_WINDOW_DAYS`` (35): a deleted account's data is gone from every backup set no later than this many days after the live deletion completed, PROVIDED
  the operator runs the retention destruction and records it. Because every set that can hold the data is at most RETENTION days old when the account is
  deleted, expiry alone reaches the end of the window; a rewrite can finish earlier. Until then the data IS still in those backups and the product says so.

WHAT THIS MODULE DOES AND DOES NOT DO
* An APPEND-ONLY, hash-chained LEDGER outside the database (a restore of an older database must not forget a deletion) records each completed deletion, each
  rewritten set and each operator attestation of a destroyed set. A modified or reordered ledger is detected.
* ``plan`` lists every set against the ledger: which sets may still hold a deleted account, how long until the window ends, which are overdue.
* ``rewrite_set`` restores a set into a scratch environment, re-applies the SAME deletion engine (``AccountDeletionService``; no second engine) for every ledger
  account, verifies the result and writes a NEW set. It never edits or deletes the original: the original must still be destroyed by the operator.
* ``attest_destruction`` records that the OPERATOR destroyed a set. This tool cannot verify that storage media were wiped, so the claim it can ever make is
  ``complete_per_operator_attestation``; it never says "erased from backups" for a set that was not rewritten or destroyed and attested.
* ``reapply_after_restore`` re-applies the ledger's deletions to a restored environment, because restoring an old backup resurrects deleted accounts.
Only SQLite sets are rewritten here. A PostgreSQL set is rewritten by the documented manual procedure (restore into a disposable PostgreSQL, run the deletion,
take a new set); that path is NOT exercised by this package.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from src.backup_set import crypto
from src.backup_set import engine as E
from src.knowledge_admin.recovery import Report

BACKUP_RETENTION_DAYS = 35
ERASURE_WINDOW_DAYS = 35
LEDGER_FORMAT = 1
GENESIS = "0" * 64
KINDS = ("deletion_recorded", "set_registered", "set_rewritten", "set_destruction_attested")
_SET_ID = re.compile(r"^[0-9a-f]{32}$")
_LABEL = re.compile(r"^[A-Za-z0-9 ._@-]{1,64}$")
CLAIM_BASIS = ("ledger and operator attestations; the destruction of storage media is not technically verified by this tool, and a set that was neither rewritten nor "
               "destroyed (and attested) still holds the data")


class ErasureError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _parse(ts: str) -> datetime:
    return _utc(datetime.fromisoformat(ts))


# ===================================================================== ledger
class Ledger:
    """An append-only JSON-lines file. Each entry carries ``prev_hash`` and ``entry_hash`` (SHA-256 over the previous hash and the canonical entry), so an edit,
    a deletion or a reordering of any line is detected by ``verify``. The file is never rewritten: entries are only appended."""

    def __init__(self, path: str | Path, *, clock: Callable[[], datetime] | None = None) -> None:
        self.path = Path(path)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _hash(prev: str, entry: dict) -> str:
        body = json.dumps({k: v for k, v in entry.items() if k != "entry_hash"}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256((prev + body).encode("utf-8")).hexdigest()

    def entries(self) -> list[dict]:
        if self.path.is_symlink():
            raise ErasureError("ledger_symlink_refused")
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def verify(self) -> list[str]:
        problems, prev = [], GENESIS
        try:
            entries = self.entries()
        except ErasureError as e:
            return [e.code]
        except Exception:  # noqa: BLE001
            return ["ledger_unreadable"]
        for i, e in enumerate(entries, start=1):
            if e.get("seq") != i or e.get("prev_hash") != prev or e.get("kind") not in KINDS or e.get("entry_hash") != self._hash(prev, e):
                problems.append("ledger_tampered")
                break
            prev = e["entry_hash"]
        return problems

    def append(self, kind: str, **fields) -> dict:
        if kind not in KINDS:
            raise ErasureError("unknown_ledger_kind")
        if self.verify():
            raise ErasureError("ledger_tampered")                   # never extend a ledger whose chain is broken
        entries = self.entries()
        prev = entries[-1]["entry_hash"] if entries else GENESIS
        entry = {"format": LEDGER_FORMAT, "seq": len(entries) + 1, "kind": kind, "recorded_at": _utc(self._clock()).isoformat(), **fields, "prev_hash": prev}
        entry["entry_hash"] = self._hash(prev, entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry

    def deletions(self) -> dict[int, datetime]:
        return {e["user_id"]: _parse(e["deleted_at"]) for e in self.entries() if e["kind"] == "deletion_recorded"}

    def attested_sets(self) -> dict[str, dict]:
        return {e["set_id"]: e for e in self.entries() if e["kind"] == "set_destruction_attested"}

    def rewritten_sets(self) -> dict[str, dict]:
        return {e["old_set_id"]: e for e in self.entries() if e["kind"] == "set_rewritten"}

    def registered_sets(self) -> dict[str, datetime]:
        return {e["set_id"]: _parse(e["created_at"]) for e in self.entries() if e["kind"] == "set_registered"}


def register_set(ledger: Ledger, set_dir: str | Path) -> dict:
    """Record that a set exists (id and creation time only). The ledger needs the INVENTORY of sets: without it a set that was deleted without an attestation would
    look like a set that never existed, and the erasure claim could be wrongly complete. Idempotent."""
    m = E.load_manifest(set_dir)
    for e in ledger.entries():
        if e["kind"] == "set_registered" and e["set_id"] == m["set_id"]:
            return e
    return ledger.append("set_registered", set_id=m["set_id"], created_at=m["created_at"])


def record_deletion(ledger: Ledger, user_id: int, deleted_at: datetime) -> dict:
    """Record that the LIVE deletion of ``user_id`` completed at ``deleted_at``. Idempotent per user. Only the numeric id is stored (no email, no name): once the
    account is deleted the integer refers to nothing."""
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        raise ErasureError("invalid_user_id")
    for e in ledger.entries():
        if e["kind"] == "deletion_recorded" and e["user_id"] == user_id:
            return e
    return ledger.append("deletion_recorded", user_id=user_id, deleted_at=_utc(deleted_at).isoformat(),
                         window_days=ERASURE_WINDOW_DAYS, retention_days=BACKUP_RETENTION_DAYS)


# ===================================================================== scanning sets
def scan_sets(sets_dir: str | Path) -> tuple[list[tuple[Path, dict]], int]:
    found, unreadable = [], 0
    base = Path(sets_dir)
    if not base.is_dir():
        return [], 0
    for d in sorted(p for p in base.iterdir() if p.is_dir() and not p.is_symlink()):
        try:
            found.append((d, E.load_manifest(d)))
        except E.SetError:
            if (d / E.MANIFEST).exists():
                unreadable += 1
    return found, unreadable


def _users_in_set(set_dir: Path, manifest: dict, encryption_key: bytes | None) -> set[int] | None:
    """The account ids present in a SQLite set's snapshot, or None when it cannot be inspected (PostgreSQL dump, sealed set without the key)."""
    if manifest["database"]["dialect"] != "sqlite":
        return None
    entry = manifest["files"][manifest["database"]["file"]]
    with tempfile.TemporaryDirectory(prefix="a4me-") as work:
        snap = Path(work) / "s.sqlite"
        try:
            if entry.get("sealed"):
                if encryption_key is None:
                    return None
                crypto.unseal_to(set_dir / entry["stored"], snap, encryption_key, set_id=manifest["set_id"], logical=manifest["database"]["file"])
            else:
                import shutil

                shutil.copyfile(set_dir / entry["stored"], snap)
            con = sqlite3.connect(f"file:{snap}?mode=ro", uri=True)
            try:
                return {int(r[0]) for r in con.execute("SELECT id FROM users")}
            finally:
                con.close()
        except Exception:  # noqa: BLE001
            return None


# ===================================================================== plan
def plan(ledger: Ledger, sets_dir: str | Path, *, now: datetime | None = None, encryption_key: bytes | None = None,
         window_days: int = ERASURE_WINDOW_DAYS, retention_days: int = BACKUP_RETENTION_DAYS) -> dict:
    """Read-only. The INVENTORY is every set registered in the ledger plus every set present under ``sets_dir``. For every set and every recorded deletion that
    happened after the set was created: a PRESENT set is closed only when it provably holds no such account (rewritten without it, or the account is not in the
    snapshot); an ABSENT set is closed only by an operator attestation of its destruction; a present set with an attestation is a contradiction and stays open.
    The claim is ``complete_per_operator_attestation`` only when nothing is open and no unregistered set is present."""
    now = _utc(now or datetime.now(timezone.utc))
    chain = ledger.verify()
    deletions = ledger.deletions() if not chain else {}
    attested, rewritten, registered = (ledger.attested_sets(), ledger.rewritten_sets(), ledger.registered_sets()) if not chain else ({}, {}, {})
    present_list, unreadable = scan_sets(sets_dir)
    present = {m["set_id"]: (d, m) for d, m in present_list}
    unregistered = sorted(sid for sid in present if sid not in registered)
    inventory = sorted(set(registered) | set(present))
    rows, open_count, overdue, older_than_a_deletion = [], 0, 0, 0
    for sid in inventory:
        d, m = present.get(sid, (None, None))
        created = _parse(m["created_at"]) if m else registered[sid]
        users = _users_in_set(d, m, encryption_key) if m else None
        erased = {int(u) for u in (((m or {}).get("rewrites") or {}).get("erased_user_ids") or [])}
        is_attested = sid in attested
        row = {"set_id": sid, "created_at": created.isoformat(), "age_days": round((now - created).total_seconds() / 86400, 2), "present": m is not None,
               "registered": sid in registered, "past_retention": (now - created) > timedelta(days=retention_days), "destruction_attested": is_attested,
               "rewritten_into": (rewritten.get(sid) or {}).get("new_set_id"), "deletions": []}
        open_here = False
        for uid, deleted_at in sorted(deletions.items()):
            if created >= deleted_at:
                continue                                              # taken after the live deletion completed: it cannot hold the account
            older_than_a_deletion += 1
            if m is None:
                state = "destroyed_per_operator_attestation" if is_attested else "absent_without_attestation"
                is_open = not is_attested
            elif is_attested:
                state, is_open = "attested_destroyed_but_still_present", True
            elif uid in erased:
                state, is_open = "rewritten_without_account", False
            elif users is not None and uid not in users:
                state, is_open = "account_not_in_set", False
            else:
                state, is_open = ("contains_account" if users is not None else "may_contain_account"), True
            deadline = deleted_at + timedelta(days=window_days)
            late = bool(is_open and now > deadline)
            overdue += int(late)
            open_here = open_here or is_open
            row["deletions"].append({"user_ref": f"uid:{uid}", "state": state, "open": is_open, "window_ends": deadline.isoformat(), "overdue": late})
        row["status"] = "open" if open_here else "closed"
        open_count += int(open_here)
        rows.append(row)
    if chain:
        claim = "ledger_invalid"
    elif not deletions:
        claim = "no_deletions_recorded"
    elif open_count or unregistered:
        claim = "incomplete"
    elif not older_than_a_deletion:
        claim = "not_applicable_no_older_sets"
    else:
        claim = "complete_per_operator_attestation"
    return {"policy": {"retention_days": retention_days, "erasure_window_days": window_days,
                       "meaning": "the data of an account whose live deletion completed is removed from every older backup set within window_days of that deletion, by rewrite or "
                                  "by destruction at retention age; until then it IS still in those sets"},
            "ledger_problems": chain, "deletions_recorded": len(deletions), "sets_in_inventory": len(rows), "sets_unreadable": unreadable,
            "unregistered_sets_present": len(unregistered), "sets_open": open_count, "overdue_entries": overdue, "erasure_claim": claim, "claim_basis": CLAIM_BASIS, "sets": rows}


# ===================================================================== the deletion engine on a scratch environment
class _SqliteCheckpointPurger:
    """Purges a run's checkpoint thread from the snapshot (official ``SqliteSaver.delete_thread``) when the snapshot has the saver's tables; otherwise there is
    nothing in this database to purge (the checkpoint store may live in its own file, which is not part of the set)."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path

    def purge_run(self, run_id: str) -> bool:
        con = sqlite3.connect(self._path)
        try:
            if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='checkpoints'").fetchone() is None:
                return True
            from langgraph.checkpoint.sqlite import SqliteSaver

            SqliteSaver(con).delete_thread(run_id)
            con.commit()
            return True
        finally:
            con.close()


def scrub_environment(layout: dict[str, Path], user_ids: list[int]) -> dict:
    """Re-apply the account deletion to a restored SQLite environment (``E.restore_layout`` paths) with the ONE deletion engine. Returns counts and fixed codes;
    never an id list longer than the ledger's, a name or a path."""
    from src.application.account_deletion_service import AccountDeletionService, SubscriptionResolutionRequired
    from src.documents.storage import LocalDocumentStore
    from src.persistence import make_engine, make_session_factory
    from src.privacy.preparation import PreparationRunIndex

    out = {"accounts_requested": len(user_ids), "accounts_present": 0, "accounts_erased": 0, "billing_reference_retained": 0, "files_purged": 0, "files_failed": 0,
           "checkpoints_purged": 0, "checkpoints_failed": 0, "codes": []}
    db = layout["database"]
    eng = make_engine(f"sqlite:///{db}")
    try:
        sf = make_session_factory(eng)
        docs = LocalDocumentStore(str(layout["documents"]))
        svc = AccountDeletionService(sf, document_store=docs, agent_service=_SqliteCheckpointPurger(db), preparation_index=PreparationRunIndex(sf))
        for uid in user_ids:
            try:
                summary = svc.delete_account(uid)
            except SubscriptionResolutionRequired:
                summary = svc.delete_account(uid, preserve_billing_reference=True)      # the live erasure keeps ONLY the minimum billing reference too
                out["billing_reference_retained"] += 1
            if summary.existed:
                out["accounts_present"] += 1
                out["accounts_erased"] += 1
            out["files_purged"] += summary.files_purged
            out["files_failed"] += summary.files_failed
            out["checkpoints_purged"] += summary.checkpoints_purged
            out["checkpoints_failed"] += summary.checkpoints_failed
        if out["files_failed"]:
            out["codes"].append("file_purge_failed")
        if out["checkpoints_failed"]:
            out["codes"].append("checkpoint_purge_failed")
    finally:
        eng.dispose()
    return out


def user_storage_keys(layout: dict[str, Path], user_ids: list[int]) -> set[str]:
    """The private-file keys the given accounts own, read BEFORE a scrub (afterwards the rows that name them are gone)."""
    con = sqlite3.connect(f"file:{layout['database']}?mode=ro", uri=True)
    try:
        keys: set[str] = set()
        for uid in user_ids:
            keys |= {r[0] for r in con.execute("SELECT v.storage_key FROM document_versions v JOIN candidate_documents d ON d.id = v.document_id WHERE d.user_id = ?", (uid,)) if r[0]}
        return keys
    finally:
        con.close()


def verify_scrubbed(layout: dict[str, Path], user_ids: list[int], keys: set[str]) -> list[str]:
    """After a scrub: no candidate document row, no interview row, no account row (an anonymised retained billing shell is allowed) and none of the accounts' private
    files remain."""
    problems = []
    con = sqlite3.connect(f"file:{layout['database']}?mode=ro", uri=True)
    try:
        for uid in user_ids:
            if con.execute("SELECT COUNT(*) FROM candidate_documents WHERE user_id = ?", (uid,)).fetchone()[0]:
                problems.append("candidate_documents_remain")
            if con.execute("SELECT COUNT(*) FROM interviews WHERE user_id = ?", (uid,)).fetchone()[0]:
                problems.append("interviews_remain")
            if con.execute("SELECT COUNT(*) FROM users WHERE id = ? AND status != 'deletion_requested'", (uid,)).fetchone()[0]:
                problems.append("account_row_remains")
    finally:
        con.close()
    if any((layout["documents"] / k).exists() for k in keys):
        problems.append("private_files_remain")
    return sorted(set(problems))


def reapply_after_restore(ledger: Ledger, target_root: str | Path, *, execute: bool = False) -> Report:
    """After ANY restore of an older set, re-apply every ledger deletion to the restored SQLite environment (restoring resurrects deleted accounts). Dry-run
    by default: reports which ledger accounts exist in the restored database."""
    rep = Report("reapply_deletions", execute)
    chain = ledger.verify()
    if chain:
        rep.ok, rep.codes = False, chain
        return rep
    lay = E.restore_layout(Path(target_root))
    if not lay["database"].is_file():
        rep.ok, rep.codes = False, ["restored_database_missing"]
        return rep
    ids = sorted(ledger.deletions())
    con = sqlite3.connect(f"file:{lay['database']}?mode=ro", uri=True)
    try:
        present = [i for i in ids if con.execute("SELECT 1 FROM users WHERE id = ? AND status != 'deletion_requested'", (i,)).fetchone()]
    finally:
        con.close()
    rep.counts = {"ledger_accounts": len(ids), "present_in_restored_environment": len(present)}
    if not execute or not present:
        return rep
    keys = user_storage_keys(lay, present)
    result = scrub_environment(lay, present)
    problems = verify_scrubbed(lay, present, keys)
    rep.details = result
    if problems or result["codes"]:
        rep.ok, rep.codes = False, sorted(set(problems + result["codes"]))
    return rep


# ===================================================================== rewrite a set
def rewrite_set(set_dir: str | Path, out_dir: str | Path, ledger: Ledger, *, execute: bool = False, encryption_key: bytes | None = None,
                new_encryption_key: bytes | None = None, signing_key: bytes | None = None, storage_encrypted_attested: bool = False, api_env: str | None = None,
                allow_active_jobs: bool = False, clock: Callable[[], datetime] | None = None) -> Report:
    """Write a NEW set equal to ``set_dir`` without the accounts the ledger records as deleted AFTER the set was taken: the deletion is re-applied, with the
    one deletion engine, to a scratch restore of the set. The original set is only read; it must still be destroyed by the operator (``attest_destruction``).
    Dry-run by default."""
    base, out = Path(set_dir), Path(out_dir)
    rep = Report("rewrite_set", execute)
    chain = ledger.verify()
    if chain:
        rep.ok, rep.codes = False, chain
        return rep
    v = E.verify_set(base, encryption_key=encryption_key, signing_key=signing_key)
    if not v.ok:
        rep.ok, rep.codes = False, ["backup_integrity_failed"] + v.codes
        return rep
    m = E.load_manifest(base)
    if m["database"]["dialect"] != "sqlite":
        rep.ok, rep.codes = False, ["rewrite_requires_manual_postgresql_procedure"]       # NOT exercised by this package (documented in the runbook)
        return rep
    created = _parse(m["created_at"])
    todo = sorted(uid for uid, when in ledger.deletions().items() if created < when)
    present = _users_in_set(base, m, encryption_key)
    if present is not None:
        todo = [u for u in todo if u in present]
    rep.counts = {"accounts_to_erase": len(todo)}
    if not todo:
        rep.codes.append("nothing_to_rewrite")
        return rep
    if not execute:
        return rep
    if out.exists() and any(out.iterdir()):
        rep.ok, rep.codes = False, ["backup_target_not_empty"]
        return rep
    with tempfile.TemporaryDirectory(prefix="a4mw-") as work_s:
        work = Path(work_s)
        env_root = work / "env"
        r = E.restore_set(base, target_root=env_root, execute=True, encryption_key=encryption_key, signing_key=signing_key)
        if not r.ok:
            rep.ok, rep.codes = False, ["scratch_restore_failed"] + r.codes
            return rep
        lay = E.restore_layout(env_root)
        keys = user_storage_keys(lay, todo)
        result = scrub_environment(lay, todo)
        problems = verify_scrubbed(lay, todo, keys)
        rep.details = {"scrub": result}
        if problems or result["codes"]:
            rep.ok, rep.codes = False, ["scrub_verification_failed"] + sorted(set(problems + result["codes"]))
            return rep
        identity = None
        kman = m["files"].get("knowledge/manifest.json")
        if kman:
            try:
                from src.knowledge_admin.contracts import RuntimeIdentity

                tmp = work / "kman.json"
                E._materialise(base, m, "knowledge/manifest.json", tmp, encryption_key)
                src_identity = json.loads(tmp.read_text(encoding="utf-8")).get("source_identity")
                identity = RuntimeIdentity.from_dict(src_identity) if src_identity else None
            except Exception:  # noqa: BLE001 - the identity is informational; a rewritten set without it still restores (file-level index copy)
                identity = None
        source = E.Source(database_url=f"sqlite:///{lay['database']}", documents_dir=lay["documents"], knowledge_files_dir=lay["knowledge_files"],
                          knowledge_index_dir=lay["knowledge_index"], identity=identity)
        rewrites = {"rewrites": {"rewritten_from_set_id": m["set_id"], "erased_user_ids": todo, "method": "account_deletion_service on a scratch restore",
                                 "ledger_seq": len(ledger.entries()), "original_destroyed": False}}
        new = E.create_set(source, out_dir=out, execute=True, encryption_key=new_encryption_key, signing_key=signing_key, storage_encrypted_attested=storage_encrypted_attested,
                           api_env=api_env, allow_active_jobs=allow_active_jobs, extra_manifest=rewrites, clock=clock)
        rep.codes += [c for c in new.codes if c not in rep.codes]
        if not new.ok:
            rep.ok = False
            rep.codes.insert(0, "new_set_failed")
            return rep
        nv = E.verify_set(out, encryption_key=new_encryption_key, signing_key=signing_key)
        if not nv.ok:
            rep.ok, rep.codes = False, ["new_set_verification_failed"] + nv.codes
            return rep
        new_id = new.details["set_id"]
    register_set(ledger, out)
    ledger.append("set_rewritten", old_set_id=m["set_id"], new_set_id=new_id, erased_user_ids=todo)
    rep.details |= {"old_set_id": m["set_id"], "new_set_id": new_id, "original_set_must_be_destroyed": True, "erasure_claim": "none_until_original_destroyed_and_attested"}
    return rep


# ===================================================================== attest destruction
def attest_destruction(ledger: Ledger, set_id: str, *, attested_by: str, reason: str, sets_dir: str | Path | None = None, now: datetime | None = None) -> dict:
    """Record that the OPERATOR destroyed a set (reason ``rewritten`` or ``expired``). Refused while a set with that id is still present under ``sets_dir``. The tool
    cannot verify the destruction of the media: the ledger records the operator's statement and says so."""
    if not _SET_ID.match(set_id or ""):
        raise ErasureError("invalid_set_id")
    if not _LABEL.match(attested_by or ""):
        raise ErasureError("invalid_attestor_label")
    if reason not in ("rewritten", "expired"):
        raise ErasureError("invalid_reason")
    if sets_dir is not None:
        for _, m in scan_sets(sets_dir)[0]:
            if m["set_id"] == set_id:
                raise ErasureError("set_still_present")
    if reason == "rewritten" and set_id not in ledger.rewritten_sets():
        raise ErasureError("set_not_rewritten")
    if reason == "expired":
        created = ledger.registered_sets().get(set_id)
        if created is None:
            raise ErasureError("set_not_registered")
        if (_utc(now or datetime.now(timezone.utc)) - created) <= timedelta(days=BACKUP_RETENTION_DAYS):
            raise ErasureError("set_not_expired")
    for e in ledger.entries():
        if e["kind"] == "set_destruction_attested" and e["set_id"] == set_id:
            return e
    return ledger.append("set_destruction_attested", set_id=set_id, attested_by=attested_by, reason=reason, verified_by_tool=False)
