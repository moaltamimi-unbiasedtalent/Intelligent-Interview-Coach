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
import sys
from typing import Mapping

from src.llm.budget import governor as G
from src.llm.budget.errors import BudgetError

REFUSED_EXIT = 2


def require_paid_budget(script: str, *, budget_class: str = "evaluation", category: str = "evaluation", session_factory=None,
                        environ: Mapping[str, str] | None = None) -> G.BudgetGovernor:
    """Return an OPEN, installed governor or raise ``BudgetError``. ``script`` is only a label for the operator."""
    existing = G.active_governor()
    if existing is not None:
        if not existing.is_open:
            raise BudgetError(existing.closed_reason or "governor_closed", f"{script}: the AI budget governor is closed.")
        existing._open_or_refuse()
        if existing.budget_class != budget_class:
            raise BudgetError("class_mismatch", "The installed budget is not approved for this script class.")
        return existing
    if session_factory is None:
        from src.config import load_config
        from src.persistence import make_engine, make_session_factory

        session_factory = make_session_factory(make_engine(load_config().database_url))
    governor = G.BudgetGovernor.build(session_factory, budget_class=budget_class, default_category=category, environ=environ)
    if governor.killed():
        raise BudgetError("kill_switch", f"{script}: the AI budget kill switch is engaged.")
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
