"""Operational health alert categories (package 05C, PR 2). Additive and data-preserving: the CHECK on ``admin_notifications.category`` accepts seven more code-defined categories
(``api_error_rate_high``, ``worker_unhealthy``, ``job_queue_backlog``, ``indexing_stalled``, ``provider_unhealthy``, ``quota_reaper_stale``, ``ai_budget_attention``). No table, column
or row is added or changed. It is the only schema change of PR 2 and exists because the in-app alert mechanism pins its categories in a database constraint (the same reason as 0040).

The downgrade is FAIL-CLOSED: it refuses (deleting nothing) while any alert row uses one of the new categories, because restoring the narrower constraint would either fail or force
their deletion. Resolve and remove those alerts deliberately first. Chains from 0044 (PR 1, the budget governor ledger); the lead re-chains if another package takes 0045 first.

Revision ID: 0045_monitoring_alert_categories
Revises: 0044_ai_budget_ledger
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0045_monitoring_alert_categories"
down_revision = "0044_ai_budget_ledger"
branch_labels = None
depends_on = None

OLD = ("auth_failure_burst", "admin_access_denied_burst", "job_failed", "knowledge_collection_lost", "knowledge_source_files_missing", "knowledge_identity_mismatch",
       "knowledge_embedding_mismatch")
NEW_ONLY = ("api_error_rate_high", "worker_unhealthy", "job_queue_backlog", "indexing_stalled", "provider_unhealthy", "quota_reaper_stale", "ai_budget_attention")


def _in(values: tuple[str, ...]) -> str:
    return f"category IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    with op.batch_alter_table("admin_notifications") as b:
        b.drop_constraint("ck_notification_category", type_="check")
        b.create_check_constraint("ck_notification_category", _in(OLD + NEW_ONLY))


def downgrade() -> None:
    """FAIL CLOSED: refuses (deleting nothing) while any alert uses an operational-health category."""
    bind = op.get_bind()
    count = bind.execute(sa.text(f"SELECT COUNT(*) FROM admin_notifications WHERE category IN ({', '.join(repr(v) for v in NEW_ONLY)})")).scalar() or 0
    if count:
        raise RuntimeError(f"Refusing to downgrade 0045_monitoring_alert_categories: {count} operational-health alert row(s) exist. Resolve and remove them deliberately first.")
    with op.batch_alter_table("admin_notifications") as b:
        b.drop_constraint("ck_notification_category", type_="check")
        b.create_check_constraint("ck_notification_category", _in(OLD))
