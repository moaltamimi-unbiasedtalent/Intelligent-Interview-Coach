"""Protection rules shared by every Admin Users action (03C). Evaluated INSIDE the mutation transaction against CURRENT database state."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.admin_users.revision import account_revision
from src.application.admin_permissions import permissions_for_role
from src.application.errors import ConflictError
from src.persistence import ACCOUNT_STATUS_ACTIVE, User


class AdminForbidden(PermissionError):
    """The actor may not act on this account (a more privileged account). Mapped to HTTP 403."""


STALE_MESSAGE = "This account changed since you loaded it. Reload and review before acting."


def make_precondition(*, actor_user_id: int, expected_revision: str | None, allow_self: bool = False, hierarchy: bool = True,
                      self_message: str = "You cannot do this to your own account."):
    """Build the ``precondition(session, target)`` hook: self-action, privilege hierarchy and stale-revision checks, in that order.

    ``expected_revision=None`` skips only the revision check (legacy routes that still accept it as optional)."""

    def check(s: Session, target: User) -> None:
        if target.id == actor_user_id and not allow_self:
            raise ConflictError(self_message)
        actor = s.get(User, actor_user_id)
        if actor is None or actor.status != ACCOUNT_STATUS_ACTIVE:
            raise AdminForbidden("The acting administrator is no longer active.")
        if hierarchy and target.id != actor_user_id and not permissions_for_role(target.platform_role) <= permissions_for_role(actor.platform_role):
            # Cannot act on an account holding authority the actor does not hold (no escalation by proxy).
            raise AdminForbidden("You cannot act on an account with more authority than your own.")
        if expected_revision is not None and account_revision(s, target) != expected_revision:
            raise ConflictError(STALE_MESSAGE)

    return check
