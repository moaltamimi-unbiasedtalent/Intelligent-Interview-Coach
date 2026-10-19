"""P10E persistent cumulative ledger: ONE authoritative accounting state OUTSIDE the Git checkout.

The owner approved USD 10 and 300 provider calls as CUMULATIVE totals for all P10E live execution. This module makes that survive new runs, process restarts, branch switches and
new checkouts on the designated host:

* A single SQLite database (``synchronous=FULL``, so a committed reservation is on disk before the network request begins) in a directory the caller names EXPLICITLY (no default)
  that must be outside the repository, owned by the running user and not accessible to group or others.
* Append-only by construction: triggers refuse DELETE and refuse changing a settled row or any immutable column; each reservation is hash-chained to the previous one and the head is
  recorded, so deletion, reordering or truncation is detected when the ledger is opened.
* Identity: the ledger carries a genesis id, the designated environment id and a host fingerprint. The owner-reviewed authorization record names the expected genesis id once the
  ledger exists, so a new empty ledger in another checkout or location can neither be initialized (initialization is refused once a genesis id is recorded) nor accepted (the
  genesis id would not match). A missing ledger after use is a STOP, never an automatic re-initialization.
* Exclusive session: an operating-system ``flock`` held for the whole execution session (released by the OS if the process dies, so there is no stale lock to break). A second
  session, checkout or process is refused. A previous session that did not close cleanly is reconciled under the lock: every reservation it left open is kept at its FULL worst
  case as potentially billable. Nothing is ever refunded or reset.
* Reservations are made atomically (``BEGIN IMMEDIATE``): the cumulative dollar and call totals are checked and the reservation committed in one transaction.

A local filesystem lock cannot protect a different host: the single designated host is part of the procedure, and the host fingerprint refuses a copied ledger elsewhere.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import platform
import sqlite3
import threading
import stat
import subprocess
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

from src.p10e.errors import BudgetExceeded, LiveRunRefused

ROOT = Path(__file__).resolve().parents[2]
DB_NAME = "ledger.sqlite"
LOCK_NAME = "session.lock"
IMMUTABLE_META = ("genesis_id", "environment_id", "host_fingerprint", "approved_total_usd", "call_cap", "created_at")
ZERO = Decimal(0)

SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sessions(session_id TEXT PRIMARY KEY, pid INTEGER NOT NULL, uid INTEGER NOT NULL, started_at TEXT NOT NULL, ended_at TEXT, end_state TEXT);
CREATE TABLE entries(
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL, run_id TEXT NOT NULL, area TEXT NOT NULL, model TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('reserved','settled_known','settled_unknown','rejected')),
  reserved_usd TEXT NOT NULL, committed_usd TEXT NOT NULL, call_units INTEGER NOT NULL CHECK(call_units >= 1),
  input_tokens INTEGER, output_tokens INTEGER, provider_cost_usd TEXT, status_code INTEGER, note TEXT,
  created_at TEXT NOT NULL, settled_at TEXT, prev_hash TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TRIGGER entries_no_delete BEFORE DELETE ON entries BEGIN SELECT RAISE(ABORT, 'ledger entries are append-only'); END;
CREATE TRIGGER entries_settled_immutable BEFORE UPDATE ON entries WHEN OLD.state != 'reserved' BEGIN SELECT RAISE(ABORT, 'a settled ledger entry is immutable'); END;
CREATE TRIGGER entries_identity_immutable BEFORE UPDATE ON entries WHEN NEW.seq != OLD.seq OR NEW.session_id != OLD.session_id OR NEW.run_id != OLD.run_id OR NEW.area != OLD.area
  OR NEW.model != OLD.model OR NEW.reserved_usd != OLD.reserved_usd OR NEW.call_units != OLD.call_units OR NEW.created_at != OLD.created_at OR NEW.prev_hash != OLD.prev_hash OR NEW.row_hash != OLD.row_hash
  BEGIN SELECT RAISE(ABORT, 'the identity and reservation of a ledger entry are immutable'); END;
CREATE TRIGGER meta_no_delete BEFORE DELETE ON meta BEGIN SELECT RAISE(ABORT, 'ledger metadata is append-only'); END;
CREATE TRIGGER meta_identity_immutable BEFORE UPDATE ON meta WHEN OLD.key IN ('genesis_id','environment_id','host_fingerprint','approved_total_usd','call_cap','created_at')
  BEGIN SELECT RAISE(ABORT, 'ledger identity is immutable'); END;
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def host_fingerprint() -> str:
    """A stable, non-reversible identifier of this host (hash only; never the raw identifier)."""
    raw = None
    try:
        if platform.system() == "Darwin":
            out = subprocess.check_output(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], stderr=subprocess.DEVNULL, timeout=10).decode()
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    raw = line.split("=")[-1].strip().strip('"')
        elif Path("/etc/machine-id").exists():
            raw = Path("/etc/machine-id").read_text().strip()
    except Exception:  # noqa: BLE001
        raw = None
    raw = raw or f"{platform.node()}|{uuid.getnode()}"
    return hashlib.sha256(("p10e-host|" + raw).encode()).hexdigest()[:32]


def _row_hash(prev: str, seq: int, session_id: str, run_id: str, model: str, reserved_usd: str, created_at: str) -> str:
    return hashlib.sha256("|".join((prev, str(seq), session_id, run_id, model, reserved_usd, created_at)).encode()).hexdigest()


def check_location(directory: Path, *, repo_root: Path = ROOT) -> Path:
    """The ledger directory must be explicit, absolute, outside every Git checkout of this project, owned by the running user and closed to group and others."""
    p = Path(directory).expanduser()
    if not p.is_absolute():
        raise LiveRunRefused("ledger_location_invalid", "The ledger location must be an absolute path.")
    p = p.resolve()
    root = repo_root.resolve()
    if p == root or root in p.parents or p in root.parents:
        raise LiveRunRefused("ledger_location_invalid", "The ledger must live outside the Git checkout (and not contain it).")
    for parent in [p, *p.parents]:
        if (parent / ".git").exists():
            raise LiveRunRefused("ledger_location_invalid", "The ledger must not be inside any Git working tree.")
    if p.exists():
        st = p.stat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or (st.st_mode & 0o077):
            raise LiveRunRefused("ledger_location_insecure", "The ledger directory must be owned by the running user and not accessible to group or others (mode 0700).")
    return p


class Ledger:
    def __init__(self, directory: Path, conn: sqlite3.Connection, lock_fd: int | None = None, session_id: str | None = None) -> None:
        self.dir, self.conn, self._lock_fd, self.session_id = directory, conn, lock_fd, session_id
        self.meta: dict[str, str] = {}
        self._mutex = threading.RLock()        # one connection shared by every thread of the session (the SDK and agents may call from worker threads); all access is serialized

    # ------------------------------------------------------------------ creation (once, explicit)
    @classmethod
    def create(cls, directory: Path, *, environment_id: str, approved_total_usd: Decimal, call_cap: int, repo_root: Path = ROOT) -> "Ledger":
        """Initialize a NEW ledger. Refuses if one exists. The caller (the CLI) additionally refuses when the authorization record already names a genesis id."""
        d = check_location(directory, repo_root=repo_root)
        db = d / DB_NAME
        if db.exists():
            raise LiveRunRefused("ledger_exists", "A ledger already exists here; it is never replaced or re-initialized.")
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(d, 0o700)
        conn = sqlite3.connect(db, isolation_level=None, check_same_thread=False)
        os.chmod(db, 0o600)
        conn.execute("PRAGMA synchronous=FULL")
        conn.executescript(SCHEMA)
        genesis = uuid.uuid4().hex
        meta = {"genesis_id": genesis, "environment_id": environment_id, "host_fingerprint": host_fingerprint(), "approved_total_usd": str(approved_total_usd), "call_cap": str(int(call_cap)),
                "created_at": _now(), "last_seq": "0", "last_hash": "GENESIS:" + genesis}
        with conn:
            for k, v in meta.items():
                conn.execute("INSERT INTO meta(key,value) VALUES(?,?)", (k, v))
        conn.close()
        return cls.open(d, expected_genesis=genesis, environment_id=environment_id, repo_root=repo_root, take_lock=False)

    # ------------------------------------------------------------------ opening (verified)
    @classmethod
    def open(cls, directory: Path, *, expected_genesis: str | None, environment_id: str | None, repo_root: Path = ROOT, take_lock: bool = True) -> "Ledger":
        d = check_location(directory, repo_root=repo_root)
        db = d / DB_NAME
        if not db.exists():
            raise LiveRunRefused("ledger_missing", "The persistent ledger is missing. It is NEVER re-initialized automatically: restore it from backup or have the owner reconcile.")
        if not expected_genesis:
            raise LiveRunRefused("ledger_not_designated", "The authorization record names no ledger genesis id, so no ledger is trusted yet.")
        lock_fd = None
        if take_lock:
            lock_fd = os.open(d / LOCK_NAME, os.O_RDWR | os.O_CREAT, 0o600)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                os.close(lock_fd)
                raise LiveRunRefused("ledger_locked", "Another P10E live session holds the exclusive ledger lock. Paid execution is refused.") from None
        try:
            conn = sqlite3.connect(db, isolation_level=None, timeout=30, check_same_thread=False)
            try:
                conn.execute("PRAGMA synchronous=FULL")
            except sqlite3.DatabaseError as exc:
                raise LiveRunRefused("ledger_corrupted", "The ledger cannot be read. Additional calls are refused.") from exc
            led = cls(d, conn, lock_fd)
            try:
                led.meta = dict(conn.execute("SELECT key,value FROM meta").fetchall())
            except sqlite3.DatabaseError as exc:
                raise LiveRunRefused("ledger_corrupted", "The ledger cannot be read. Additional calls are refused.") from exc
            led._verify(expected_genesis, environment_id)
            if take_lock:
                led._begin_session()
            return led
        except BaseException:
            if lock_fd is not None:
                os.close(lock_fd)
            raise

    def _verify(self, expected_genesis: str, environment_id: str | None) -> None:
        c = self.conn
        try:
            if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise LiveRunRefused("ledger_corrupted", "The ledger failed its integrity check. Additional calls are refused.")
            for t in ("entries_no_delete", "entries_settled_immutable", "entries_identity_immutable", "meta_no_delete", "meta_identity_immutable"):
                if not c.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND name=?", (t,)).fetchone():
                    raise LiveRunRefused("ledger_corrupted", "The ledger's append-only protections are missing.")
        except sqlite3.DatabaseError as exc:
            raise LiveRunRefused("ledger_corrupted", "The ledger cannot be read. Additional calls are refused.") from exc
        m = self.meta
        if m.get("genesis_id") != expected_genesis:
            raise LiveRunRefused("ledger_identity_mismatch", "This ledger is not the one the owner-reviewed authorization designates (genesis id differs). Refused: no second allowance exists.")
        if environment_id is not None and m.get("environment_id") != environment_id:
            raise LiveRunRefused("ledger_identity_mismatch", "The ledger belongs to a different execution environment.")
        if m.get("host_fingerprint") != host_fingerprint():
            raise LiveRunRefused("ledger_wrong_host", "The ledger is bound to a different host. P10E live execution is permitted only on the designated host.")
        prev = "GENESIS:" + m["genesis_id"]
        last_seq = 0
        for seq, sid, rid, model, rsv, created, ph, rh in c.execute("SELECT seq,session_id,run_id,model,reserved_usd,created_at,prev_hash,row_hash FROM entries ORDER BY seq"):
            if ph != prev or rh != _row_hash(prev, seq, sid, rid, model, rsv, created):
                raise LiveRunRefused("ledger_corrupted", "The ledger's hash chain is broken (an entry was altered, removed or reordered). Additional calls are refused.")
            prev, last_seq = rh, seq
        if str(last_seq) != m.get("last_seq") or prev != m.get("last_hash"):
            raise LiveRunRefused("ledger_corrupted", "The ledger's recorded head does not match its entries (truncation or tampering). Additional calls are refused.")

    def _begin_session(self) -> None:
        self.session_id = uuid.uuid4().hex
        c = self.conn
        with self._tx():
            for (sid,) in c.execute("SELECT session_id FROM sessions WHERE ended_at IS NULL").fetchall():
                # A previous session did not close cleanly. Whatever it left reserved is kept at its FULL worst case (potentially billable); nothing is refunded.
                c.execute("UPDATE entries SET state='settled_unknown', settled_at=?, note='session ended without settlement: kept at full worst case' WHERE session_id=? AND state='reserved'", (_now(), sid))
                c.execute("UPDATE sessions SET ended_at=?, end_state='recovered_unclean' WHERE session_id=?", (_now(), sid))
            c.execute("INSERT INTO sessions(session_id,pid,uid,started_at) VALUES(?,?,?,?)", (self.session_id, os.getpid(), os.getuid(), _now()))

    # ------------------------------------------------------------------ transactions
    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._mutex:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise
            else:
                self.conn.execute("COMMIT")

    def totals(self) -> dict[str, Any]:
        with self._mutex:
            return self._totals()

    def _totals(self) -> dict[str, Any]:
        c = self.conn
        usd = sum((Decimal(r[0]) for r in c.execute("SELECT committed_usd FROM entries")), ZERO)
        calls = c.execute("SELECT COALESCE(SUM(call_units),0) FROM entries").fetchone()[0]
        pend = c.execute("SELECT COUNT(*) FROM entries WHERE state='reserved'").fetchone()[0]
        unk = c.execute("SELECT COUNT(*) FROM entries WHERE state='settled_unknown'").fetchone()[0]
        rej = c.execute("SELECT COUNT(*) FROM entries WHERE state='rejected'").fetchone()[0]
        known = c.execute("SELECT COUNT(*) FROM entries WHERE state='settled_known'").fetchone()[0]
        return {"committed_usd": usd, "calls": int(calls), "pending": pend, "unknown": unk, "rejected": rej, "settled_known": known,
                "approved_total_usd": Decimal(self.meta["approved_total_usd"]), "call_cap": int(self.meta["call_cap"])}

    # ------------------------------------------------------------------ reserve and settle
    def reserve(self, *, run_id: str, area: str, model: str, reserved_usd: Decimal, call_units: int = 1, max_usd: Decimal, max_calls: int) -> int:
        """Atomically check the cumulative caps and persist the reservation. The caller may send the request only AFTER this returns."""
        if self.session_id is None:
            raise LiveRunRefused("no_session", "No exclusive session is held.")
        with self._tx() as c:
            usd = sum((Decimal(r[0]) for r in c.execute("SELECT committed_usd FROM entries")), ZERO)
            calls = c.execute("SELECT COALESCE(SUM(call_units),0) FROM entries").fetchone()[0]
            cap_usd = min(max_usd, Decimal(self.meta["approved_total_usd"]))
            cap_calls = min(int(max_calls), int(self.meta["call_cap"]))
            if calls + call_units > cap_calls:
                raise BudgetExceeded("call_limit", "The cumulative provider-call limit would be exceeded.")
            if usd + reserved_usd > cap_usd:
                raise BudgetExceeded("spend_ceiling", "This request could exceed the cumulative spending ceiling (worst case); it is refused.")
            seq = (c.execute("SELECT COALESCE(MAX(seq),0) FROM entries").fetchone()[0]) + 1
            prev = c.execute("SELECT value FROM meta WHERE key='last_hash'").fetchone()[0]
            created = _now()
            rsv = str(reserved_usd)
            rh = _row_hash(prev, seq, self.session_id, run_id, model, rsv, created)
            c.execute("INSERT INTO entries(seq,session_id,run_id,area,model,state,reserved_usd,committed_usd,call_units,created_at,prev_hash,row_hash) VALUES(?,?,?,?,?,'reserved',?,?,?,?,?,?)",
                      (seq, self.session_id, run_id, area, model, rsv, rsv, call_units, created, prev, rh))
            c.execute("UPDATE meta SET value=? WHERE key='last_seq'", (str(seq),))
            c.execute("UPDATE meta SET value=? WHERE key='last_hash'", (rh,))
            return seq

    def settle(self, seq: int, *, state: str, committed_usd: Decimal, input_tokens: int | None = None, output_tokens: int | None = None, provider_cost_usd: Decimal | None = None,
               status_code: int | None = None, note: str | None = None) -> None:
        if state not in ("settled_known", "settled_unknown", "rejected"):
            raise ValueError("invalid settlement state")
        with self._tx() as c:
            cur = c.execute("UPDATE entries SET state=?, committed_usd=?, input_tokens=?, output_tokens=?, provider_cost_usd=?, status_code=?, note=?, settled_at=? WHERE seq=? AND state='reserved'",
                            (state, str(committed_usd), input_tokens, output_tokens, None if provider_cost_usd is None else str(provider_cost_usd), status_code, note, _now(), seq))
            if cur.rowcount != 1:
                raise LiveRunRefused("ledger_corrupted", "A settlement referenced an entry that is not an open reservation.")

    # ------------------------------------------------------------------ closing
    def close(self, *, backup: bool = True) -> None:
        try:
            if self.session_id and self.conn:
                with self._tx() as c:
                    # Anything still reserved at a clean close is potentially billable and kept at its full worst case.
                    c.execute("UPDATE entries SET state='settled_unknown', settled_at=?, note='left open at close: kept at full worst case' WHERE session_id=? AND state='reserved'", (_now(), self.session_id))
                    c.execute("UPDATE sessions SET ended_at=?, end_state='closed' WHERE session_id=?", (_now(), self.session_id))
                if backup:
                    dst = self.dir / f"ledger.backup-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.sqlite"
                    b = sqlite3.connect(dst)
                    try:
                        self.conn.backup(b)
                    finally:
                        b.close()
                    os.chmod(dst, 0o600)
        finally:
            try:
                self.conn.close()
            finally:
                if self._lock_fd is not None:
                    fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                    os.close(self._lock_fd)
                    self._lock_fd = None

    def snapshot(self) -> dict:
        t = self.totals()
        return {"genesis_id": self.meta["genesis_id"], "environment_id": self.meta["environment_id"], "session_id": self.session_id, "committed_usd": str(t["committed_usd"]), "calls": t["calls"],
                "approved_total_usd": str(t["approved_total_usd"]), "call_cap": t["call_cap"], "remaining_usd": str(t["approved_total_usd"] - t["committed_usd"]), "remaining_calls": t["call_cap"] - t["calls"],
                "entries_unknown": t["unknown"], "entries_rejected": t["rejected"], "entries_known": t["settled_known"], "pending": t["pending"]}


def read_only_status(directory: Path, *, expected_genesis: str | None) -> dict:
    """Totals without taking the session lock or writing (for the status command). Verifies identity and the chain."""
    led = Ledger.open(directory, expected_genesis=expected_genesis, environment_id=None, take_lock=False)
    try:
        return {k: v for k, v in led.snapshot().items() if k != "session_id"}
    finally:
        led.conn.close()


__all__ = ["Ledger", "check_location", "host_fingerprint", "read_only_status"]
