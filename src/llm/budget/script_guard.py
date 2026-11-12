"""The ONE gate every paid-call path in ``scripts/`` goes through (05C).

A script that could make a paid provider call (an ``--allow-paid`` style flag, a ``--live`` run, a non-free embedder) calls ``guard_paid_script(...)`` AFTER its own existing refusals
(those are never weakened) and BEFORE the first provider request. The guard:

1. refuses in CI;
2. loads the owner's budget configuration (``AI_BUDGET_CONFIG_PATH``; none ships with the repository);
3. requires the approved-budget marker: ``AI_BUDGET_APPROVED_MARKER`` must equal the ``approval_marker`` the owner defined in that configuration (this repository, CI and agents never set it);
4. requires the durable ledger (migration 0044 applied) and a disengaged kill switch;
5. installs the governor's httpx chokepoint for the budget class (default ``evaluation``), so every request the script makes is reserved, bounded and settled.

Any problem prints a fixed refusal (reason code, never a key, marker or prompt) and the script exits non-zero. Nothing here makes a provider request.
"""

from __future__ import annotations

import atexit
import os
import sys
from pathlib import Path
from urllib.request import getproxies
from typing import Callable, Mapping

from src.llm.budget import governor as G
from src.llm.budget.config import GOVERNED_07B_LEDGER_ENV, load_config, require_approved_marker, validate_hosted_approval
from src.llm.budget.errors import BudgetError
from src.llm.budget.postgres_07b import validate_postgres_url

REFUSED_EXIT = 2


def require_paid_budget(script: str, *, budget_class: str = "evaluation", category: str = "evaluation", session_factory=None,
                        environ: Mapping[str, str] | None = None, governed_07b: bool = False,
                        prototype_handler: Callable | None = None) -> G.BudgetGovernor:
    """Return an OPEN, installed governor or raise ``BudgetError``. ``script`` is only a label for the operator."""
    env = os.environ if environ is None else environ
    existing = G.active_governor()
    config = None
    if governed_07b:
        from src.demo_live.guard import ProviderControl

        if env.get("CI") or env.get("GITHUB_ACTIONS"):
            raise BudgetError("ci_forbidden", "Paid provider calls never run in CI.")
        if existing is not None or ProviderControl._active is not None or env.get("ASK4MO_PROVIDER_MODE"):
            raise BudgetError("guard_conflict", "07B requires an exclusive governor without legacy controls.")
        if budget_class != "evaluation":
            raise BudgetError("class_mismatch", "07B requires the evaluation budget class.")
        if env.get("OPENAI_PROXY") or getproxies().keys() - {"no"}:
            raise BudgetError("provider_proxy_not_allowed", "07B requires direct provider transport.")
        config = load_config(environ=env)
        require_approved_marker(config, env)
        validate_hosted_approval(config, env, governed_07b=True)
    if existing is not None:
        if not existing.is_open:
            raise BudgetError(existing.closed_reason or "governor_closed", f"{script}: the AI budget governor is closed.")
        existing._open_or_refuse()
        if existing.budget_class != budget_class:
            raise BudgetError("class_mismatch", "The installed budget is not approved for this script class.")
        return existing
    if session_factory is None:
        from src.config import load_config as load_app_config
        from src.persistence import make_engine, make_session_factory

        if governed_07b:
            from sqlalchemy.engine import make_url

            try:
                url = make_url(env[GOVERNED_07B_LEDGER_ENV])
                backend = url.get_backend_name()
                if backend == "sqlite":
                    path = Path(url.database or "")
                    if url.query or not path.is_absolute() or path != path.resolve() or not path.is_file():
                        raise ValueError
                    engine = make_engine(env[GOVERNED_07B_LEDGER_ENV])
                elif backend == "postgresql":
                    from sqlalchemy import create_engine

                    validate_postgres_url(url)
                    engine = create_engine(url, connect_args={"hostaddr": url.host, "connect_timeout": 5},
                                           hide_parameters=True)
                else:
                    raise ValueError
                session_factory = make_session_factory(engine)
            except Exception:
                raise BudgetError("ledger_unavailable", "07B requires the approved dedicated durable ledger.") from None
        else:
            session_factory = make_session_factory(make_engine(load_app_config().database_url))
    governor = G.BudgetGovernor.build(session_factory, budget_class=budget_class, default_category=category,
                                     environ=env, config=config, governed_07b=governed_07b)
    if governor.killed():
        raise BudgetError("kill_switch", f"{script}: the AI budget kill switch is engaged.")
    if governed_07b and governor._unknown_07b():
        raise BudgetError("unknown_outcome_no_retry", "An earlier provider outcome requires reconciliation.")
    if governed_07b:
        governor.prototype_handler = prototype_handler
    G.install(governor)
    atexit.register(G.uninstall)
    return governor


def guard_embedder_script(script: str, embedder, *, session_factory=None, environ: Mapping[str, str] | None = None) -> int | None:
    """For scripts that build an embedder: a FREE (local hash) embedder needs nothing and ``None`` is returned; a paid one needs the governed budget (category ``embedding``)."""
    if getattr(embedder, "provider", None) == "local":
        return None
    return guard_paid_script(script, category="embedding", session_factory=session_factory, environ=environ)


def guard_paid_script(script: str, *, budget_class: str = "evaluation", category: str = "evaluation", session_factory=None,
                      environ: Mapping[str, str] | None = None) -> int | None:
    """``None`` when the paid run is approved and governed; otherwise prints the refusal and returns the exit code the script should return."""
    try:
        require_paid_budget(script, budget_class=budget_class, category=category, session_factory=session_factory, environ=environ)
    except BudgetError as exc:
        print(f"REFUSED by the AI budget governor ({exc.reason}): {exc}", file=sys.stderr)
        return REFUSED_EXIT
    return None
