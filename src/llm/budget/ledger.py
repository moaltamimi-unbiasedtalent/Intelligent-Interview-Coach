"""Durable, multi-process-safe spend ledger of the production AI budget governor (05C), generalised from ``src/demo_live/budget.py``.

Design rules (each is tested with mocked providers):

* ADMISSION IS ONE CONDITIONAL UPDATE. A reservation advances the class counter and the category counter with ``UPDATE ... SET held = held + :worst WHERE held + :worst <= :stop AND
  requests < :max``; a row count of 0 is a refusal. The database serialises those updates (row locks on PostgreSQL, the write lock on SQLite), so any number of threads and processes
  can never jointly exceed a ceiling. Limits are read from the CONFIGURATION on every call (they are never stored), so the owner can raise or lower a ceiling without a migration.
* ``held`` = settled actual cost + open reservations at their WORST case + unknown outcomes at their worst case (a timeout, a connection loss, a 5xx, a 200 without usage). A crash
  leaves open reservations in place; nothing is released silently.
* A settlement larger than its reservation (the estimate under-counted) engages the kill switch. The hard cap is a second, higher line that normal operation never reaches.
* Money is integer micro-USD. Unknown tokens, latency and costs are NULL, never 0.
* The ledger holds no prompt, response, key, user identifier or provider message; only a content-free request fingerprint.
* Any ledger problem refuses the request (fail closed).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from src.llm.budget.config import BudgetConfig, micro_to_usd
from src.llm.budget.errors import BudgetError
from src.persistence import AiBudgetControl, AiBudgetEntry

GLOBAL = "global"


def class_key(budget_class: str) -> str:
    return f"class:{budget_class}"


def category_key(budget_class: str, category: str) -> str:
    return f"cat:{budget_class}:{category}"


@dataclass(frozen=True)
class Reservation:
    entry_id: int
    budget_class: str
    category: str
    worst_case: int


class DbBudgetLedger:
    """The ledger over the application database (any SQLAlchemy engine the application uses: PostgreSQL in hosted environments, SQLite in development and tests)."""

    def __init__(self, session_factory: sessionmaker, *, clock: Callable[[], float] = time.time) -> None:
        self._sf = session_factory
        self._clock = clock
        self._known: set[str] = set()

    # ------------------------------------------------------------------ helpers
    def _ensure_rows(self, s: Session, keys: list[str]) -> None:
        """Create missing counter rows. WRITE-FIRST (an INSERT ... ON CONFLICT DO NOTHING, never a read followed by a write): on SQLite a read-then-write transaction can deadlock with
        another writer, a write-first one waits on the busy timeout instead. Rows already known to exist in this process are skipped."""
        missing = [k for k in keys if k not in self._known]
        if not missing:
            return
        dialect = s.get_bind().dialect.name
        for key in missing:
            if dialect == "sqlite":
                from sqlalchemy.dialects.sqlite import insert as dialect_insert
            elif dialect == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as dialect_insert
            else:  # pragma: no cover - the application supports only these two
                raise BudgetError("ledger_unavailable", "Unsupported database dialect for the budget ledger (fail closed).")
            s.execute(dialect_insert(AiBudgetControl).values(scope_key=key, held_micro_usd=0, requests=0, killed=False, updated_at=datetime.now(timezone.utc)).on_conflict_do_nothing())
        s.commit()
        self._known.update(missing)

    def ensure_ready(self) -> None:
        """Raise ``ledger_unavailable`` unless the ledger tables are usable (called at install so a missing migration fails closed up front)."""
        try:
            with self._sf() as s:
                s.execute(select(func.count()).select_from(AiBudgetControl)).scalar()
                s.execute(select(func.count()).select_from(AiBudgetEntry)).scalar()
        except SQLAlchemyError:
            raise BudgetError("ledger_unavailable", "The budget ledger tables are not available (is migration 0044 applied?). Paid calls are refused (fail closed).") from None

    # ------------------------------------------------------------------ kill switch
    def killed(self) -> bool:
        try:
            with self._sf() as s:
                row = s.get(AiBudgetControl, GLOBAL)
                return bool(row and row.killed)
        except SQLAlchemyError:
            return True                                   # an unreadable switch is treated as engaged

    def kill(self, reason: str = "operator") -> None:
        with self._sf() as s:
            self._ensure_rows(s, [GLOBAL])
            s.execute(update(AiBudgetControl).where(AiBudgetControl.scope_key == GLOBAL).values(killed=True, kill_reason=reason[:64]))
            s.commit()

    def resume(self) -> None:
        with self._sf() as s:
            self._ensure_rows(s, [GLOBAL])
            s.execute(update(AiBudgetControl).where(AiBudgetControl.scope_key == GLOBAL).values(killed=False, kill_reason=None))
            s.commit()

    # ------------------------------------------------------------------ reservation
    def reserve(self, config: BudgetConfig, *, budget_class: str, category: str, operation: str, model: str, endpoint: str, fingerprint: str, worst_case: int) -> Reservation:
        """Atomically admit and record a reservation or raise ``BudgetError``. Bounded retries and duplicate suppression are decided here, in the same transaction."""
        cls = config.classes.get(budget_class)
        if cls is None:
            raise BudgetError("class_not_configured", f"Budget class {budget_class!r} has no configured ceiling (fail closed).")
        cat = cls.categories.get(category)
        if cat is None:
            raise BudgetError("category_not_configured", f"Category {category!r} has no configured ceiling in class {budget_class!r} (fail closed).")
        if worst_case > cat.stop:
            raise BudgetError("request_exceeds_category", "A single request's worst case exceeds the category stop threshold.")
        now = self._clock()
        try:
            with self._sf() as s:
                self._ensure_rows(s, [GLOBAL, class_key(budget_class), category_key(budget_class, category)])
                # The first statement of the admission transaction is a WRITE (it takes the database write lock up front, so the checks below see a stable state).
                s.execute(update(AiBudgetControl).where(AiBudgetControl.scope_key == GLOBAL).values(updated_at=datetime.now(timezone.utc)))
                if bool(s.execute(select(AiBudgetControl.killed).where(AiBudgetControl.scope_key == GLOBAL)).scalar()):
                    s.rollback()
                    raise BudgetError("kill_switch", "The AI budget kill switch is engaged; no provider request is sent.")
                self._check_duplicates(s, config, fingerprint, now)
                ck, gk = class_key(budget_class), category_key(budget_class, category)
                # (1) the class counter: held + worst <= stop AND requests < max. (2) the category counter. Either failing rolls the whole transaction back.
                hit = s.execute(update(AiBudgetControl).where(AiBudgetControl.scope_key == ck, AiBudgetControl.held_micro_usd + worst_case <= cls.ceiling.stop,
                                                              AiBudgetControl.requests < cls.max_requests)
                                .values(held_micro_usd=AiBudgetControl.held_micro_usd + worst_case, requests=AiBudgetControl.requests + 1))
                if hit.rowcount != 1:
                    s.rollback()
                    raise BudgetError(*self._class_refusal(config, budget_class, worst_case))
                hit = s.execute(update(AiBudgetControl).where(AiBudgetControl.scope_key == gk, AiBudgetControl.held_micro_usd + worst_case <= cat.stop)
                                .values(held_micro_usd=AiBudgetControl.held_micro_usd + worst_case, requests=AiBudgetControl.requests + 1))
                if hit.rowcount != 1:
                    s.rollback()
                    raise BudgetError("category_stop", f"The {category} allocation of the {budget_class} budget would be exceeded by this request.")
                entry = AiBudgetEntry(created_ts=now, budget_class=budget_class, category=category, operation=operation[:48], model=model[:160], endpoint=endpoint,
                                      fingerprint=fingerprint, state="reserved", reserved_micro_usd=worst_case)
                s.add(entry)
                try:
                    s.flush()
                except IntegrityError:
                    s.rollback()
                    raise BudgetError("duplicate_in_flight", "An identical request is already in flight; it is not sent twice.") from None
                s.commit()
                return Reservation(entry.id, budget_class, category, worst_case)
        except BudgetError:
            raise
        except SQLAlchemyError:
            raise BudgetError("ledger_error", "The budget ledger could not record the reservation; the request is refused (fail closed).") from None

    def _class_refusal(self, config: BudgetConfig, budget_class: str, worst_case: int) -> tuple[str, str]:
        with self._sf() as s:
            row = s.get(AiBudgetControl, class_key(budget_class))
            held, n = (row.held_micro_usd, row.requests) if row else (0, 0)
        cls = config.classes[budget_class]
        if n >= cls.max_requests:
            return "request_cap", f"The request cap of the {budget_class} budget is reached."
        return "stop_threshold", f"The {budget_class} stop threshold would be exceeded (held {micro_to_usd(held)} USD, this request up to {micro_to_usd(worst_case)} USD)."

    def _check_duplicates(self, s: Session, config: BudgetConfig, fingerprint: str, now: float) -> None:
        """Bounded retries and no retry after an unknown outcome. A call that was REFUSED by the provider before any inference (429 and other determinate rejections) may be retried up to
        ``max_retries`` times inside the window; a call whose outcome is unknown (timeout, 5xx, no usage) is never sent again automatically, because it may already have been billed."""
        window = config.limits.dedupe_window_s
        if window <= 0:
            return
        since = now - window
        rows = s.execute(select(AiBudgetEntry.state, func.count()).where(AiBudgetEntry.fingerprint == fingerprint, AiBudgetEntry.created_ts >= since).group_by(AiBudgetEntry.state)).all()
        by_state = {st: n for st, n in rows}
        if by_state.get("unknown"):
            raise BudgetError("unknown_outcome_no_retry", "An identical earlier request has an unknown outcome (possibly billed); it is not retried automatically.")
        if by_state.get("rejected", 0) > config.limits.max_retries:
            raise BudgetError("retry_limit", "The bounded retry limit for this request is reached.")

    # ------------------------------------------------------------------ settlement
    def settle(self, reservation: Reservation, *, outcome: str, committed: int = 0, input_tokens: int | None = None, output_tokens: int | None = None,
               est_cost: int | None = None, provider_cost: int | None = None, status_code: int | None = None, latency_ms: int | None = None, error_category: str | None = None) -> None:
        """Close a reservation. ``unknown`` keeps the full worst case; ``rejected`` (a determinate provider refusal) releases the money but the call stays counted."""
        if outcome not in ("settled", "rejected", "unknown"):
            raise ValueError(outcome)
        try:
            with self._sf() as s:
                delta = (committed - reservation.worst_case) if outcome == "settled" else (-reservation.worst_case if outcome == "rejected" else 0)
                done = s.execute(update(AiBudgetEntry).where(AiBudgetEntry.id == reservation.entry_id, AiBudgetEntry.state == "reserved")
                                 .values(state=outcome, committed_micro_usd=committed if outcome == "settled" else 0, input_tokens=input_tokens, output_tokens=output_tokens,
                                         est_cost_micro_usd=est_cost, provider_cost_micro_usd=provider_cost, status_code=status_code, latency_ms=latency_ms,
                                         error_category=error_category, settled_ts=self._clock()))
                if done.rowcount != 1:                        # already settled (idempotent)
                    s.rollback()
                    return
                if delta:
                    for key in (class_key(reservation.budget_class), category_key(reservation.budget_class, reservation.category)):
                        s.execute(update(AiBudgetControl).where(AiBudgetControl.scope_key == key).values(held_micro_usd=AiBudgetControl.held_micro_usd + delta))
                if outcome == "settled" and committed > reservation.worst_case:
                    s.execute(update(AiBudgetControl).where(AiBudgetControl.scope_key == GLOBAL).values(killed=True, kill_reason="overrun"))
                s.commit()
        except SQLAlchemyError:
            # The reservation stays open at its worst case (it is never released silently); the failure is not hidden from the caller's accounting.
            raise BudgetError("ledger_error", "The budget ledger could not record the settlement; the reservation stays held at its worst case.") from None

    # ------------------------------------------------------------------ reporting (counts and money only)
    def snapshot(self, config: BudgetConfig, budget_class: str) -> dict[str, Any]:
        cls = config.classes[budget_class]
        with self._sf() as s:
            g = s.get(AiBudgetControl, GLOBAL)
            cr = s.get(AiBudgetControl, class_key(budget_class))
            held, requests = (cr.held_micro_usd, cr.requests) if cr else (0, 0)
            cats = {}
            for name, ceil in cls.categories.items():
                r = s.get(AiBudgetControl, category_key(budget_class, name))
                h = r.held_micro_usd if r else 0
                cats[name] = {"hard_cap_usd": micro_to_usd(ceil.hard_cap), "stop_usd": micro_to_usd(ceil.stop), "held_usd": micro_to_usd(h), "remaining_to_stop_usd": micro_to_usd(max(ceil.stop - h, 0))}
            states = {st: n for st, n in s.execute(select(AiBudgetEntry.state, func.count()).where(AiBudgetEntry.budget_class == budget_class).group_by(AiBudgetEntry.state)).all()}
            agg = s.execute(select(func.coalesce(func.sum(AiBudgetEntry.committed_micro_usd), 0), func.count(AiBudgetEntry.input_tokens), func.sum(AiBudgetEntry.input_tokens),
                                   func.sum(AiBudgetEntry.output_tokens), func.avg(AiBudgetEntry.latency_ms), func.count(AiBudgetEntry.error_category))
                            .where(AiBudgetEntry.budget_class == budget_class)).one()
            unknown_held = s.execute(select(func.coalesce(func.sum(AiBudgetEntry.reserved_micro_usd), 0)).where(AiBudgetEntry.budget_class == budget_class, AiBudgetEntry.state == "unknown")).scalar()
            open_held = s.execute(select(func.coalesce(func.sum(AiBudgetEntry.reserved_micro_usd), 0)).where(AiBudgetEntry.budget_class == budget_class, AiBudgetEntry.state == "reserved")).scalar()
        known_calls = int(agg[1] or 0)
        return {
            "budget_class": budget_class, "killed": bool(g and g.killed), "kill_reason": g.kill_reason if g and g.killed else None,
            "hard_cap_usd": micro_to_usd(cls.ceiling.hard_cap), "stop_usd": micro_to_usd(cls.ceiling.stop), "held_usd": micro_to_usd(held),
            "settled_usd": micro_to_usd(int(agg[0] or 0)), "open_reservations_usd": micro_to_usd(int(open_held or 0)), "unknown_held_usd": micro_to_usd(int(unknown_held or 0)),
            "remaining_to_stop_usd": micro_to_usd(max(cls.ceiling.stop - held, 0)), "remaining_to_hard_cap_usd": micro_to_usd(max(cls.ceiling.hard_cap - held, 0)),
            "requests": requests, "request_cap": cls.max_requests, "remaining_requests": max(cls.max_requests - requests, 0), "calls_by_state": states,
            "input_tokens_known": int(agg[2]) if known_calls else None, "output_tokens_known": int(agg[3]) if known_calls else None, "calls_with_known_usage": known_calls,
            "average_latency_ms": round(float(agg[4]), 1) if agg[4] is not None else None, "provider_error_calls": int(agg[5] or 0), "categories": cats,
        }

    def integrity(self, budget_class: str) -> dict[str, Any]:
        """Recompute the counters from the entries. A drift means the counters cannot be trusted (reported by the status; never silently repaired)."""
        with self._sf() as s:
            expect = s.execute(select(func.coalesce(func.sum(AiBudgetEntry.committed_micro_usd), 0)).where(AiBudgetEntry.budget_class == budget_class, AiBudgetEntry.state == "settled")).scalar() or 0
            expect += s.execute(select(func.coalesce(func.sum(AiBudgetEntry.reserved_micro_usd), 0)).where(AiBudgetEntry.budget_class == budget_class, AiBudgetEntry.state.in_(("reserved", "unknown")))).scalar() or 0
            n = s.execute(select(func.count()).select_from(AiBudgetEntry).where(AiBudgetEntry.budget_class == budget_class)).scalar() or 0
            row = s.get(AiBudgetControl, class_key(budget_class))
            held, requests = (row.held_micro_usd, row.requests) if row else (0, 0)
        return {"consistent": held == int(expect) and requests == int(n), "counter_held": held, "entries_held": int(expect), "counter_requests": requests, "entries": int(n)}
