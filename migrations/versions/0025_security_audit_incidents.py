"""Security, audit and incident management (P10B-W10.13). SCHEMA ONLY: nothing is seeded (no incidents, alerts, role requests or elevated sessions).

Adds ``admin_incidents``, ``incident_events`` (append-only history), ``incident_tickets`` (identifier-only links), ``admin_notifications`` (durable in-app alerts) and
``admin_role_change_requests`` (two-person role changes), the step-up columns on ``auth_sessions``, and DB-level append-only triggers on ``audit_events`` and
``incident_events``: DELETE and arbitrary UPDATE are rejected; the ONLY permitted UPDATE is ``actor_user_id`` going from a value to NULL (account-deletion
anonymisation via the FK ``ON DELETE SET NULL``). Not tamper-proof against a database owner/superuser. Downgrade removes the triggers (and the PostgreSQL functions)
before the tables. Chains from 0024. Single head.

Revision ID: 0025_security_audit_incidents
Revises: 0024_reporting_analytics
Create Date: 2026-10-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

INCIDENT_SEVERITIES = ("low", "medium", "high", "critical")
INCIDENT_STATUSES = ("open", "investigating", "monitoring", "resolved", "closed")
INCIDENT_SERVICES = ("authentication", "agent", "practice", "research", "documents", "integrations", "knowledge", "jobs",
                     "billing", "privacy", "admin", "platform")
ALERT_CATEGORIES = ("auth_failure_burst", "admin_access_denied_burst", "job_failed")
ALERT_SEVERITIES = ("low", "medium", "high", "critical")
ALERT_STATES = ("active", "acknowledged", "resolved")
ROLE_REQUEST_STATUSES = ("pending", "applied", "rejected", "cancelled", "stale")

# The trigger DDL is FROZEN here (a copy of the W10.13 definition) so later changes to the application models cannot alter this migration.


def append_only_trigger_ddl(table: str, dialect: str) -> list[str]:
    """DDL for DB-level append-only protection of ``table`` (P10B-W10.13). DELETE is rejected. UPDATE is rejected unless the ONLY change is
    ``actor_user_id`` going from a value to NULL (the FK ``ON DELETE SET NULL`` account-deletion anonymisation). Not tamper-proof against a
    database owner/superuser, who can drop the trigger; production DBA privileges remain a deployment responsibility."""
    cols = ("id", "event_type", "target_type", "target_id", "result", "request_id", "context", "created_at") if table == "audit_events" else None
    if table == "incident_events":
        cols = ("id", "incident_id", "action", "prior_status", "new_status", "request_id", "meta", "created_at")
    assert cols is not None
    msg = f"{table} is append-only"
    if dialect == "sqlite":
        same = " AND ".join(f"NEW.{c} IS OLD.{c}" for c in cols)
        return [
            f"CREATE TRIGGER IF NOT EXISTS trg_{table}_no_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, '{msg}'); END",
            f"CREATE TRIGGER IF NOT EXISTS trg_{table}_no_update BEFORE UPDATE ON {table} "
            f"WHEN NOT ({same} AND NEW.actor_user_id IS NULL AND OLD.actor_user_id IS NOT NULL) BEGIN SELECT RAISE(ABORT, '{msg}'); END",
        ]
    if dialect == "postgresql":
        # JSON columns have no equality operator in PostgreSQL, so compare their text form.
        parts = []
        for c in cols:
            parts.append(f"NEW.{c}::text IS NOT DISTINCT FROM OLD.{c}::text" if c in ("context", "meta") else f"NEW.{c} IS NOT DISTINCT FROM OLD.{c}")
        same = " AND ".join(parts)
        return [
            f"CREATE OR REPLACE FUNCTION {table}_guard() RETURNS trigger AS $$ BEGIN "
            f"IF TG_OP = 'DELETE' THEN RAISE EXCEPTION '{msg}'; END IF; "
            f"IF NOT ({same} AND NEW.actor_user_id IS NULL AND OLD.actor_user_id IS NOT NULL) THEN RAISE EXCEPTION '{msg}'; END IF; "
            f"RETURN NEW; END; $$ LANGUAGE plpgsql",
            f"DROP TRIGGER IF EXISTS trg_{table}_guard ON {table}",
            f"CREATE TRIGGER trg_{table}_guard BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {table}_guard()",
        ]
    return []


def append_only_trigger_drop_ddl(table: str, dialect: str) -> list[str]:
    if dialect == "sqlite":
        return [f"DROP TRIGGER IF EXISTS trg_{table}_no_delete", f"DROP TRIGGER IF EXISTS trg_{table}_no_update"]
    if dialect == "postgresql":
        return [f"DROP TRIGGER IF EXISTS trg_{table}_guard ON {table}", f"DROP FUNCTION IF EXISTS {table}_guard()"]
    return []


revision = "0025_security_audit_incidents"
down_revision = "0024_reporting_analytics"
branch_labels = None
depends_on = None

TRIGGER_TABLES = ("audit_events", "incident_events")


def _in(column, values):
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    dt = lambda: sa.DateTime(timezone=True)  # noqa: E731
    op.create_table(
        "admin_incidents",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False), sa.Column("severity", sa.String(length=12), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"), sa.Column("affected_service", sa.String(length=24), nullable=False),
        sa.Column("started_at", dt(), nullable=False), sa.Column("resolved_at", dt(), nullable=True),
        sa.Column("owner_admin_user_id", sa.Integer(), nullable=True), sa.Column("affected_user_estimate", sa.Integer(), nullable=True),
        sa.Column("root_cause", sa.String(length=1000), nullable=True), sa.Column("remediation", sa.String(length=1000), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True), sa.Column("created_at", dt(), nullable=False), sa.Column("updated_at", dt(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_admin_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("severity", INCIDENT_SEVERITIES), name="ck_incident_severity"),
        sa.CheckConstraint(_in("status", INCIDENT_STATUSES), name="ck_incident_status"),
        sa.CheckConstraint(_in("affected_service", INCIDENT_SERVICES), name="ck_incident_service"),
        sa.CheckConstraint("affected_user_estimate IS NULL OR affected_user_estimate >= 0", name="ck_incident_estimate"),
        sa.CheckConstraint("revision >= 0", name="ck_incident_revision"),
        sa.CheckConstraint("(status IN ('resolved','closed') AND resolved_at IS NOT NULL) OR (status NOT IN ('resolved','closed') AND resolved_at IS NULL)",
                           name="ck_incident_resolved_at"),
    )
    op.create_index("ix_admin_incidents_public_id", "admin_incidents", ["public_id"], unique=True)
    op.create_index("ix_incident_status_updated", "admin_incidents", ["status", "updated_at"])

    op.create_table(
        "incident_events",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("prior_status", sa.String(length=16), nullable=True), sa.Column("new_status", sa.String(length=16), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True), sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True), sa.Column("created_at", dt(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["incident_id"], ["admin_incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_incident_events_incident", "incident_events", ["incident_id", "id"])

    op.create_table(
        "incident_tickets",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("linked_by_user_id", sa.Integer(), nullable=True), sa.Column("linked_at", dt(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["incident_id"], ["admin_incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("incident_id", "ticket_id", name="uq_incident_ticket"),
    )
    op.create_index("ix_incident_tickets_incident_id", "incident_tickets", ["incident_id"])
    op.create_index("ix_incident_tickets_ticket_id", "incident_tickets", ["ticket_id"])

    op.create_table(
        "admin_notifications",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False), sa.Column("severity", sa.String(length=12), nullable=False),
        sa.Column("dedupe_key", sa.String(length=80), nullable=False), sa.Column("state", sa.String(length=14), nullable=False, server_default="active"),
        sa.Column("source_type", sa.String(length=24), nullable=False), sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False), sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", dt(), nullable=False), sa.Column("last_seen_at", dt(), nullable=False),
        sa.Column("acknowledged_at", dt(), nullable=True), sa.Column("acknowledged_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", dt(), nullable=True), sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", dt(), nullable=False), sa.Column("updated_at", dt(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["acknowledged_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("dedupe_key", name="uq_admin_notification_dedupe"),
        sa.CheckConstraint(_in("category", ALERT_CATEGORIES), name="ck_notification_category"),
        sa.CheckConstraint(_in("severity", ALERT_SEVERITIES), name="ck_notification_severity"),
        sa.CheckConstraint(_in("state", ALERT_STATES), name="ck_notification_state"),
        sa.CheckConstraint("revision >= 0", name="ck_notification_revision"),
        sa.CheckConstraint("occurrence_count >= 1", name="ck_notification_occurrences"),
        sa.CheckConstraint("last_seen_at >= first_seen_at", name="ck_notification_seen"),
    )
    op.create_index("ix_admin_notifications_public_id", "admin_notifications", ["public_id"], unique=True)
    op.create_index("ix_notification_state_seen", "admin_notifications", ["state", "last_seen_at"])

    op.create_table(
        "admin_role_change_requests",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=False), sa.Column("before_role", sa.String(length=32), nullable=False),
        sa.Column("requested_role", sa.String(length=32), nullable=False), sa.Column("requester_user_id", sa.Integer(), nullable=True),
        sa.Column("approver_user_id", sa.Integer(), nullable=True), sa.Column("status", sa.String(length=12), nullable=False, server_default="pending"),
        sa.Column("reason", sa.String(length=200), nullable=False), sa.Column("decision_reason", sa.String(length=200), nullable=True),
        sa.Column("requested_at", dt(), nullable=False), sa.Column("decided_at", dt(), nullable=True), sa.Column("applied_at", dt(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("status", ROLE_REQUEST_STATUSES), name="ck_role_request_status"),
        sa.CheckConstraint("revision >= 0", name="ck_role_request_revision"),
        sa.CheckConstraint("approver_user_id IS NULL OR requester_user_id IS NULL OR approver_user_id <> requester_user_id", name="ck_role_request_distinct"),
        sa.CheckConstraint("requester_user_id IS NULL OR requester_user_id <> target_user_id", name="ck_role_request_not_self"),
    )
    op.create_index("ix_admin_role_change_requests_public_id", "admin_role_change_requests", ["public_id"], unique=True)
    op.create_index("ix_role_request_status", "admin_role_change_requests", ["status", "requested_at"])
    op.create_index("uq_role_request_one_pending", "admin_role_change_requests", ["target_user_id"], unique=True,
                    sqlite_where=sa.text("status = 'pending'"), postgresql_where=sa.text("status = 'pending'"))

    with op.batch_alter_table("auth_sessions") as batch:
        batch.add_column(sa.Column("elevated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("elevated_until", sa.DateTime(timezone=True), nullable=True))

    dialect = op.get_bind().dialect.name
    for table in TRIGGER_TABLES:
        for stmt in append_only_trigger_ddl(table, dialect):
            op.execute(stmt)


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    for table in TRIGGER_TABLES:
        for stmt in append_only_trigger_drop_ddl(table, dialect):
            op.execute(stmt)
    with op.batch_alter_table("auth_sessions") as batch:
        batch.drop_column("elevated_until")
        batch.drop_column("elevated_at")
    op.drop_table("admin_role_change_requests")
    op.drop_table("admin_notifications")
    op.drop_table("incident_tickets")
    op.drop_table("incident_events")
    op.drop_table("admin_incidents")
