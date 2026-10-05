"""Test helper for the W10.13 governed (two-person, step-up) role change. Drives the real HTTP API; nothing here bypasses a guard."""

from __future__ import annotations

API = "/api/v1"


def step_up(c, cookies, password):
    return c.post(f"{API}/admin/step-up", json={"password": password}, cookies=cookies)


def ensure_elevated(c, cookies, password):
    """Step up only when this session is not already elevated (the real client does the same; it also keeps the step-up rate limit honest)."""
    if not c.get(f"{API}/admin/step-up", cookies=cookies).json().get("elevated"):
        assert step_up(c, cookies, password).status_code == 200


def request_change(c, requester, target_id, role, *, password, reason="role change for test", elevate=True):
    if elevate:
        ensure_elevated(c, requester, password)
    return c.post(f"{API}/admin/role-changes", json={"target_user_id": target_id, "role": role, "reason": reason}, cookies=requester)


def approve(c, approver, public_id, *, password, elevate=True):
    if elevate:
        ensure_elevated(c, approver, password)
    return c.post(f"{API}/admin/role-changes/{public_id}/approve", cookies=approver)


def change_role(c, requester, approver, target_id, role, *, password, reason="role change for test"):
    """Request as one Admin, approve as a different Admin. Returns (request_response, approve_response | None)."""
    r = request_change(c, requester, target_id, role, password=password, reason=reason)
    if r.status_code != 200:
        return r, None
    return r, approve(c, approver, r.json()["public_id"], password=password)
