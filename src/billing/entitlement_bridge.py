"""Billing-to-entitlement bridge (W12.4D-D): the ONLY place provider-verified billing state may influence product access.

Inputs: a reconciled ``BillingProviderLink`` (verified ownership, verified price mapping, authoritative provider state) and an EXPLICIT entitlement
policy. Never inputs: a client claim, a redirect parameter, a raw provider id from a request, an unverified event, a mock flag.

Policy boundary. The owner has NOT approved trial, grace, refund, cancellation, dispute or price rules, so the runtime policy is UNAPPROVED and
``decide`` returns ``policy_unapproved``: nothing is granted or revoked, only the evaluation is recorded as evidence. Offline tests inject a clearly
named SYNTHETIC policy. A rule the owner has not decided is ``None`` and yields ``hold`` (leave access as it is and flag the link for review):
undecided never means grant and never means revoke.

Ownership of access. A provider-managed grant is a ``subscriptions`` row with ``source = "provider"`` created by THIS bridge; only such a row is ever
ended by it. ``admin``, ``migration`` and ``system_default`` assignments are never overridden by a grant (admin and migration) and never ended by a revoke.
The bridge never extends an entitlement: plan assignment has no expiry here, so a replayed event cannot extend access twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select

from src.entitlements import DefaultPlanUnavailable, ensure_default_subscription
from src.persistence import (
    BillingEntitlementDecision as ED, PlanVersion, PLAN_STATUS_ACTIVE, SUBSCRIPTION_STATUS_ACTIVE, SUBSCRIPTION_STATUS_ENDED,
    Subscription, utcnow,
)

ACTIONS = ("keep", "revoke")


@dataclass(frozen=True)
class EntitlementPolicy:
    policy_id: str
    approved: bool
    grant_plan_codes: tuple[str, ...] = ("premium",)
    trial_grants: bool | None = None            # None = owner has not decided
    past_due: str | None = None                 # "keep" | "revoke" | None (undecided)
    unpaid: str | None = None
    canceled: str | None = None                 # applies to canceled and incomplete_expired
    paused: str | None = None
    full_refund: str | None = None
    dispute_open: str | None = None
    dispute_lost: str | None = None
    synthetic: bool = False

    def __post_init__(self) -> None:
        for name in ("past_due", "unpaid", "canceled", "paused", "full_refund", "dispute_open", "dispute_lost"):
            if getattr(self, name) not in (None, *ACTIONS):
                raise ValueError(f"{name} must be keep, revoke or None")


UNAPPROVED_POLICY = EntitlementPolicy(policy_id="unapproved", approved=False)


def runtime_policy() -> EntitlementPolicy:
    """The policy the running system uses. There is NO owner-approved policy in code, so this is always unapproved, whatever
    ``PAID_ENTITLEMENT_POLICY_APPROVED`` says: approving rules is a reviewed code change that adds a policy here, never a setting."""
    return UNAPPROVED_POLICY


@dataclass(frozen=True)
class Decision:
    action: str            # grant | revoke | keep | none | hold | policy_unapproved
    reason: str


def _rule(value: str | None, *, undecided: str) -> tuple[str | None, str]:
    return (None, undecided) if value is None else (value, "policy")


def decide(link, policy: EntitlementPolicy) -> Decision:
    """Pure: verified link state + explicit policy -> a decision. No I/O."""
    if not policy.approved:
        return Decision("policy_unapproved", "policy_not_approved")
    state = link.provider_state
    if state in ("canceled", "incomplete_expired"):
        rule, why = _rule(policy.canceled, undecided="cancellation_policy_undecided")
        return Decision("hold", why) if rule is None else Decision(rule, "subscription_ended")
    if state == "unpaid":
        rule, why = _rule(policy.unpaid, undecided="unpaid_policy_undecided")
        return Decision("hold", why) if rule is None else Decision(rule, "subscription_unpaid")
    if link.refund_state == "full":
        rule, why = _rule(policy.full_refund, undecided="refund_policy_undecided")
        if rule is None:
            return Decision("hold", why)
        if rule == "revoke":
            return Decision("revoke", "full_refund")
    if link.dispute_state == "lost":
        rule, why = _rule(policy.dispute_lost, undecided="dispute_policy_undecided")
        if rule is None:
            return Decision("hold", why)
        if rule == "revoke":
            return Decision("revoke", "dispute_lost")
    if link.dispute_state == "open":
        rule, why = _rule(policy.dispute_open, undecided="dispute_policy_undecided")
        if rule is None:
            return Decision("hold", why)
        if rule == "revoke":
            return Decision("revoke", "dispute_open")
    if state == "past_due":
        rule, why = _rule(policy.past_due, undecided="grace_policy_undecided")
        return Decision("hold", why) if rule is None else Decision(rule, "past_due")
    if state == "paused":
        rule, why = _rule(policy.paused, undecided="pause_policy_undecided")
        return Decision("hold", why) if rule is None else Decision(rule, "paused")
    if state == "trialing":
        if policy.trial_grants is None:
            return Decision("hold", "trial_policy_undecided")
        return Decision("grant", "trial_allowed") if policy.trial_grants else Decision("none", "trial_not_granting")
    if state == "active":
        if link.latest_invoice_state != "paid":
            return Decision("hold", "payment_not_confirmed")        # active without a paid invoice is not payment evidence
        return Decision("grant", "active_and_paid")
    return Decision("none", "not_eligible_state")                   # incomplete


@dataclass
class Outcome:
    decision: str
    reason: str
    applied: bool = False
    subscription_id: int | None = None
    notes: list[str] = field(default_factory=list)


def _active_row(s, user_id: int) -> Subscription | None:
    return s.scalar(select(Subscription).where(Subscription.user_id == user_id, Subscription.status == SUBSCRIPTION_STATUS_ACTIVE))


def provider_grant_exists(s, user_id: int) -> bool:
    """Read-only: does this candidate currently hold a provider-managed (bridge-created) active assignment?"""
    row = _active_row(s, user_id)
    return row is not None and row.source == "provider"


def evaluate_and_apply(s, link, policy: EntitlementPolicy, *, event_id: int | None, now: datetime | None = None) -> Outcome:
    """Evaluate ``link`` under ``policy`` and apply the result inside the CALLER's transaction. Records the evidence row. Idempotent: replaying the same
    verified state changes nothing."""
    now = now or utcnow()
    d = decide(link, policy)
    out = Outcome(d.action, d.reason)
    plan = s.get(PlanVersion, link.plan_version_id)
    active = _active_row(s, link.user_id)
    if d.action == "grant":
        if plan is None or plan.status != PLAN_STATUS_ACTIVE or plan.plan_code not in policy.grant_plan_codes:
            out.decision, out.reason = "refused", "plan_version_not_grantable"
        elif active is not None and active.source in ("admin", "migration"):
            out.decision, out.reason = "skipped_manual_assignment", "manual_assignment_preserved"
        elif active is not None and active.source == "provider" and active.plan_version_id == plan.id:
            out.decision, out.reason = "keep", "already_granted"                      # replay: nothing changes, nothing is extended
            link.entitlement_subscription_id = active.id
        else:
            if active is not None:
                active.status, active.ended_at = SUBSCRIPTION_STATUS_ENDED, now         # system_default or an older provider row
                s.flush()
            row = Subscription(user_id=link.user_id, plan_version_id=plan.id, status=SUBSCRIPTION_STATUS_ACTIVE, source="provider", started_at=now)
            s.add(row)
            s.flush()
            link.entitlement_subscription_id = row.id
            out.applied, out.subscription_id = True, row.id
    elif d.action == "revoke":
        mine = active is not None and active.source == "provider" and active.id == link.entitlement_subscription_id
        if mine:
            active.status, active.ended_at = SUBSCRIPTION_STATUS_ENDED, now
            s.flush()
            try:
                ensure_default_subscription(s, link.user_id)
            except DefaultPlanUnavailable:
                out.notes.append("default_plan_unavailable")
            out.applied = True
        else:
            out.decision, out.reason = "keep", "nothing_provider_owned_to_revoke"     # a manual or newer assignment is never revoked by this link
    link.entitlement_decision = out.decision
    s.add(ED(link_id=link.id, event_id=event_id, decision=out.decision, reason=out.reason[:60], policy_id=policy.policy_id[:60],
             provider_state=link.provider_state, applied=out.applied, created_at=now))
    return out


