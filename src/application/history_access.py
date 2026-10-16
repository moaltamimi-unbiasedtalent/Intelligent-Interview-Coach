"""Canonical completed-interview HISTORY ACCESS policy (W12.4D-P2-B).

Owner-approved product rule: BASIC may access the latest THREE completed interviews; PREMIUM may access the complete eligible retained history. This is an
ACCESS limit, never a deletion, storage or retention limit: no record is removed, moved or rewritten by a plan change, and a re-upgrade restores access
without any data operation because nothing was ever taken away.

* **Default disabled.** ``HISTORY_RESTRICTIONS_ENFORCED = False`` is a code constant (like the billing gates and ``AI_COST_LIMITS_ENFORCED``): merging this change
  alters nothing for any real candidate. No setting, startup, Admin action, frontend flag, Premium preview or billing fixture can flip it. A later, reviewed
  release enables it (procedure in ``docs/capstone/product/W12_04D_P2_B_HISTORY_PROGRESS_ENTITLEMENTS.md``).
* **One authority.** The decision is read from the EXISTING ``EntitlementService`` (the caller's ACTIVE subscription, else the Basic fallback). There is no
  second entitlement system and no writer here. Premium means an ACTIVE Premium-plan subscription; ``premium_preview`` is a different, unrelated key and is
  never consulted. Unknown, unresolved, expired or unverified state resolves to Basic (fail closed to the approved window, never to unlimited). The plan label
  never comes from the client.
* **One selection mechanism.** ``InterviewRepository.eligible_ids`` (newest ``created_at`` then ``id``) is the only place "latest three" is computed; history,
  detail, exports, sharing, Opportunity views, progress and session reads all take the window from this policy and pass it to that mechanism.
* **Out of scope on purpose:** the candidate's privacy export, account deletion and the owner's own delete are data RIGHTS and are never gated here; Admin and
  internal processing use repositories without a window (Admin is not a data superuser: no admin route reads candidate interview content).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

# A code constant: nothing but a reviewed release can enable the restriction. Tests flip it on an isolated module attribute.
HISTORY_RESTRICTIONS_ENFORCED = False
BASIC_HISTORY_WINDOW = 3                       # owner-approved: the latest three COMPLETED interviews
_TEST_ENVS = ("development", "dev", "local", "test", "testing")

__all__ = ["HISTORY_RESTRICTIONS_ENFORCED", "BASIC_HISTORY_WINDOW", "HistoryDecision", "HistoryAccessPolicy", "HistoryNotAvailableError"]


class HistoryNotAvailableError(Exception):
    """An owned interview lies outside the caller's current history window. Carries nothing about the interview."""


@dataclass(frozen=True)
class HistoryDecision:
    window: int | None      # None = the complete eligible retained history
    reason: str             # gate_disabled | premium | basic | unresolved | override_premium | override_basic

    @property
    def restricted(self) -> bool:
        return self.window is not None


class HistoryAccessPolicy:
    """Stateless per request: nothing is cached, so a plan change takes effect on the very next read."""

    def __init__(self, entitlements, *, override: Callable[[int], str] | None = None) -> None:
        if override is not None and (os.environ.get("API_ENV") or "development").strip().lower() not in _TEST_ENVS:
            # An injected (synthetic) decision is a test seam only: it can never be used by a hosted environment.
            raise ValueError("A synthetic history-access decision cannot be used outside development and test.")
        self._entitlements = entitlements
        self._override = override

    def decide(self, user_id: int) -> HistoryDecision:
        if not HISTORY_RESTRICTIONS_ENFORCED:
            return HistoryDecision(None, "gate_disabled")                     # existing candidates keep exactly what they have today
        if self._override is not None:
            chosen = self._override(int(user_id))
            return HistoryDecision(None, "override_premium") if chosen == "premium" else HistoryDecision(BASIC_HISTORY_WINDOW, "override_basic")
        from src.application.plan_state import PREMIUM, UNRESOLVED, resolve_plan_state

        state = resolve_plan_state(self._entitlements, user_id)
        if state == PREMIUM:
            return HistoryDecision(None, "premium")
        return HistoryDecision(BASIC_HISTORY_WINDOW, "unresolved" if state == UNRESOLVED else "basic")

    def window_for(self, user_id: int) -> int | None:
        return self.decide(user_id).window
