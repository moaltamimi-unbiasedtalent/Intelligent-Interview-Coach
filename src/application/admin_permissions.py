"""Admin permission registry, code-defined role presets and the deterministic resolver (P10B-W10.1).

One source of truth for ``platform.<domain>.<action>`` permissions (the canonical 43 from
``docs/capstone/admin/ADMIN_PLATFORM_MASTER_PLAN.md`` section 5; there is NO break-glass permission, by
owner decision AD-02). Roles are code-defined presets (AD-08): no custom roles, no role tables.

Resolution is default-deny and server-side only: an unknown, missing, candidate (``user``) or any
unrecognised role resolves to the empty set; nothing is read from the browser. A platform admin is NOT a
private-candidate-data superuser: no permission here inspects CV, document, answer, Mo conversation,
memory, evidence, report or preparation-chat content.
"""

from __future__ import annotations

from typing import Final

# --- canonical registry (43) -----------------------------------------------------------------------
PERMISSIONS: Final[tuple[str, ...]] = (
    "platform.ai.activate",
    "platform.ai.manage",
    "platform.ai.read",
    "platform.audit.export",
    "platform.audit.read",
    "platform.billing.read",
    "platform.billing.refund",
    "platform.config.manage",
    "platform.flags.manage",
    "platform.flags.read",
    "platform.incidents.manage",
    "platform.integrations.manage",
    "platform.integrations.read",
    "platform.integrations.secret.rotate",
    "platform.jobs.manage",
    "platform.jobs.read",
    "platform.knowledge.approve",
    "platform.knowledge.manage",
    "platform.knowledge.read",
    "platform.legal.manage",
    "platform.overview.read",
    "platform.plans.manage",
    "platform.plans.price.change",
    "platform.plans.read",
    "platform.privacy.execute",
    "platform.privacy.read",
    "platform.releases.read",
    "platform.reports.commercial.read",
    "platform.reports.read",
    "platform.security.manage",
    "platform.security.read",
    "platform.subscriptions.manage",
    "platform.subscriptions.read",
    "platform.support.manage",
    "platform.support.note",
    "platform.support.read",
    "platform.support.reply",
    "platform.users.manage",
    "platform.users.read",
    "platform.users.role.assign",
    "platform.users.sessions.revoke",
    "platform.workspaces.manage",
    "platform.workspaces.read",
)
PERMISSION_SET: Final[frozenset[str]] = frozenset(PERMISSIONS)

# Names used by routes (kept as constants so a typo is an import error, not a silent deny).
OVERVIEW_READ = "platform.overview.read"
USERS_READ = "platform.users.read"
USERS_MANAGE = "platform.users.manage"
USERS_ROLE_ASSIGN = "platform.users.role.assign"
WORKSPACES_READ = "platform.workspaces.read"
WORKSPACES_MANAGE = "platform.workspaces.manage"
USERS_SESSIONS_REVOKE = "platform.users.sessions.revoke"
SUBSCRIPTIONS_MANAGE = "platform.subscriptions.manage"
PRIVACY_READ = "platform.privacy.read"
REPORTS_READ = "platform.reports.read"
FLAGS_READ = "platform.flags.read"
FLAGS_MANAGE = "platform.flags.manage"
INTEGRATIONS_READ = "platform.integrations.read"
AUDIT_READ = "platform.audit.read"
AI_READ = "platform.ai.read"
KNOWLEDGE_READ = "platform.knowledge.read"
RELEASES_READ = "platform.releases.read"
SECURITY_READ = "platform.security.read"
INTEGRATIONS_MANAGE = "platform.integrations.manage"
SECRET_ROTATE = "platform.integrations.secret.rotate"
JOBS_READ = "platform.jobs.read"
JOBS_MANAGE = "platform.jobs.manage"
PLANS_READ = "platform.plans.read"
PLANS_MANAGE = "platform.plans.manage"
SUBSCRIPTIONS_READ = "platform.subscriptions.read"
SUPPORT_READ = "platform.support.read"
SUPPORT_REPLY = "platform.support.reply"
SUPPORT_MANAGE = "platform.support.manage"
SUPPORT_NOTE = "platform.support.note"

# --- role presets (AD-08: code-defined; never persisted as tables) ---------------------------------
ROLE_CANDIDATE = "user"
ROLE_PLATFORM_ADMIN = "platform_admin"
ROLE_SUPPORT_OPERATOR = "support_operator"
ROLE_BILLING_ADMIN = "billing_admin"
ROLE_KNOWLEDGE_ADMIN = "knowledge_admin"
ROLE_SECURITY_PRIVACY_ADMIN = "security_privacy_admin"
ROLE_OPERATIONS_ADMIN = "operations_admin"

ADMIN_ROLES: Final[tuple[str, ...]] = (
    ROLE_PLATFORM_ADMIN,
    ROLE_SUPPORT_OPERATOR,
    ROLE_BILLING_ADMIN,
    ROLE_KNOWLEDGE_ADMIN,
    ROLE_SECURITY_PRIVACY_ADMIN,
    ROLE_OPERATIONS_ADMIN,
)

ROLE_PRESETS: Final[dict[str, frozenset[str]]] = {
    # Everything the pre-W10 platform_admin could legitimately do, mapped to explicit permissions.
    ROLE_PLATFORM_ADMIN: frozenset({
        OVERVIEW_READ, USERS_READ, USERS_MANAGE, USERS_ROLE_ASSIGN,
        WORKSPACES_READ, "platform.workspaces.manage", "platform.users.sessions.revoke",
        SUBSCRIPTIONS_MANAGE, "platform.subscriptions.read",
        SUPPORT_READ, SUPPORT_REPLY, SUPPORT_MANAGE, SUPPORT_NOTE,
        PLANS_READ, PLANS_MANAGE, INTEGRATIONS_MANAGE,
        PRIVACY_READ, REPORTS_READ, FLAGS_READ, FLAGS_MANAGE, INTEGRATIONS_READ,
        AUDIT_READ, AI_READ, KNOWLEDGE_READ, RELEASES_READ, SECURITY_READ,
    }),
    ROLE_SUPPORT_OPERATOR: frozenset({
        OVERVIEW_READ, USERS_READ, WORKSPACES_READ,
        "platform.support.read", "platform.support.reply", "platform.support.manage", "platform.support.note",
    }),
    ROLE_BILLING_ADMIN: frozenset({
        OVERVIEW_READ, USERS_READ,
        "platform.plans.read", "platform.plans.manage", "platform.plans.price.change",
        "platform.subscriptions.read", SUBSCRIPTIONS_MANAGE,
        "platform.billing.read", "platform.billing.refund", "platform.reports.commercial.read",
    }),
    ROLE_KNOWLEDGE_ADMIN: frozenset({
        OVERVIEW_READ, KNOWLEDGE_READ, "platform.knowledge.manage", "platform.knowledge.approve",
        AI_READ, "platform.jobs.read",
    }),
    ROLE_SECURITY_PRIVACY_ADMIN: frozenset({
        OVERVIEW_READ, USERS_READ, "platform.users.sessions.revoke",
        PRIVACY_READ, "platform.privacy.execute", "platform.legal.manage",
        SECURITY_READ, "platform.security.manage", "platform.incidents.manage",
        AUDIT_READ, "platform.audit.export",
    }),
    ROLE_OPERATIONS_ADMIN: frozenset({
        OVERVIEW_READ, "platform.jobs.read", "platform.jobs.manage",
        INTEGRATIONS_READ, "platform.integrations.manage",
        FLAGS_READ, FLAGS_MANAGE, "platform.config.manage",
        RELEASES_READ, REPORTS_READ, AI_READ,
    }),
}

# Candidate-private content inspection is deliberately NOT a permission. Guarded by the evaluator/tests.
BANNED_PERMISSION_FRAGMENTS: Final[tuple[str, ...]] = (
    "break_glass", "breakglass", "impersonat", "candidate", "cv", "document", "answer", "conversation",
    "memory", "evidence", "report.content", "chat", "view_as",
)


def permissions_for_role(role: str | None) -> frozenset[str]:
    """Resolve a persisted platform role to its permission set (unknown/None/candidate -> empty)."""
    if not role:
        return frozenset()
    return ROLE_PRESETS.get(role, frozenset())


def is_admin_role(role: str | None) -> bool:
    """True for any recognised admin preset (a coarse 'may open the admin area' signal, UX only)."""
    return bool(role) and role in ROLE_PRESETS


def sorted_permissions(role: str | None) -> list[str]:
    return sorted(permissions_for_role(role))
