"""Explicit resource-sharing application service (Capstone P6.5).

Sharing is EXPLICIT and allow-listed. A candidate may share only an allow-listed resource
they OWN (interview report / story / preparation summary), VIEW-only, into a workspace they
are an active member of. Ownership never transfers. The access decision is re-derived on
every read, so revocation and source deletion take effect immediately — a cached/shared
link can never bypass them. Reading shared content loads the resource as its OWNER (owner
scoping intact), gated by a valid share grant.
"""

from __future__ import annotations

from typing import Callable

from src.application.errors import ValidationError
from src.persistence import (
    SHARE_PERMISSION_VIEW,
    SHAREABLE_RESOURCE_TYPES,
)

__all__ = ["SharingService", "SharingPermissionError", "SharingNotFoundError"]

# owner_verifier(resource_id, owner_user_id) -> bool  (does this user own this resource?)
OwnerVerifier = Callable[[str, int], bool]
# owner_loader(resource_id, owner_user_id) -> dict | None  (safe projection of the resource)
OwnerLoader = Callable[[str, int], "dict | None"]


class SharingPermissionError(Exception):
    """Authenticated but not authorized (not the owner / not a member)."""


class SharingNotFoundError(Exception):
    """Resource/grant not found or not visible to the caller."""


class SharingService:
    def __init__(self, *, workspaces, audit=None,
                 owner_verifiers: dict[str, OwnerVerifier] | None = None,
                 owner_loaders: dict[str, OwnerLoader] | None = None) -> None:
        self._ws = workspaces
        self._audit = audit
        self._verifiers = owner_verifiers or {}
        self._loaders = owner_loaders or {}

    def _audit_event(self, event_type: str, actor_user_id: int, workspace_id: int, **ctx) -> None:
        if self._audit is None:
            return
        try:
            self._audit.record(event_type=event_type, actor_user_id=actor_user_id,
                               target_type="share", target_id=str(workspace_id),
                               context={k: v for k, v in ctx.items() if v is not None})
        except Exception:  # noqa: BLE001
            pass

    def share(self, *, user_id: int, workspace_id: int, resource_type: str,
              resource_id: str) -> dict:
        """Create a VIEW share of an OWNED, allow-listed resource into a member workspace."""
        if resource_type not in SHAREABLE_RESOURCE_TYPES:
            raise ValidationError("This resource type cannot be shared.")
        rid = (resource_id or "").strip()
        if not rid:
            raise ValidationError("A resource id is required.")
        # The caller must be an ACTIVE member of the target workspace.
        if self._ws.member_role(workspace_id, user_id) is None:
            raise SharingPermissionError("You are not a member of this workspace.")
        # The caller must OWN the resource (owner-verified; deny if unverifiable).
        verifier = self._verifiers.get(resource_type)
        if verifier is None or not _safe_bool(verifier, rid, user_id):
            raise SharingPermissionError("You can only share a resource you own.")
        share_id = self._ws.create_share(
            owner_user_id=user_id, workspace_id=workspace_id, resource_type=resource_type,
            resource_id=rid, permission=SHARE_PERMISSION_VIEW)
        self._audit_event("share.created", user_id, workspace_id,
                         resource_type=resource_type)
        return {"share_id": share_id, "status": "active", "permission": SHARE_PERMISSION_VIEW}

    def revoke(self, *, user_id: int, share_id: int) -> dict:
        """Revoke a share — only the owner may. Takes effect immediately."""
        grant = self._ws.get_share(share_id)
        if grant is None or grant["owner_user_id"] != user_id:
            raise SharingNotFoundError("Share not found.")
        self._ws.revoke_share(share_id=share_id, owner_user_id=user_id)
        self._audit_event("share.revoked", user_id, grant["workspace_id"],
                         resource_type=grant["resource_type"])
        return {"status": "revoked"}

    def list_shared_by_me(self, *, user_id: int) -> list[dict]:
        return self._ws.list_shares_by_owner(user_id)

    def list_shared_with_me(self, *, user_id: int) -> list[dict]:
        return self._ws.list_shares_for_member(user_id)

    def can_view(self, *, user_id: int, resource_type: str, resource_id: str) -> int | None:
        """Return the owner id iff the caller may VIEW the resource (owner OR valid share);
        else None. This is the single authorization decision, re-derived every call."""
        rid = (resource_id or "").strip()
        verifier = self._verifiers.get(resource_type)
        if verifier is not None and _safe_bool(verifier, rid, user_id):
            return user_id  # the caller owns it
        return self._ws.active_share_owner_for_member(
            user_id=user_id, resource_type=resource_type, resource_id=rid)

    def resolve_shared_resource(self, *, user_id: int, resource_type: str,
                                resource_id: str) -> dict:
        """Load a shared resource as its OWNER, gated by a valid share (or ownership).

        Owner scoping stays intact: the loader is called with the OWNER's id, never the
        caller's, and only after the access decision passes. Revocation/deletion → 404.
        """
        if resource_type not in SHAREABLE_RESOURCE_TYPES:
            raise ValidationError("This resource type cannot be shared.")
        owner_id = self.can_view(user_id=user_id, resource_type=resource_type, resource_id=resource_id)
        if owner_id is None:
            raise SharingNotFoundError("Not found.")
        loader = self._loaders.get(resource_type)
        if loader is None:
            raise SharingNotFoundError("Not found.")
        resource = loader((resource_id or "").strip(), owner_id)
        if resource is None:
            # The source was deleted after the grant — never resurrect it.
            raise SharingNotFoundError("Not found.")
        return {"resource_type": resource_type, "resource_id": resource_id,
                "shared_by_owner": owner_id != user_id, "resource": resource}

    def invalidate_on_delete(self, *, owner_user_id: int, resource_type: str,
                             resource_id: str) -> int:
        """Revoke all grants of a resource when the source resource is deleted."""
        return self._ws.invalidate_shares_for_resource(
            owner_user_id=owner_user_id, resource_type=resource_type,
            resource_id=(resource_id or "").strip())


def _safe_bool(fn, *args) -> bool:
    try:
        return bool(fn(*args))
    except Exception:  # noqa: BLE001 - a failing verifier denies (fail-closed)
        return False
