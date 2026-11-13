"""Restricted PostgreSQL ledger for the synthetic governed 07B receiver.

The dedicated database owns policy, replay protection and monetary transitions.
The application's credential can execute only the dedicated runtime entry points.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime
from ipaddress import ip_address
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

from src.llm.budget.config import BudgetConfig, GOVERNED_07B_OPERATIONS, micro_to_usd, usd_to_micro
from src.llm.budget.errors import BudgetError
from src.llm.budget.ledger import Reservation, SQLITE_MAX_INTEGER

RUNTIME_ROLE = "ask4mo_07b_runtime"
SCHEMA_OWNER = "ask4mo_07b_owner"
_LIBPQ_OVERRIDES = frozenset({
    "PGHOST", "PGHOSTADDR", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD", "PGPASSFILE",
    "PGSERVICE", "PGSERVICEFILE", "PGSYSCONFDIR", "PGOPTIONS", "PGREQUIREAUTH", "PGCHANNELBINDING",
    "PGGSSENCMODE", "PGGSSLIB", "PGKRBSRVNAME", "PGTARGETSESSIONATTRS", "PGLOADBALANCEHOSTS",
    "PGCONNECT_TIMEOUT", "PGREQUIREPEER", "PGREQUIRESSL", "PGSSPIUSESPN", "PGMINPROTOCOLVERSION",
    "PGMAXPROTOCOLVERSION",
})
_REFUSALS = frozenset({
    "policy_mismatch", "kill_switch", "approval_invalid", "duplicate_in_flight",
    "unknown_outcome_no_retry", "retry_limit", "concurrency_limit", "total_request_cap",
    "request_cap", "total_stop", "stop_threshold", "category_stop", "handoff_refused",
    "settlement_refused", "authorization_invalid", "hold_not_reconcilable",
    "recovery_reconciliation_required", "ledger_inconsistent", "unsupported_isolation", "ledger_unavailable",
})

_VERIFY_BINDING = text("""
    SELECT session_user = :runtime AND current_user = :runtime, ledger_id, privileges_valid
    FROM ask4mo_07b.binding()
""")


def validate_postgres_url(url: URL) -> None:
    """Bind the synthetic-only PostgreSQL connection to one literal loopback endpoint."""
    if (url.drivername != "postgresql+psycopg" or url.username != RUNTIME_ROLE
            or not url.password or not url.host or not url.database or not url.port or url.query):
        raise BudgetError("ledger_unavailable", "07B requires the dedicated restricted PostgreSQL login.")
    try:
        loopback = ip_address(url.host).is_loopback
    except ValueError:
        loopback = False
    if (not loopback or not 0 < url.port <= 65535
            or any(key in _LIBPQ_OVERRIDES or key.startswith(("PGSSL", "PGOAUTH")) for key in os.environ)):
        raise BudgetError("ledger_unavailable", "07B requires the approved loopback PostgreSQL endpoint without libpq overrides.")


def database_policy(config: BudgetConfig) -> dict[str, Any]:
    """Project the approved budget into the exact record the provisioner binds."""
    approval = config.approval
    cls = config.classes["evaluation"]
    ledger_id = approval.get("postgres_ledger_id")
    try:
        identity = UUID(ledger_id) if isinstance(ledger_id, str) else None
    except ValueError:
        identity = None
    if identity is None or not identity.int or str(identity) != ledger_id:
        raise BudgetError("approval_invalid", "07B PostgreSQL requires a canonical approved ledger identity.")

    def moment(key: str) -> datetime:
        return datetime.fromisoformat(approval[key].replace("Z", "+00:00"))

    amounts = (config.total.stop, cls.ceiling.stop, *(limit.stop for limit in cls.categories.values()))
    limits = (*amounts, config.total_max_requests, cls.max_requests)
    if any(type(limit) is not int or not 0 <= limit <= SQLITE_MAX_INTEGER for limit in limits):
        raise BudgetError("approval_invalid", "07B PostgreSQL limits exceed the supported integer range.")
    operations = {}
    for operation, (endpoint, category) in GOVERNED_07B_OPERATIONS.items():
        model = approval["operation_models"][operation]
        price = config.pricing[model]
        output_cap = config.limits.max_output_tokens if endpoint == "chat" else 0
        reserve = usd_to_micro(config.limits.max_input_tokens * price.prompt + output_cap * price.completion)
        if reserve > SQLITE_MAX_INTEGER:
            raise BudgetError("approval_invalid", "07B PostgreSQL reservation exceeds the supported integer range.")
        operations[operation] = {
            "endpoint": endpoint, "category": category, "model": model, "reservation_micro_usd": reserve,
            "prompt_usd_per_token": str(price.prompt), "completion_usd_per_token": str(price.completion),
        }
    return {
        "ledger_id": ledger_id,
        "hash": config.raw_hash,
        "starts_at": max(moment("period_start"), moment("pricing_effective_at")).isoformat(),
        "expires_at": min(moment("expires_at"), moment("pricing_expires_at")).isoformat(),
        "total_stop": config.total.stop,
        "total_requests": config.total_max_requests,
        "class_stop": cls.ceiling.stop,
        "class_requests": cls.max_requests,
        "category_stops": {name: limit.stop for name, limit in cls.categories.items()},
        "operations": operations,
    }


class Postgres07BLedger:
    """Database-backed admission for the existing, synthetic-only HTTPX receiver."""

    def __init__(self, session_factory, config: BudgetConfig) -> None:
        self._sf = session_factory
        with session_factory() as session:
            self._url = session.get_bind().url
        self._policy = database_policy(config)
        self._policy_json = json.dumps(self._policy)

    def _verify_endpoint(self, connection) -> None:
        from psycopg import Connection

        if isinstance(connection, Connection) and not connection.autocommit:
            info = connection.info
            if ((info.host, getattr(info, "hostaddr", None), info.port, info.dbname, info.user)
                    == (self._url.host, self._url.host, self._url.port, self._url.database, RUNTIME_ROLE)
                    and 160000 <= info.server_version < 170000):
                return
        raise BudgetError("ledger_unavailable", "07B refused an unverified PostgreSQL connection endpoint.")

    @contextmanager
    def _transaction(self):
        try:
            validate_postgres_url(self._url)
            with self._sf.begin() as session:
                self._verify_endpoint(session.connection().connection.driver_connection)
                session.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
                session.execute(text("SET LOCAL search_path = pg_catalog, pg_temp"))
                session.execute(text("SET LOCAL statement_timeout = '5s'"))
                session.execute(text("SET LOCAL lock_timeout = '3s'"))
                binding = session.execute(_VERIFY_BINDING, {"runtime": RUNTIME_ROLE}).one_or_none()
                if binding is None or binding[0] is not True or binding[2] is not True:
                    raise BudgetError("ledger_unavailable", "07B refused an unverified PostgreSQL identity or privilege boundary.")
                if str(binding[1]) != self._policy["ledger_id"]:
                    raise BudgetError("policy_mismatch", "The connected PostgreSQL ledger does not match the approved identity.")
                yield session
        except SQLAlchemyError as exc:
            original = getattr(exc, "orig", None)
            reason = getattr(getattr(original, "diag", None), "message_primary", None)
            if getattr(original, "sqlstate", None) == "P0001" and reason in _REFUSALS:
                raise BudgetError(reason, "The PostgreSQL 07B ledger refused the operation.") from None
            raise BudgetError("ledger_error", "The PostgreSQL 07B ledger operation could not complete.") from None

    def _read(self, session) -> dict[str, Any]:
        state = session.scalar(text("SELECT ask4mo_07b.status()"))
        if state is None or state["policy"] != self._policy:
            raise BudgetError("policy_mismatch", "The database 07B policy does not match the approved configuration.")
        return state

    def ensure_ready(self) -> None:
        with self._transaction() as session:
            self._read(session)

    def killed(self) -> bool:
        try:
            with self._transaction() as session:
                return self._read(session)["killed"]
        except BudgetError:
            return True

    def reserve(self, config: BudgetConfig, *, budget_class: str, category: str, operation: str, model: str,
                endpoint: str, fingerprint: str, worst_case: int, governed_07b: bool = False) -> Reservation:
        if (not governed_07b or budget_class != "evaluation" or config.raw_hash != self._policy["hash"]
                or GOVERNED_07B_OPERATIONS.get(operation) != (endpoint, category)
                or type(worst_case) is not int or not 0 <= worst_case <= SQLITE_MAX_INTEGER):
            raise BudgetError("approval_invalid", "07B reservation does not match the dedicated PostgreSQL policy.")
        worst_case = max(worst_case, self._policy["operations"][operation]["reservation_micro_usd"])
        with self._transaction() as session:
            entry_id, token = session.execute(text("""
                SELECT entry_id, token FROM ask4mo_07b.reserve(
                    CAST(:policy AS jsonb), :operation, :model, :endpoint, :fingerprint, :worst)
            """), {"policy": self._policy_json, "operation": operation, "model": model,
                   "endpoint": endpoint, "fingerprint": fingerprint, "worst": worst_case}).one()
        return Reservation(entry_id, budget_class, category, worst_case, endpoint, token)

    def accept_07b_handoff(self, reservation: Reservation, accept: Callable[[], None]) -> None:
        with self._transaction() as session:
            session.execute(text("""
                SELECT ask4mo_07b.accept_handoff(:id, :token, CAST(:policy AS jsonb))
            """), {"id": reservation.entry_id, "token": reservation.capability, "policy": self._policy_json})
            accept()
        # The transaction commits before the receiver can invoke its handler.

    def settle(self, reservation: Reservation, *, outcome: str, committed: int = 0, input_tokens: int | None = None,
               output_tokens: int | None = None, est_cost: int | None = None, provider_cost: int | None = None,
               status_code: int | None = None, latency_ms: int | None = None, error_category: str | None = None) -> None:
        with self._transaction() as session:
            state = session.scalar(text("""
                SELECT ask4mo_07b.settle(:id, :token, :outcome, :cost, :input, :output,
                    :status, :latency, :error, :estimated, :reported)
            """), {"id": reservation.entry_id, "token": reservation.capability, "outcome": outcome,
                   "cost": committed, "input": input_tokens, "output": output_tokens, "status": status_code,
                   "latency": latency_ms, "error": error_category, "estimated": est_cost, "reported": provider_cost})
        if state == "unknown" and outcome != "unknown":
            raise BudgetError("outcome_unknown", "The PostgreSQL 07B ledger retained uncertain exposure.")

    def snapshot(self, config: BudgetConfig, budget_class: str) -> dict[str, Any]:
        cls = config.classes[budget_class]
        with self._transaction() as session:
            state = self._read(session)
        held = state["held"]
        requests = state["requests"]
        stop = min(cls.ceiling.stop, config.total.stop)
        hard_cap = min(cls.ceiling.hard_cap, config.total.hard_cap)
        request_cap = min(cls.max_requests, config.total_max_requests)
        categories = {}
        for name, limit in cls.categories.items():
            amount = state["categories"].get(name, 0)
            categories[name] = {
                "hard_cap_usd": micro_to_usd(limit.hard_cap), "stop_usd": micro_to_usd(limit.stop),
                "held_usd": micro_to_usd(amount), "remaining_to_stop_usd": micro_to_usd(max(limit.stop - amount, 0)),
            }
        return {
            "budget_class": budget_class, "killed": state["killed"], "kill_reason": state["kill_reason"],
            "hard_cap_usd": micro_to_usd(hard_cap), "stop_usd": micro_to_usd(stop),
            "held_usd": micro_to_usd(held), "settled_usd": micro_to_usd(state["settled"]),
            "open_reservations_usd": micro_to_usd(state["open"]), "unknown_held_usd": micro_to_usd(state["unknown"]),
            "remaining_to_stop_usd": micro_to_usd(max(stop - held, 0)),
            "remaining_to_hard_cap_usd": micro_to_usd(max(hard_cap - held, 0)),
            "requests": requests, "request_cap": request_cap, "remaining_requests": max(request_cap - requests, 0),
            "calls_by_state": state["states"], "input_tokens_known": state["input_tokens"],
            "output_tokens_known": state["output_tokens"], "calls_with_known_usage": state["known_calls"],
            "average_latency_ms": state["latency"], "provider_error_calls": state["errors"], "categories": categories,
        }

    def integrity(self, budget_class: str) -> dict[str, Any]:
        """Compare aggregates derived from the one durable entry set."""
        with self._transaction() as session:
            state = self._read(session)
        exposure = state["settled"] + state["open"] + state["unknown"]
        requests = sum(state["states"].values())
        return {
            "consistent": budget_class == "evaluation" and state["held"] == exposure == sum(state["categories"].values())
            and state["requests"] == requests,
            "counter_held": state["held"], "entries_held": exposure,
            "counter_requests": state["requests"], "entries": requests,
        }
