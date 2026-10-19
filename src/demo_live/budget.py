"""Durable, multi-process-atomic budget ledger for the capstone live demonstration (EUR, integer micro-euros).

Design rules (each is tested with mocked providers and simulated exhaustion):
* A reservation is committed to the ledger BEFORE the request is dispatched, inside one ``BEGIN IMMEDIATE`` SQLite transaction, so concurrent threads and concurrent
  processes (the API, the RAGAS CLI) can never jointly exceed the budget.
* What counts against the budget is the sum of: settled actual cost, open reservations at their WORST case, and unknown outcomes (a timeout, a connection loss, a
  server error, a response without usage) kept at their worst case forever. A crash leaves open reservations in place; they are never released silently.
* Admission needs ``held + worst_case <= min(category cap, operating stop)``; the operating stop (EUR 8.00) is below the hard cap (EUR 10.00), and the hard cap is
  never reachable by normal operation. The safety reserve is released only by an explicit operator action, and even then the cap is never exceeded.
* The ledger is outside the repository, is its own database with its own genesis, and has no connection to the P10E ledger.
* Anything missing or inconsistent (authorization, pricing, ledger, kill switch) fails CLOSED.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import stat
import threading
import time
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any

MICRO = Decimal(1_000_000)
ROOT = Path(__file__).resolve().parents[2]
AUTH_PATH = ROOT / "evaluations/demo_live/authorization.json"
PRICING_PATH = ROOT / "evaluations/demo_live/pricing.json"
KILL_FILE = "KILL"


class DemoBudgetError(Exception):
    """A request was refused. ``reason`` is a stable machine code; the message never carries prompts, keys or provider text."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def micros(value: str | Decimal | int) -> int:
    return int((Decimal(str(value)) * MICRO).to_integral_value(rounding=ROUND_CEILING))


def eur(micro: int) -> str:
    return f"{Decimal(micro) / MICRO:.6f}"


@dataclass(frozen=True)
class Limits:
    max_requests_total: int
    max_input_tokens: int
    max_output_tokens: int
    request_timeout_s: int
    max_retries: int
    max_concurrency: int


@dataclass(frozen=True)
class Authorization:
    raw: dict
    cap: int
    stop: int
    usd_to_eur: Decimal
    category_caps: dict[str, int]
    reserve: int
    limits: Limits
    hosts: tuple[str, ...]
    endpoints: tuple[str, ...]


def load_authorization(path: Path = AUTH_PATH) -> Authorization:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        lim = raw["limits"]
        auth = Authorization(
            raw=raw, cap=micros(raw["cap_eur"]), stop=micros(raw["normal_operating_stop_eur"]), usd_to_eur=Decimal(str(raw["usd_to_eur_rate_applied"])),
            category_caps={k: micros(v) for k, v in raw["category_caps_eur"].items()}, reserve=micros(raw["safety_reserve_eur"]),
            limits=Limits(int(lim["max_requests_total"]), int(lim["max_input_tokens_per_request"]), int(lim["max_output_tokens_per_request"]), int(lim["request_timeout_s"]),
                          int(lim["max_retries"]), int(lim["max_concurrency"])),
            hosts=tuple(raw["allowed_provider_hosts"]), endpoints=tuple(raw["allowed_priced_endpoints"]))
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise DemoBudgetError("authorization_unavailable", f"The demonstration authorization record is missing or invalid ({type(exc).__name__}).") from None
    if raw.get("currency") != "EUR" or auth.cap <= 0 or auth.stop <= 0 or auth.stop > auth.cap or auth.usd_to_eur <= 0 or auth.usd_to_eur < Decimal("1"):
        raise DemoBudgetError("authorization_invalid", "The authorization must be in EUR, have 0 < stop <= cap, and count USD at a rate of at least 1.00 (conservative).")
    if auth.cap > micros("10.00") or sum(auth.category_caps.values()) + auth.reserve > auth.cap:
        raise DemoBudgetError("authorization_invalid", "The category caps plus the reserve exceed the cap, or the cap is above the owner-approved EUR 10.00.")
    return auth


def load_pricing(path: Path = PRICING_PATH) -> dict[str, tuple[Decimal, Decimal]]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))["models"]
        return {m: (Decimal(p["prompt"]), Decimal(p["completion"])) for m, p in raw.items()}
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise DemoBudgetError("pricing_unavailable", f"The pricing snapshot is missing or invalid ({type(exc).__name__}).") from None


def estimate_tokens(text: str) -> int:
    """Pessimistic input estimate (about 3 characters per token)."""
    return max(1, -(-len(text) // 3))


SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS entries (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, category TEXT NOT NULL, operation TEXT NOT NULL, model TEXT NOT NULL, endpoint TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('reserved','settled','rejected','unknown')), reserved INTEGER NOT NULL, committed INTEGER NOT NULL DEFAULT 0,
  input_tokens INTEGER, output_tokens INTEGER, est_cost INTEGER, provider_cost INTEGER, status_code INTEGER, note TEXT);
"""


class DemoBudget:
    """One handle on the ledger directory; safe across threads (RLock) and processes (SQLite IMMEDIATE transactions)."""

    def __init__(self, directory: str | Path, authorization: Authorization | None = None) -> None:
        self.dir = Path(directory)
        self.auth = authorization or load_authorization()
        self.dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.dir, stat.S_IRWXU)
        self.path = self.dir / "ledger.db"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), timeout=30.0, isolation_level=None, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.executescript(SCHEMA)
        try:
            os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        self._ensure_genesis()

    # ------------------------------------------------------------------ genesis and integrity
    def _ensure_genesis(self) -> None:
        a = self.auth
        wanted = {"cap": str(a.cap), "stop": str(a.stop), "usd_to_eur": str(a.usd_to_eur), "category_caps": json.dumps(a.category_caps, sort_keys=True), "reserve": str(a.reserve),
                  "limits": json.dumps(a.limits.__dict__, sort_keys=True)}
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                have = dict(self._conn.execute("SELECT key, value FROM meta").fetchall())
                if not have:
                    for k, v in {**wanted, "genesis_id": secrets.token_hex(8), "created_at": str(time.time()), "reserve_released": "0"}.items():
                        self._conn.execute("INSERT INTO meta VALUES (?, ?)", (k, v))
                else:
                    for k, v in wanted.items():
                        if have.get(k) != v:
                            self._conn.execute("ROLLBACK")
                            raise DemoBudgetError("ledger_mismatch", f"The ledger was created under different limits ({k}); it is never edited. Use a new ledger directory.")
                self._conn.execute("COMMIT")
            except DemoBudgetError:
                raise
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def _meta(self, key: str) -> str:
        row = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else ""

    # ------------------------------------------------------------------ kill switch
    @property
    def kill_path(self) -> Path:
        return self.dir / KILL_FILE

    def killed(self) -> bool:
        return self.kill_path.exists()

    def kill(self, why: str = "operator") -> None:
        self.kill_path.write_text(why[:200], encoding="utf-8")

    def resume(self) -> None:
        self.kill_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------ accounting
    def _held(self, category: str | None = None) -> int:
        q = "SELECT COALESCE(SUM(CASE state WHEN 'settled' THEN committed WHEN 'rejected' THEN 0 ELSE reserved END),0) FROM entries"
        args: tuple = ()
        if category:
            q += " WHERE category=?"
            args = (category,)
        return int(self._conn.execute(q, args).fetchone()[0])

    def operating_limit(self) -> int:
        return self.auth.cap if self._meta("reserve_released") == "1" else self.auth.stop

    def release_reserve(self) -> None:
        with self._lock:
            self._conn.execute("UPDATE meta SET value='1' WHERE key='reserve_released'")

    def reserve(self, *, category: str, operation: str, model: str, endpoint: str, worst_case: int) -> int:
        """Atomically admit and record a reservation or raise ``DemoBudgetError``. Returns the entry sequence."""
        a = self.auth
        with self._lock:
            if self.killed():
                raise DemoBudgetError("kill_switch", "The demonstration kill switch is engaged; no provider request is sent.")
            if category not in a.category_caps:
                raise DemoBudgetError("category_unknown", f"The request has no recognised budget category ({category!r}); it is refused (fail closed).")
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                n = int(self._conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0])
                if n >= a.limits.max_requests_total:
                    raise DemoBudgetError("request_cap", "The total request cap for the demonstration is reached.")
                held_total = self._held()
                if held_total + worst_case > self.operating_limit():
                    raise DemoBudgetError("operating_stop", f"The operating stop would be exceeded (held {eur(held_total)} EUR, this request up to {eur(worst_case)} EUR).")
                if held_total + worst_case > a.cap:
                    raise DemoBudgetError("hard_cap", "The hard cap would be exceeded.")
                held_cat = self._held(category)
                if self._meta("reserve_released") != "1" and held_cat + worst_case > a.category_caps[category]:       # once the reserve is released only the total limit applies
                    raise DemoBudgetError("category_cap", f"The {category} allocation would be exceeded (held {eur(held_cat)} EUR, this request up to {eur(worst_case)} EUR).")
                cur = self._conn.execute("INSERT INTO entries (ts, category, operation, model, endpoint, state, reserved) VALUES (?,?,?,?,?, 'reserved', ?)",
                                         (time.time(), category, operation, model, endpoint, worst_case))
                seq = int(cur.lastrowid)
                self._conn.execute("COMMIT")
                return seq
            except DemoBudgetError:
                self._conn.execute("ROLLBACK")
                raise
            except Exception:
                self._conn.execute("ROLLBACK")
                raise DemoBudgetError("ledger_error", "The budget ledger could not record the reservation; the request is refused (fail closed).") from None

    def settle(self, seq: int, *, outcome: str, committed: int = 0, input_tokens: int | None = None, output_tokens: int | None = None, est_cost: int | None = None,
               provider_cost: int | None = None, status_code: int | None = None, note: str = "") -> None:
        """Close a reservation. ``unknown`` keeps the full worst case; ``rejected`` (a determinate provider refusal) releases the money but keeps the call counted."""
        if outcome not in ("settled", "rejected", "unknown"):
            raise ValueError(outcome)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute("SELECT reserved FROM entries WHERE seq=? AND state='reserved'", (seq,)).fetchone()
                if row is None:
                    self._conn.execute("ROLLBACK")
                    return
                reserved = int(row[0])
                if outcome == "settled" and committed > reserved:
                    note = (note + " OVERRUN: actual exceeded the reservation; kill switch engaged").strip()
                    self.kill("overrun")
                self._conn.execute("UPDATE entries SET state=?, committed=?, input_tokens=?, output_tokens=?, est_cost=?, provider_cost=?, status_code=?, note=? WHERE seq=?",
                                   (outcome, committed if outcome == "settled" else 0, input_tokens, output_tokens, est_cost, provider_cost, status_code, note, seq))
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    # ------------------------------------------------------------------ reporting
    def summary(self) -> dict[str, Any]:
        a = self.auth
        with self._lock:
            q = self._conn.execute
            committed = int(q("SELECT COALESCE(SUM(committed),0) FROM entries WHERE state='settled'").fetchone()[0])
            open_res = int(q("SELECT COALESCE(SUM(reserved),0) FROM entries WHERE state='reserved'").fetchone()[0])
            unknown = int(q("SELECT COALESCE(SUM(reserved),0) FROM entries WHERE state='unknown'").fetchone()[0])
            held = committed + open_res + unknown
            calls = int(q("SELECT COUNT(*) FROM entries").fetchone()[0])
            by_cat = {c: {"cap_eur": eur(cap), "held_eur": eur(self._held(c))} for c, cap in a.category_caps.items()}
            by_model = {m: n for m, n in q("SELECT model, COUNT(*) FROM entries GROUP BY model").fetchall()}
            by_state = {s: n for s, n in q("SELECT state, COUNT(*) FROM entries GROUP BY state").fetchall()}
        limit = self.operating_limit()
        return {"genesis_id": self._meta("genesis_id"), "currency": "EUR", "cap_eur": eur(a.cap), "operating_stop_eur": eur(limit), "reserve_released": self._meta("reserve_released") == "1",
                "settled_eur": eur(committed), "reserved_open_eur": eur(open_res), "unknown_held_eur": eur(unknown), "held_total_eur": eur(held),
                "remaining_to_stop_eur": eur(max(limit - held, 0)), "remaining_to_cap_eur": eur(max(a.cap - held, 0)), "requests": calls, "request_cap": a.limits.max_requests_total,
                "requests_by_state": by_state, "requests_by_model": by_model, "categories": by_cat, "kill_switch": self.killed(),
                "note": "All figures are ESTIMATES from the pricing snapshot and reported usage, held conservatively (USD counted 1:1 as EUR); they are not confirmed provider charges."}

    def recent(self, n: int = 12) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT seq, ts, category, operation, model, endpoint, state, reserved, committed, input_tokens, output_tokens, status_code, note FROM entries ORDER BY seq DESC LIMIT ?", (n,)).fetchall()
        keys = ("seq", "ts", "category", "operation", "model", "endpoint", "state", "reserved", "committed", "input_tokens", "output_tokens", "status_code", "note")
        return [dict(zip(keys, r)) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
